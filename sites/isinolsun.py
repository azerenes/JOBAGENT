import re
import time as t
from .base import SiteAdapter, Job

JS_STATE = '''() => {
    const vis = (e) => { const r=e.getBoundingClientRect(); const s=getComputedStyle(e); return r.width>0 && r.height>0 && s.display!=='none' && s.visibility!=='hidden'; };
    const txt = (document.body.innerText||'');
    const els = [...document.querySelectorAll('a,button,span')];
    const doneV = els.some(e => (e.innerText||'').trim()==='Başvurdun' && vis(e));
    const btnV  = els.some(e => (e.innerText||'').trim()==='Başvur' && vis(e));
    return {doneV, btnV, chal: /Basılı Tut|doğrulama/i.test(txt)};
}'''


class IsinolsunAdapter(SiteAdapter):
    name = 'isinolsun'
    label = 'Isinolsun.com'
    base = 'https://isinolsun.com'

    def search(self, page, meslek, ek_kelime, sehir, sayfa=2, cv_keywords=None):
        terms = self.search_terms(meslek, ek_kelime, cv_keywords)
        cards = {}
        for term in terms:
            for sy in range(1, sayfa + 1):
                url = f'{self.base}/is-ilanlari/{sehir}-{term}?page={sy}&pn={sy}'
                try:
                    page.goto(url, timeout=45000, wait_until='domcontentloaded')
                    t.sleep(2.2)
                    found = page.evaluate('''() => {
                        const out = [];
                        document.querySelectorAll('a[data-test="job-list-link"]').forEach(a=>{
                            const href = a.getAttribute('href') || '';
                            if (out.some(x=>x.href===href)) return;
                            const h = a.querySelector('h3[data-test="job-list-title"]');
                            const p = a.querySelector('p[data-test="job-list-text"]');
                            const c = a.querySelector('em[data-test="job-list-city"]');
                            let company = '';
                            if (p) {
                                const cl = p.cloneNode(true);
                                cl.querySelectorAll('em').forEach(e=>e.remove());
                                company = (cl.innerText||'').trim();
                            }
                            out.push({href, title: h?h.innerText.trim():'', company,
                                      location: c?(c.innerText||'').trim():''});
                        });
                        return out;
                    }''')
                    for c in found:
                        m = re.search(r'-0ioj([A-Fa-f0-9]+)$', c['href'])
                        jid = m.group(1) if m else c['href']
                        if not jid:
                            continue
                        cards[jid] = Job(
                            title=c['title'], company=c['company'], location=c['location'],
                            url=self.base + c['href'] if c['href'].startswith('/') else c['href'],
                            site='isinolsun', job_id=jid)
                    if len(found) < 42:
                        break
                except Exception:
                    pass
                t.sleep(0.7)
        return list(cards.values())

    def login_url(self):
        return f'{self.base}/giris'

    def is_logged_in(self, page):
        try:
            page.goto(self.base, timeout=40000, wait_until='domcontentloaded')
            t.sleep(1.5)
            r = page.evaluate('''() => [...document.querySelectorAll('a')].some(a=>{
                const h=(a.getAttribute('href')||'').toLowerCase();
                const tx=(a.innerText||'').toLowerCase();
                return h.includes('/profil') || tx.includes('profilim') || tx.includes('çık');
            })''')
            return bool(r)
        except Exception:
            return False

    def apply(self, page, job, ask=None, bank=None):
        try:
            page.goto(job.url, timeout=45000, wait_until='domcontentloaded')
            st = None
            for _ in range(12):
                t.sleep(1.5)
                st = page.evaluate(JS_STATE)
                if st['doneV'] or st['btnV'] or st['chal']:
                    break
            if st is None:
                return 'belirsiz'
            if st['chal'] and not st['btnV']:
                return 'challenge'
            if st['doneV']:
                return 'daha-once'
            if not st['btnV']:
                return 'belirsiz'
            clicked = page.evaluate('''() => {
                const vis = (e) => { const r=e.getBoundingClientRect(); const s=getComputedStyle(e);
                    return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'; };
                const el = [...document.querySelectorAll('a,button,span')].find(e =>
                    (e.innerText||'').trim()==='Başvur' && vis(e));
                if (el) { el.click(); return true; }
                return false;
            }''')
            if not clicked:
                return 'hata:buton-yok'
            t.sleep(1.5)
            # sirket sorulari varsa doldur
            self.fill_questions(page, bank or {}, ask)
            t.sleep(0.5)
            # form gonderme butonu belirirse tikla
            page.evaluate('''() => {
                const vis = (e) => { const r=e.getBoundingClientRect(); const s=getComputedStyle(e);
                    return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'; };
                const b = [...document.querySelectorAll('button, input[type=submit]')].find(e =>
                    /başvuruyu tamamla|başvurunu gönder|gönder|gonder|onayla|devam et|tamamla/i.test((e.innerText||e.value||'').trim()) && vis(e));
                if (b) { b.click(); }
            }''')
            st2 = None
            for _ in range(10):
                st2 = page.evaluate(JS_STATE)
                if st2['doneV'] or st2['chal']:
                    break
                t.sleep(1)
            if st2 and st2['doneV']:
                return 'basvuru-alindi'
            if st2 and st2['chal']:
                return 'challenge'
            return 'hata:yeni-baslik'
        except Exception as e:
            return 'hata:' + type(e).__name__
