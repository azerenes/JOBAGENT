import json
import os
import sys
import threading
import time as t

from playwright.sync_api import sync_playwright


def _app_dir():
    """Kalici verinin konumu: paketlenmis (exe) ise exe'nin yani, yoksa kod dizini."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = _app_dir()
BUNDLE_DIR = getattr(sys, '_MEIPASS', APP_DIR)   # paket icindeki kaynaklar (templates/static)
DATA_DIR = os.path.join(APP_DIR, 'data')
PROFILE_DIR = os.path.join(DATA_DIR, 'profiles')
CONFIG_PATH = os.path.join(APP_DIR, 'config.json')

_lock = threading.Lock()


def default_config():
    return {
        "browser": {
            "channel": "",          # chrome | chromium | msedge | opera | "" (otomatik)
            "executable": "",       # opsiyonel ozel tarayici yolu (Ornek: Opera)
            "profile": ""           # opsiyonel ortak profil yolu (bos = site basina ayri profil)
        },
        "city": "ankara",
        "max_pages": 2,
        "host": "127.0.0.1",
        "port": 5000
    }


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            base = default_config()
            base.update(json.load(open(CONFIG_PATH, encoding='utf-8')))
            return base
        except Exception:
            pass
    return default_config()


def save_config(cfg):
    json.dump(cfg, open(CONFIG_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def _find_chrome():
    envs = [os.environ.get('PROGRAMFILES', r'C:\Program Files'),
            os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)'),
            os.environ.get('LOCALAPPDATA', '')]
    cands = []
    for e in envs:
        cands += [os.path.join(e, r'Google\Chrome\Application\chrome.exe'),
                  os.path.join(e, r'Microsoft\Edge\Application\msedge.exe')]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


class BrowserManager:
    """Playwright ornekleri ve site basina kalici profil/oturum yonetir."""

    def __init__(self, config=None):
        self.config = config or load_config()
        self._pw = None
        self._contexts = {}
        self._lock = threading.Lock()

    # ---- lifecycle ----
    def _start(self):
        if self._pw is None:
            self._pw = sync_playwright().start()

    def stop(self):
        with self._lock:
            for ctx in self._contexts.values():
                try:
                    ctx.close()
                except Exception:
                    pass
            self._contexts.clear()
            if self._pw:
                try:
                    self._pw.stop()
                except Exception:
                    pass
                self._pw = None

    # ---- launch args ----
    def _launch_kwargs(self, site):
        br = self.config.get('browser', {})
        channel = br.get('channel') or ''
        exe = br.get('executable') or ''
        profile = br.get('profile') or ''
        if not channel and not exe:
            chrome = _find_chrome()
            if chrome and chrome.endswith('msedge.exe'):
                channel = 'msedge'
            elif chrome:
                channel = 'chrome'
            else:
                if getattr(sys, 'frozen', False):
                    raise RuntimeError('JOBAGENT için Google Chrome veya Microsoft Edge kurulu olmalıdır.')
                channel = 'chromium'
        os.makedirs(PROFILE_DIR, exist_ok=True)
        user_dir = profile or os.path.join(PROFILE_DIR, site)
        kwargs = dict(user_data_dir=user_dir,
                      headless=False,
                      locale='tr-TR',
                      viewport={'width': 1600, 'height': 1000},
                      ignore_default_args=['--enable-automation'],
                      args=['--disable-blink-features=AutomationControlled'])
        if exe:
            kwargs['executable_path'] = exe
        elif channel:
            kwargs['channel'] = channel
        return kwargs

    # ---- context edinme ----
    def context(self, site):
        with self._lock:
            if site in self._contexts:
                return self._contexts[site]
            self._start()
            kwargs = self._launch_kwargs(site)
            ctx = self._pw.chromium.launch_persistent_context(**kwargs)
            ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            self._contexts[site] = ctx
            return ctx

    def fresh_page(self, site):
        ctx = self.context(site)
        return ctx.new_page()

    def ensure_closed(self):
        self.stop()
