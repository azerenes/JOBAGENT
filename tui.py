# -*- coding: utf-8 -*-
"""JOBAGENT — tam ekran terminal arayüzü (Textual TUI).

Akış: meslek -> CV yolu -> site seçimi (1-3) -> uygun işler listelenir
      -> kullanıcı seçer (Boşluk) -> seçililere toplu başvuru.
"""
import os
import sys
import threading

from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (Button, Checkbox, DataTable, Footer, Input,
                             Label, LoadingIndicator, Log, ProgressBar, Static)

from browser import DATA_DIR, load_config
from cv_reader import extract_text
from export import build_tick_html
from worker import get_session, load_answers, new_session, run_apply, run_search
from sites import ADAPTERS

try:
    sys.stdout.reconfigure(errors='replace')
    sys.stderr.reconfigure(errors='replace')
except Exception:
    pass


CSS = """
Screen { align: center top; padding: 1 2; }
#wrap { width: 100%; max-width: 112; height: 100%; }
.title { text-style: bold; color: $accent; text-align: center; margin-bottom: 1; }
.hint { color: $text-muted; text-align: center; }
.warn { color: $warning; text-align: center; }
Label { margin-top: 1; }
Input { margin-bottom: 0; }
Checkbox { margin: 0 2 0 0; }
#sites { height: auto; }
#actions { height: auto; align-horizontal: center; }
Button { margin: 1 1 0 0; }
#table { height: 1fr; margin-top: 1; }
#log { height: 1fr; margin-top: 1; }
#count { color: $text-muted; text-align: center; }
"""


class SetupScreen(Screen):
    BINDINGS = [Binding('ctrl+q', 'quit', 'Çık')]

    def compose(self):
        cfg = load_config()
        with Vertical(id='wrap'):
            yield Static('JOBAGENT — İş Başvuru Otomasyonu', classes='title')
            yield Label('1) Mesleğiniz / arama kelimesi *')
            yield Input(placeholder='örn. Elektrik Teknisyeni', id='meslek')
            yield Label('2) CV dosyası (.pdf / .docx / .txt)')
            yield Input(placeholder='örn. C:\\Kullanıcılar\\...\\cv.pdf  (boş olabilir)', id='cv')
            yield Label('Şehir (URL slug)')
            yield Input(value=cfg.get('city', 'ankara'), id='sehir')
            yield Label('Ek arama kelimeleri (virgülle, opsiyonel)')
            yield Input(placeholder='örn. pano, otomasyon, zayıf akım', id='ek')
            yield Label('Hariç tutulacaklar (virgülle, opsiyonel)')
            yield Input(placeholder='örn. mühendis, satış, şef', id='exclude')
            yield Label('3) Kaynak siteler (en az birini seçin)')
            with Horizontal(id='sites'):
                for key, adapter in ADAPTERS.items():
                    yield Checkbox(adapter.label, id=f'site_{key}', value=(key == 'isinolsun'))
            yield Static('ÖNEMLİ: Seçilen sitelere tarayıcıdan önceden giriş yapılmış olmalıdır '
                         '(eleman.net, isinolsun.com, kariyer.net hesabıyla). Giriş yoksa başvuru '
                         'sırasında pencere açılıp giriş istenir ve akış bekler.', classes='warn')
            yield Button('Uygun İşleri Bul', variant='primary', id='start')
            yield Static('İpucu: sekmelerle dolaşın · ok/Enter ile gezinin · Ctrl+Q çıkış', classes='hint')
        yield Footer()

    def on_button_pressed(self, event):
        if event.button.id == 'start':
            self._start()

    def on_input_submitted(self, event):
        if event.input.id == 'exclude':
            self._start()

    def _start(self):
        meslek = self.query_one('#meslek', Input).value.strip()
        if not meslek:
            self.notify('Meslek zorunlu — önce mesleğinizi yazın', severity='error')
            self.query_one('#meslek', Input).focus()
            return
        sites = [k for k in ADAPTERS if self.query_one(f'#site_{k}', Checkbox).value]
        if not sites:
            self.notify('En az bir kaynak site seçin', severity='error')
            return
        sehir = self.query_one('#sehir', Input).value.strip() or 'ankara'
        ek = self.query_one('#ek', Input).value.strip()
        ex = self.query_one('#exclude', Input).value.strip()
        cv_path = self.query_one('#cv', Input).value.strip()
        cv_text = ''
        if cv_path:
            if not os.path.exists(cv_path):
                self.notify(f'CV bulunamadı: {cv_path}', severity='error')
                return
            cv_text = extract_text(cv_path)
            if not cv_text.strip():
                self.notify('CV metni çıkarılamadı (tarama sayfası olabilir), devam ediliyor...',
                            severity='warning')
        sessions = {}
        for site in sites:
            sid = new_session(site, meslek, sehir, ek, ex, cv_path, cv_text)
            sessions[site] = sid
        self.app.meslek = meslek
        self.app.sessions = sessions
        self.app.site_labels = {k: v.label for k, v in ADAPTERS.items()}
        self.app.push_screen(SearchScreen(sites))


