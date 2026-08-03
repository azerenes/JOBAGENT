# -*- coding: utf-8 -*-
"""Terminal (cmd / PowerShell) kullanicisi icin tam CLI arayuzu.

Ornek kullanim:
    python cli.py --site isinolsun --meslek "Elektrik Teknisyeni" --cv cv.pdf
    python cli.py -s kariyer -m "Kablo Teknikeri" --sehir ankara --ek-kelime "pano,otomasyon"
    python cli.py --site eleman --meslek "..." --cv cv.docx --apply-all

Parametresiz calisirsa interaktif sorularla ilerler.
"""
import argparse
import os
import sys

try:
    sys.stdout.reconfigure(errors='replace')
    sys.stderr.reconfigure(errors='replace')
except Exception:
    pass

from browser import DATA_DIR, load_config
from cv_reader import extract_text
from export import build_tick_html
from worker import get_session, load_answers, new_session, run_apply, run_search
from sites import ADAPTERS

DURUM_LABEL = {
    'basvuru-alindi': '✓ Başvuruldu',
    'daha-once': '✓ Zaten başvurulmuş',
    'giris-gerekli': '! Giriş gerekli',
    'challenge': '! Challenge (manuel çözüm gerekli)',
    'belirsiz': '? Belirsiz',
    'hata:buton-yok': '✗ Başvuru butonu bulunamadı',
}

BOS = {'', ' ', None}


def ask(label, default=''):
    d = f' [{default}]' if default else ''
    v = input(f'{label}{d}: ').strip()
    return v or default


def ask_choice(label, options, default=None):
    for i, (key, txt) in enumerate(options, 1):
        mark = ' (varsayılan)' if key == default else ''
        print(f'  {i}) {txt}{mark}')
    while True:
        v = input(f'{label}: ').strip()
        if not v and default:
            return default
        if v.isdigit() and 1 <= int(v) <= len(options):
            return options[int(v) - 1][0]
        print('Geçersiz seçim.')


def parse_numbers(spec, total):
    """'1,3,5-8' gibi secimi index setine cevirir."""
    out = set()
    for part in spec.replace(';', ',').split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            try:
                a, b = int(a), int(b)
                if a > b:
                    a, b = b, a
                out.update(range(max(1, a), min(total, b) + 1))
            except ValueError:
                pass
        else:
            try:
                n = int(part)
                if 1 <= n <= total:
                    out.add(n)
            except ValueError:
                pass
    return out


def build_session(args, cfg):
    site = args.site
    meslek = args.meslek
    if not meslek and not args.yes:
        meslek = ask('Mesleğiniz / Arama kelimesi (zorunlu)')
    if not meslek:
        print('HATA: meslek zorunlu.')
        sys.exit(2)

    sehir = args.sehir or ('' if args.yes else ask('Şehir', cfg.get('city', 'ankara')))
    sehir = sehir or cfg.get('city', 'ankara')
    ek = args.ek_kelime
    if ek is None and not args.yes:
        ek = ask('Ek arama kelimeleri (virgülle)', '')
    ek = ek or ''
    ex = args.exclude
    if ex is None and not args.yes:
        ex = ask('Hariç tutulacaklar (virgülle)', '')
    ex = ex or ''

    cv_path = args.cv or ''
    if not cv_path and not args.yes:
        cv_path = ask('CV dosyası (pdf/docx/txt, boş olabilir)', '')
    cv_text = ''
    if cv_path:
        if not os.path.exists(cv_path):
            print(f'HATA: CV dosyası bulunamadı: {cv_path}')
            sys.exit(2)
        cv_text = extract_text(cv_path)
        print(f'CV okundu: {len(cv_text)} karakter')
        if not cv_text.strip():
            print("UYARI: CV'den metin çıkarılamadı (tarama sayfası olabilir).")

    sid = new_session(site, meslek, sehir, ek, ex, cv_path, cv_text)
    return sid


def print_results(jobs):
    groups = {'uygun': [], 'dusuk': [], 'eslesme-yok': []}
    n = 0
    mapping = {}
    for j in jobs:
        if j['match_state'] == 'hariç':
            continue
        groups.setdefault(j['match_state'], []).append(j)
    for gname, title in (('uygun', 'UYGUN (CV uyumlu)'),
                         ('dusuk', 'DÜŞÜK EŞLEŞME'),
                         ('eslesme-yok', 'EŞLEŞME YOK')):
        items = groups.get(gname, [])
        if not items:
            continue
        print(f'\n=== {title} ({len(items)}) ===')
        for j in items:
            n += 1
            mapping[n] = j['job_id']
            lok = j['location'] or '-'
            skor = f"[skor {j['score']}]" if j['score'] else ''
            once = ' [BAŞVURULDU]' if j['applied'] else ''
            print(f"  {n:>3}. {skor}{once} {j['title']} — {j['company']} — {lok}")
    print()
    return mapping


