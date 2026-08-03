import time as t
from dataclasses import dataclass, field, asdict


@dataclass
class Job:
    title: str = ''
    company: str = ''
    location: str = ''
    url: str = ''
    site: str = ''
    job_id: str = ''
    applied: bool = False
    desc: str = ''
    matched: list = field(default_factory=list)
    score: int = 0
    match_state: str = 'eslesme-yok'   # uygun | dusuk | eslesme-yok
    durum: str = ''                    # basvuru-alindi | daha-once | hata | belirsiz | giris-gerekli | challenge | ''

    def to_dict(self):
        return asdict(self)


class SiteAdapter:
    """Soyut arayuz: her site bir alt sinifla uygular."""

    name = 'site'
    label = 'Site'

    # ---- arama ----
    def termify(self, s):
        """Siteye uygun arama terimine cevirir (eleman/isinolsun slug, kariyer duz)."""
        return s.replace(' ', '-')

    def search_terms(self, meslek, ek_kelime, cv_keywords=None):
        """Meslek, ek kelimeler ve CV anahtar kelimelerinden arama terimleri uretir."""
        terms = []

        def add(x):
            x = self.normalize(x).strip()
            if x and x not in terms:
                terms.append(self.termify(x))

        m = self.normalize(meslek).strip()
        if m:
            add(m)
            for tok in m.split():
                if len(tok) >= 3 and tok not in ('teknisyeni', 'teknikeri', 'elemani', 'ustasi',
                                                  'kalfasi', 'sorumlusu', 'operat'):
                    add(tok)
        for x in (ek_kelime or '').split(','):
            add(x)
        for kw in (cv_keywords or []):
            add(kw)
        return terms[:15]

    def search(self, page, meslek, ek_kelime, sehir, sayfa=2, cv_keywords=None):
        """Arama yapar ve Job listesi dondurur."""
        raise NotImplementedError

    # ---- basvuru ----
    def apply(self, page, job, ask=None, bank=None):
        """Tek ilana basvuru yapar. Durum kodu dondurur.
        ask: (label,type) listesini alip {label: cevap} donduren geri cagirma (ilk sorulu ilanda sorar).
        bank: {normalize(soru): cevap} sablonu — bilinen sorular otomatik doldurulur."""
        raise NotImplementedError

    # ---- sirket sorulari ----
    JS_Q = r'''
const JOBAGENT_NORM = s => (s||'').toLowerCase()
    .replace(/İ/g,'i').replace(/ı/g,'i').replace(/I/g,'i')
    .replace(/Ğ/g,'g').replace(/ğ/g,'g')
    .replace(/Ş/g,'s').replace(/ş/g,'s')
    .replace(/Ü/g,'u').replace(/ü/g,'u')
    .replace(/Ö/g,'o').replace(/ö/g,'o')
    .replace(/Ç/g,'c').replace(/ç/g,'c')
    .replace(/[^a-z0-9\s]/g,' ').replace(/\s+/g,' ').trim();
const JOBAGENT_LABEL = el => {
    let label = '';
    if (el.id) { const lb = document.querySelector('label[for="'+el.id+'"]'); if (lb) label = lb.innerText.trim(); }
    if (!label) {
        const holder = el.closest('div,li,fieldset');
        if (holder) { const L = holder.innerText.split('\n').map(s=>s.trim()).filter(Boolean); if (L.length) label = L[0]; }
    }
    if (!label) label = el.getAttribute('aria-label') || el.placeholder || el.name || '';
    return (label||'').trim();
};
const JOBAGENT_FIELDS = () => {
    const out = [];
    document.querySelectorAll('textarea, select, input').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width===0 || r.height===0) return;
        if (el.type==='hidden'||el.type==='checkbox'||el.type==='radio'||el.type==='file'||el.type==='password') return;
        if (el.disabled || el.readOnly) return;
        const label = JOBAGENT_LABEL(el);
        const norm = JOBAGENT_NORM(label);
        if (!norm) return;
        if (/ad\s?soyad|adın|adini|soyad|isim|soyisim|e-?posta|e-?mail|email|telefon|cep|gsm|tc\s?kimlik|kimlik|doğum|dogum|cinsiyet|gender|resim|foto|adres|linkedin|github|website|password|şifre|sifre|kullanıcı|kullanici|vize|askerlik|ehliyet/.test(norm)) return;
        if (el.autocomplete) return;
        const isSelect = el.tagName === 'SELECT';
        const empty = isSelect ? (el.selectedIndex <= 0) : !(el.value && el.value.trim());
        if (!empty) return;
        out.push({norm, label, type: el.tagName==='TEXTAREA' ? 'textarea' : isSelect ? 'select' : (el.type||'text')});
    });
    return out;
};
'''

    def detect_questions(self, page):
        """Sayfadaki bos, soru niteligindeki form alanlarini dondurur: [{norm,label,type}]."""
        return page.evaluate('''() => { %s return JOBAGENT_FIELDS(); }''' % self.JS_Q)

    def fill_questions(self, page, bank, ask=None):
        """Bos sorulari doldurur. Bankadaki cevaplari kullanir; bilinmeyenleri ask ile kullaniciya sorar.
        Doldurulan alan sayisini dondurur. Bank 'norm -> cevap' sablonudur (yerinde guncellenir)."""
        need = self.detect_questions(page)
        if not need:
            return 0
        unknowns = [q for q in need if q['norm'] not in bank]
        if unknowns and ask:
            try:
                answers = ask([(q['label'], q['type']) for q in unknowns]) or {}
            except Exception:
                answers = {}
            for q in unknowns:
                ans = str(answers.get(q['label'], '') or '').strip()
                if ans:
                    bank[q['norm']] = ans
        if not bank:
            return 0
        return page.evaluate('''(bank) => {
            %s
            let n = 0;
            document.querySelectorAll('textarea, select, input').forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.width===0 || r.height===0) return;
                if (el.disabled || el.readOnly) return;
                if (el.type==='hidden'||el.type==='checkbox'||el.type==='radio'||el.type==='file'||el.type==='password') return;
                const label = JOBAGENT_LABEL(el);
                const norm = JOBAGENT_NORM(label);
                if (!norm) return;
                const ans = bank[norm];
                if (!ans) return;
                const isSelect = el.tagName === 'SELECT';
                const empty = isSelect ? (el.selectedIndex <= 0) : !(el.value && el.value.trim());
                if (!empty) return;
                if (isSelect) {
                    const low = ans.toLowerCase();
                    let matched = null;
                    for (const opt of el.options) {
                        const tx = opt.text.trim().toLowerCase();
                        if (tx === low || (tx.includes(low) && low.length >= 3)) { matched = opt; break; }
                    }
                    if (!matched) {
                        for (const opt of el.options) {
                            const tx = opt.text.trim();
                            if (tx.length > 2 && !/seçiniz|seciniz|choose|select|lutfen/i.test(tx)) { matched = opt; break; }
                        }
                    }
                    if (matched) { el.value = matched.value; el.dispatchEvent(new Event('change', {bubbles:true})); n++; }
                } else {
                    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                    if (setter) setter.call(el, ans); else el.value = ans;
                    el.dispatchEvent(new Event('input', {bubbles:true}));
                    el.dispatchEvent(new Event('change', {bubbles:true}));
                    n++;
                }
            });
            return n;
        }''' % self.JS_Q, bank)

    # ---- giris ----
    def login_url(self):
        return ''

    def is_logged_in(self, page):
        """Giris yapilmis mi? Evet/Hayir."""
        return False

    def ensure_login(self, page, status_fn):
        """Giris yoksa giris ekranini acar; kullanici giris yapana kadar bekler."""
        while not self.is_logged_in(page):
            status_fn('waiting_login', f"Tarayicida giris ekrani acildi ({self.label}). Lutfen giris yapin.")
            try:
                page.goto(self.login_url(), timeout=45000, wait_until='domcontentloaded')
            except Exception:
                pass
            for _ in range(20):   # 40 sn bekle
                t.sleep(2)
                if self.is_logged_in(page):
                    return True
        return True

    def normalize(self, s):
        tr = str.maketrans('İışğüöçİIŞĞÜÖÇ', 'iisguociisguoc')
        return s.translate(tr).lower()