class SearchScreen(Screen):
    BINDINGS = [Binding('ctrl+q', 'quit', 'Çık')]

    def __init__(self, sites):
        super().__init__()
        self.sites = sites

    def compose(self):
        with Vertical(id='wrap'):
            yield Static('Uygun işler aranıyor...', classes='title')
            yield LoadingIndicator()
            yield Log(highlight=True, id='log')
            yield Static('Bu sırada tarayıcı penceresi açılacaktır.', classes='hint')
        yield Footer()

    def on_mount(self):
        threading.Thread(target=self._run_all, daemon=True).start()

    def _log(self, msg):
        try:
            self.query_one('#log', Log).write_line(msg)
        except Exception:
            pass

    def _run_all(self):
        for site in self.sites:
            sid = self.app.sessions[site]
            label = self.app.site_labels.get(site, site)

            def st(msg, _label=label):
                self.app.call_from_thread(self._log, f'[{_label}] {msg}')

            self.app.call_from_thread(self._log, f'[{label}] arama başlıyor...')
            try:
                run_search(sid, status=st)
                n = len(get_session(sid)['jobs'])
                self.app.call_from_thread(self._log, f'[{label}] tamamlandı — {n} ilan listelendi')
            except Exception as exc:
                self.app.call_from_thread(self._log, f'[{label}] HATA: {exc}')
        self.app.call_from_thread(self.app.switch_screen, ResultsScreen(self.sites))


