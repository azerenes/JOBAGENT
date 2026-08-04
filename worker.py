import json
import os
import threading
import time
import uuid

from browser import BrowserManager, DATA_DIR
from cv_reader import normalize_turkish
from matcher import build_keywords, parse_exclude, score_job
from sites import get_adapter
from sites.base import Job

_sess_lock = threading.Lock()
SESSIONS = {}
SESSIONS_DIR = os.path.join(DATA_DIR, 'sessions')
ANSWERS_PATH = os.path.join(DATA_DIR, 'answers.json')


def load_answers():
    """Kaydedilmis sirket soru cevaplari: {normalize(soru): cevap}."""
    try:
        with open(ANSWERS_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_answers(bank):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(ANSWERS_PATH, 'w', encoding='utf-8') as f:
            json.dump(bank, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _path(sid):
    return os.path.join(SESSIONS_DIR, f'{sid}.json')


def _save(sid):
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    s = SESSIONS.get(sid)
    if s:
        with open(_path(sid), 'w', encoding='utf-8') as f:
            json.dump(s, f, ensure_ascii=False, indent=1)


def _load(sid):
    if sid in SESSIONS:
        return SESSIONS[sid]
    if os.path.exists(_path(sid)):
        try:
            SESSIONS[sid] = json.load(open(_path(sid), encoding='utf-8'))
            return SESSIONS[sid]
        except Exception:
            pass
    return None


def _update(sid, fn):
    with _sess_lock:
        s = _load(sid)
        if s:
            fn(s)
            _save(sid)
        return s


def new_session(site, meslek, sehir, ek_kelime, exclude, cv_path, cv_text):
    sid = uuid.uuid4().hex[:10]
    SESSIONS[sid] = {
        'sid': sid,
        'site': site,
        'meslek': meslek,
        'sehir': sehir,
        'ek_kelime': ek_kelime,
        'exclude': exclude,
        'cv_path': cv_path,
        'cv_text': cv_text[:3000],
        'keywords': build_keywords(cv_text, meslek, ek_kelime),
        'exclude_list': parse_exclude(exclude),
        'jobs': [],
        'phase': 'hazir',
        'progress': {'done': 0, 'total': 0, 'msg': ''},
        'log': [],
        'error': '',
    }
    _save(sid)
    return sid


def get_session(sid):
    return _load(sid)


# ---------- ARAMA ----------
def run_search(sid, status=None):
    """Aramayi senkron calistirir. status(msg) opsiyonel geri arama."""
    s = _update(sid, lambda x: x.update({'phase': 'arama', 'progress': {'done': 0, 'total': 0, 'msg': 'Arama başlatıldı...'}}))
    browser = BrowserManager()
    try:
        site = s['site']
        adapter = get_adapter(site)
        if adapter is None:
            raise RuntimeError(f'Bilinmeyen site: {site}')
        page = browser.fresh_page(site)
        if status:
            status(f'"{adapter.label}" üzerinde arama yapılıyor...')
        jobs = adapter.search(page, s['meslek'], s['ek_kelime'], s['sehir'], sayfa=2,
                              cv_keywords=s['keywords'])
        city = s['sehir'].lower()
        kept = []
        seen = set()
        for j in jobs:
            loc = (j.location or '').lower()
            if loc and city not in loc and 'türkiye' not in loc and 'turkiye' not in loc:
                continue
            score_job(j, s['keywords'], s['exclude_list'], s['meslek'])
            if j.match_state == 'eslesme-yok':
                continue
            # ayni ilan kopya olarak gelirse tekle (url veya baslik+firma)
            key = (j.site, j.url or '')
            key2 = (j.site, normalize_turkish(j.title or ''), normalize_turkish(j.company or ''))
            if key in seen or key2 in seen:
                continue
            seen.add(key)
            seen.add(key2)
            kept.append(j)
        kept.sort(key=lambda j: (j.match_state == 'uygun', j.score), reverse=True)
        data = [j.to_dict() for j in kept]
        _update(sid, lambda x: x.update({'jobs': data, 'phase': 'sonuc',
                                         'progress': {'done': len(data), 'total': len(data), 'msg': f'{len(data)} ilan bulundu'}}))
        return get_session(sid)
    except Exception as e:
        _update(sid, lambda x: x.update({'phase': 'hata', 'error': str(e)}))
        if status:
            status(f'HATA: {e}')
        raise
    finally:
        browser.stop()


def start_search(sid):
    threading.Thread(target=run_search, args=(sid, None), daemon=True).start()


def _set_job_durum(sid, job_id, durum, done, total, title):
    def fn(x):
        for item in x['jobs']:
            if item['job_id'] == job_id:
                item['durum'] = durum
                break
        x['progress'].update({'done': done, 'total': total, 'msg': f'{title} -> {durum}'})
    _update(sid, fn)


# ---------- BASVURU ----------
def run_apply(sid, selected_ids, status=None, ask=None, bank=None):
    """Basvurulari senkron calistirir. status(durum, done, total, title) opsiyonel.
    ask: sorulari sorup cevap donduren geri cagirma; bank: soru->cevap sablonu (yerinde guncellenir)."""
    s = _load(sid)
    if not s:
        raise RuntimeError('Oturum bulunamadı')
    bank = bank if bank is not None else load_answers()
    jobs = [Job(**j) for j in s['jobs'] if j['job_id'] in selected_ids]
    total = len(jobs)
    if total == 0:
        _update(sid, lambda x: x.update({'phase': 'bitti', 'progress': {'done': 0, 'total': 0, 'msg': 'Seçim boş'}}))
        return s
    _update(sid, lambda x: x.update({'phase': 'basvuru',
                                     'progress': {'done': 0, 'total': total, 'msg': 'Başvurular başlatıldı...'}}))
    browser = BrowserManager()
    try:
        site = s['site']
        adapter = get_adapter(site)
        page = browser.fresh_page(site)
        # giris kontrolu
        if not adapter.is_logged_in(page):
            _update(sid, lambda x: x.update({'progress': {'done': 0, 'total': total,
                                                          'msg': f"{adapter.label}: tarayıcıda giriş ekranı açıldı. Lütfen giriş yapın, otomatik devam edilecek."}}))
            if status:
                status('giris-gerekli', 0, total, f'{adapter.label}: tarayıcıda giriş ekranı açıldı. Lütfen giriş yapın (otomatik devam edecek).')
            adapter.ensure_login(page, lambda k, m: _update(sid, lambda x: x.update({'progress': {'done': 0, 'total': total, 'msg': m}})))
        done = 0
        for j in jobs:
            if status:
                status('islemde', done, total, j.title)
            try:
                durum = adapter.apply(page, j, ask=ask, bank=bank)
            except Exception as e:
                durum = 'hata:' + type(e).__name__
            done += 1
            _set_job_durum(sid, j.job_id, durum, done, total, j.title)
            if status:
                status(durum, done, total, j.title)
            time.sleep(1.2)
        save_answers(bank)
        _update(sid, lambda x: x.update({'phase': 'bitti',
                                         'progress': {'done': done, 'total': total, 'msg': 'Başvurular tamamlandı'}}))
        return get_session(sid)
    except Exception as e:
        _update(sid, lambda x: x.update({'phase': 'hata', 'error': str(e)}))
        raise
    finally:
        browser.stop()


def start_apply(sid, selected_ids):
    threading.Thread(target=run_apply, args=(sid, selected_ids, None, None, load_answers()), daemon=True).start()