def choose_ids(mapping, jobs_by_id, args):
    listed = list(mapping.keys())
    total = len(listed)
    if total == 0:
        return set()
    if args.all:
        return set(mapping.values())
    if args.apply_all:
        return set(job_id for job_id in mapping.values() if jobs_by_id[job_id]['match_state'] in ('uygun', 'dusuk'))
    if args.yes:
        return set(job_id for job_id in mapping.values() if jobs_by_id[job_id]['match_state'] == 'uygun')
    default = [i for i in listed if jobs_by_id[mapping[i]]['match_state'] == 'uygun']
    default_txt = ','.join(str(i) for i in default)
    spec = input(f'Hangi ilanlara başvurulacak? (1,3,5-8 / hepsi / boş={default_txt}): ').strip()
    if not spec:
        idx = set(default)
    elif spec.lower() in ('hepsi', 'all', '*', 'tümü', 'tumu'):
        idx = set(listed)
    else:
        idx = parse_numbers(spec, total)
    return {mapping[i] for i in idx}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'web':
        from app import app
        from browser import load_config
        cfg = load_config()
        print(f'Web arayüzü: http://{cfg.get("host", "127.0.0.1")}:{cfg.get("port", 5000)} (Ctrl+C ile durur)')
        app.run(host=cfg.get('host', '127.0.0.1'), port=cfg.get('port', 5000), debug=False)
        return

    ap = argparse.ArgumentParser(description='İş başvuru otomasyonu (CLI)')
    ap.add_argument('--site', '-s', choices=list(ADAPTERS.keys()), help='İlan kaynağı')
    ap.add_argument('--meslek', '-m', help='Meslek / arama kelimesi (zorunlu)')
    ap.add_argument('--sehir', help='Şehir (slug, ör. ankara)')
    ap.add_argument('--ek-kelime', help='Ek arama kelimeleri (virgülle)')
    ap.add_argument('--exclude', help='Hariç tutulacaklar (virgülle)')
    ap.add_argument('--cv', help='CV dosyası yolu (.pdf/.docx/.txt)')
    ap.add_argument('--yes', '-y', action='store_true', help='Soru sorma, varsayılanları kullan')
    ap.add_argument('--apply-all', action='store_true', help='Uygun + düşük eşleşmelerin tümüne başvur')
    ap.add_argument('--all', action='store_true', help='Listedeki tüm ilanlara başvur')
    ap.add_argument('--no-apply', action='store_true', help='Sadece ara, başvurma')
    args = ap.parse_args()

    cfg = load_config()

    if not args.site:
        if args.yes:
            args.site = 'isinolsun'
        else:
            print('İlan kaynağı:')
            args.site = ask_choice('Seçim', [(k, v.label) for k, v in ADAPTERS.items()], 'isinolsun')

    print(f'=== Kaynak: {ADAPTERS[args.site].label} ===')
    sid = build_session(args, cfg)

    def s_status(msg):
        print(f'   ... {msg}')

    print('Arama yapılıyor (tarayıcı açılacak)...')
    run_search(sid, status=s_status)
    s = get_session(sid)
    if s['phase'] == 'hata':
        print(f'HATA: {s["error"]}')
        sys.exit(1)

    jobs = s['jobs']
    print(f'\nTOPLAM {len(jobs)} ilan bulundu.')
    mapping = print_results(jobs)

    if not mapping:
        print('Uygun ilan bulunamadı.')
        return

    if args.no_apply:
        out = _write_export(s)
        print(f'Tikli takip listesi: {out}')
        return

    jobs_by_id = {j['job_id']: j for j in jobs}
    ids = choose_ids(mapping, jobs_by_id, args)
    if not ids:
        print('Seçim boş, başvuru yapılmadı.')
        return
    print(f'\n{len(ids)} ilan için başvuru başlıyor (tarayıcı açılacak)...')

    def a_status(durum, done, total, title):
        if durum == 'islemde':
            print(f'   [{done}/{total}] işleniyor: {title}')
        else:
            label = DURUM_LABEL.get(durum, ('✗ ' if durum.startswith('hata') else '? ') + durum)
            print(f'   [{done}/{total}] {label}: {title}')

    def a_ask(questions):
        print('\n   --- Şirket soruları (cevaplar kaydedilir, sonraki ilanlarda otomatik doldurulur) ---')
        answers = {}
        for label, typ in questions:
            v = input(f'   {label} [{typ}]: ').strip()
            if v:
                answers[label] = v
        return answers

    run_apply(sid, ids, status=a_status, ask=a_ask, bank=load_answers())
    s = get_session(sid)
    if s['phase'] == 'hata':
        print(f'HATA: {s["error"]}')

    n_ok = sum(1 for j in s['jobs'] if j['durum'] == 'basvuru-alindi')
    n_once = sum(1 for j in s['jobs'] if j['durum'] == 'daha-once')
    n_bad = sum(1 for j in s['jobs'] if j['durum'] and j['durum'] not in ('basvuru-alindi', 'daha-once'))
    print(f'\nÖZET: {n_ok} yeni başvuru, {n_once} zaten başvurulmuş, {n_bad} sorunlu.')

    out = _write_export(s)
    print(f'Tikli takip listesi: {out}')


def _write_export(s):
    out = os.path.join(DATA_DIR, f"takip_{s['site']}_{s['sid']}.html")
    with open(out, 'w', encoding='utf-8') as f:
        f.write(build_tick_html(s))
    return out


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nİptal edildi.')
        sys.exit(130)