class ResultsScreen(Screen):
    BINDINGS = [
        Binding('space', 'toggle', 'Seç/Kaldır'),
        Binding('a', 'apply', 'Seçililere Başvur'),
        Binding('ctrl+q', 'quit', 'Çık'),
    ]

    def __init__(self, sites):
        super().__init__()
        self.sites = sites
        self.jobs = []
        self.checked = set()

    def compose(self):
        with Vertical(id='wrap'):
            yield Static('Uygun iş ilanları', classes='title')
            yield Static('', id='count')
            yield DataTable(id='table')
            with Horizontal(id='actions'):
                yield Button('Tümünü Seç', id='selall')
                yield Button('Tümünü Kaldır', id='selnone')
                yield Button('Seçililere Başvur', variant='primary', id='apply')
            yield Static('↑↓ gezin · Boşluk = seç/kaldır · A = seçililere başvur · Ctrl+Q çıkış', classes='hint')
        yield Footer()

    def on_mount(self):
        table = self.query_one('#table', DataTable)
        table.cursor_type = 'row'
        table.zebra_stripes = True
        table.add_column('', key='chk', width=4)
        table.add_column('Skor', key='skor', width=6)
        table.add_column('İlan', key='title')
        table.add_column('Firma', key='company')
        table.add_column('Yer', key='loc')
        table.add_column('Durum', key='durum')

        jobs = []
        for site in self.sites:
            s = get_session(self.app.sessions[site])
            for j in s['jobs']:
                if j['match_state'] == 'hariç':
                    continue
                j['_site'] = site
                jobs.append(j)
        order = {'uygun': 0, 'dusuk': 1, 'eslesme-yok': 2}
        jobs.sort(key=lambda j: (j['_site'], order.get(j['match_state'], 3), -j['score']))
        self.jobs = jobs

        stcolor = {'uygun': 'green', 'dusuk': 'yellow', 'eslesme-yok': 'red'}
        for i, j in enumerate(jobs):
            table.add_row('☐', str(j['score']), j['title'], j['company'] or '-',
                          j['location'] or '-',
                          Text(j['match_state'], style=stcolor.get(j['match_state'], '')),
                          key=str(i))
        self._update_count()
        table.focus()

    def _update_count(self):
        self.query_one('#count', Static).update(
            f"Seçili: {len(self.checked)} / {len(self.jobs)}  ·  kaynak: {', '.join(self.sites)}")

    def _refresh_marks(self):
        table = self.query_one('#table', DataTable)
        for i, j in enumerate(self.jobs):
            table.update_cell(str(i), 'chk', '☑' if j['job_id'] in self.checked else '☐')
        self._update_count()

    def _toggle_row(self, row):
        if not (0 <= row < len(self.jobs)):
            return
        j = self.jobs[row]
        if j['job_id'] in self.checked:
            self.checked.discard(j['job_id'])
            mark = '☐'
        else:
            self.checked.add(j['job_id'])
            mark = '☑'
        self.query_one('#table', DataTable).update_cell(str(row), 'chk', mark)
        self._update_count()

    def action_toggle(self):
        row = self.query_one('#table', DataTable).cursor_coordinate.row
        self._toggle_row(row)

    def on_button_pressed(self, event):
        bid = event.button.id
        if bid == 'selall':
            self.checked = {j['job_id'] for j in self.jobs}
            self._refresh_marks()
        elif bid == 'selnone':
            self.checked.clear()
            self._refresh_marks()
        elif bid == 'apply':
            self.action_apply()

    def action_apply(self):
        ids = {j['job_id'] for j in self.jobs if j['job_id'] in self.checked}
        if not ids:
            self.notify('Önce ilan seçin (Boşluk tuşu)', severity='warning')
            return
        by_site = {}
        for j in self.jobs:
            if j['job_id'] in ids:
                by_site.setdefault(j['_site'], []).append(j['job_id'])
        plan = [(self.app.sessions[site], site_ids) for site, site_ids in by_site.items()]
        self.app.push_screen(ApplyScreen(plan))


class ApplyScreen(Screen):
    BINDINGS = [Binding('ctrl+q', 'quit', 'Çık')]

    def __init__(self, plan):
        super().__init__()
        self.plan = plan
        self.total = sum(len(ids) for _, ids in plan)
        self.finished = False

    def compose(self):
        with Vertical(id='wrap'):
            yield Static('Başvurular sürüyor...', classes='title')
            yield ProgressBar(total=self.total, id='pb', show_eta=False)
            yield Log(highlight=True, id='log')
            yield Static('Tarayıcıda giriş gerekirse lütfen giriş yapın, otomatik devam eder.', classes='hint')
        yield Footer()

    def on_mount(self):
        threading.Thread(target=self._run_all, daemon=True).start()

    def _log(self, msg):
        try:
            self.query_one('#log', Log).write_line(msg)
        except Exception:
            pass

    def _progress(self, done):
        try:
            self.query_one('#pb', ProgressBar).advance(done - self.query_one('#pb', ProgressBar).progress)
        except Exception:
            pass

    def _run_all(self):
        bank = load_answers()
        for sid, ids in self.plan:
            s = get_session(sid)
            label = self.app.site_labels.get(s['site'], s['site'])

            def st(durum, done, total, title, _l=label):
                self.app.call_from_thread(self._log, f'[{_l}] {title} -> {durum}')
                self.app.call_from_thread(self._progress, done)

            def ask(questions):
                event = threading.Event()
                result = {}

                def show():
                    self.app.push_screen(QuestionScreen(questions, result, event))

                self.app.call_from_thread(show)
                event.wait()
                return result

            self.app.call_from_thread(self._log, f'[{label}] başvurular başlıyor ({len(ids)} ilan)...')
            try:
                run_apply(sid, ids, status=st, ask=ask, bank=bank)
            except Exception as exc:
                self.app.call_from_thread(self._log, f'[{label}] HATA: {exc}')

        htmls = []
        ok = once = bad = 0
        for sid, _ in self.plan:
            s = get_session(sid)
            out = os.path.join(DATA_DIR, f"takip_{s['site']}_{s['sid']}.html")
            with open(out, 'w', encoding='utf-8') as f:
                f.write(build_tick_html(s))
            htmls.append(out)
            for j in s['jobs']:
                if j['durum'] == 'basvuru-alindi':
                    ok += 1
                elif j['durum'] == 'daha-once':
                    once += 1
                elif j['durum']:
                    bad += 1
        self.app.call_from_thread(self._finish, ok, once, bad, htmls)

    def _finish(self, ok, once, bad, htmls):
        self.finished = True
        self.query_one('#pb', ProgressBar).advance(self.total - self.query_one('#pb', ProgressBar).progress)
        self.query_one('#wrap', Vertical).query_one('Static.title').update('Başvurular tamamlandı')
        log = self.query_one('#log', Log)
        log.write_line('')
        log.write_line(f"✓ Yeni başvuru: {ok}   ✓ Zaten başvurulmuş: {once}   ✗ Sorunlu: {bad}")
        log.write_line('')
        log.write_line('Tikli takip listeleri:')
        for h in htmls:
            log.write_line(f'   {h}')
        log.write_line('')
        log.write_line('Çıkmak için Ctrl+Q.')
        self.notify('Başvurular tamamlandı', severity='information')


class QuestionScreen(Screen):
    """Sirket sorularini kullaniciya soran ekran. Cevaplar ilk sorulu ilanda toplanir,
    sonrakilerde ayni sorular otomatik doldurulur."""

    BINDINGS = [Binding('ctrl+q', 'cancel', 'Vazgeç')]

    def __init__(self, questions, result, event):
        super().__init__()
        self.questions = questions
        self.result = result
        self.event = event

    def compose(self):
        with Vertical(id='wrap'):
            yield Static('Şirket soruları', classes='title')
            yield Static('Bu sorular ilk kez soruluyor. Cevaplarınız kaydedilir ve benzer sorular sonraki ilanlarda otomatik doldurulur.',
                         classes='hint')
            for i, (label, typ) in enumerate(self.questions):
                yield Label(f'{label}  [{typ}]')
                yield Input(placeholder='Cevabınız', id=f'q{i}')
            with Horizontal(id='actions'):
                yield Button('Gönder', variant='primary', id='ok')
            yield Static('Boş bırakılanlar doldurulmaz.', classes='hint')
        yield Footer()

    def on_button_pressed(self, event):
        if event.button.id == 'ok':
            self._submit()

    def on_input_submitted(self, event):
        if self.questions and event.input.id == f'q{len(self.questions) - 1}':
            self._submit()

    def _submit(self):
        for i, (label, _typ) in enumerate(self.questions):
            val = self.query_one(f'#q{i}', Input).value.strip()
            if val:
                self.result[label] = val
        self.app.pop_screen()
        self.event.set()

    def action_cancel(self):
        self.app.pop_screen()
        self.event.set()


class JobAgentApp(App):
    TITLE = 'JOBAGENT'
    CSS = CSS
    BINDINGS = [Binding('ctrl+q', 'quit', 'Çık')]

    def on_mount(self):
        self.push_screen(SetupScreen())


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'web':
        from app import app
        from browser import load_config
        cfg = load_config()
        print(f'Web arayüzü: http://{cfg.get("host", "127.0.0.1")}:{cfg.get("port", 5000)} (Ctrl+C ile durur)')
        app.run(host=cfg.get('host', '127.0.0.1'), port=cfg.get('port', 5000), debug=False)
        return
    if len(sys.argv) > 1 and sys.argv[1] in ('--cli', 'cli'):
        from cli import main as cli_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        cli_main()
        return
    if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h'):
        from cli import main as cli_main
        sys.argv = [sys.argv[0]] + sys.argv[1:]
        cli_main()
        return
    JobAgentApp().run()


if __name__ == '__main__':
    main()
