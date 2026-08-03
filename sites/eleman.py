import re
import time as t
from .base import SiteAdapter, Job


class ElemanAdapter(SiteAdapter):
    name = 'eleman'
    label = 'Eleman.net'
    base = 'https://www.eleman.net'

    def search(self, page, meslek, ek_kelime, sehir, sayfa=2, cv_keywords=None):
        terms = self.search_terms(meslek, ek_kelime, cv_keywords)
        cards = {}
        for term in terms:
            for sy in range(1, sayfa + 1):
                url = f'{self.base}/is-ilanlari/{sehir}/{term}?sy={sy}'
                try:
                    page.goto(url, timeout=45000, wait_until='domcontentloaded')
                    t.sleep(2.2)
                    found = page.evaluate('''() => {
                        const out = [];
                        document.querySelectorAll('a[href*="/is-ilani/"]').forEach(a=>{
                            const href = a.getAttribute('href') || '';
                            if (out.some(x=>x.href===href)) return;
                            const lines = (a.innerText||'').split('\\n').map(s=>s.trim()).filter(Boolean);
                            let title = '';
                            const h = a.querySelector('h1,h2,h3,h4,h5');
                            if (h) title = h.innerText.trim();
                            if (!title) title = lines[0] || '';
                            let company = lines[1] || '';
                            const cityRe = /Ankara|İstanbul|Istanbul|İzmir|Izmir|Bursa|Kocaeli|Eskişehir|Eskisehir|Adana|Antalya|Gaziantep|Konya|Türkiye|Turkiye|Tümü/i;
                            const loc = lines.find(l => cityRe.test(l)) || '';
                            out.push({href, title, company, location: loc});
                        });
                        return out;
                    }''')
                    for c in found:
                        mid = re.search(r'-i(\d+)$', c['href'])
                        c['job_id'] = mid.group(1) if mid else c['href']
                        if not c['job_id']:
                            continue
                        cards[c['job_id']] = Job(
                            title=c['title'], company=c['company'], location=c['location'],
                            url=self.base + c['href'] if c['href'].startswith('/') else c['href'],
                            site='eleman', job_id=c['job_id'])
                    if len(found) < 42:
                        break
                except Exception:
                    pass
                t.sleep(0.7)
        return list(cards.values())

    def login_url(self):
        return f'{self.base}/aday_giris.php'

    def is_logged_in(self, page):
        try:
            page.goto(f'{self.base}/aday/', timeout=40000, wait_until='domcontentloaded')
            t.sleep(1.5)
            url = page.url.lower()
            if 'giris' in url or 'login' in url:
                return False
            txt = (page.evaluate('() => document.body.innerText || ""') or '')
            return ('çık' in txt.lower() or 'profilim' in txt.lower())
        except Exception:
            return False

    def apply(self, page, job, ask=None, bank=None):
        u = f'{self.base}/aday/basvuru_yap.php?ilan_id={job.job_id}'
        try:
            page.goto(u, timeout=45000, wait_until='domcontentloaded')
            t.sleep(2.5)
            st = page.evaluate('''() => {
                const txt = (document.body.innerText||'');
                const applied = /daha\\s*önce\\s*başvurmuşsunuz|daha\\s*once\\s*basvurmusunuz/i.test(txt);
                const chk = [...document.querySelectorAll('input[type=checkbox]')].filter(c=>{
                    const r=c.getBoundingClientRect(); return r.width>0&&r.height>0;
                });
                const subs = [...document.querySelectorAll('input[type=submit], button[type=submit]')].filter(b=>{
                    const r=b.getBoundingClientRect(); return r.width>0&&r.height>0;
                });
                const login = /giriş yap|giris yap|üye girişi/i.test(txt);
                return {applied, chk: chk.length, subs: subs.length, login};
            }''')
            if st['login']:
                return 'giris-gerekli'
            if st['applied']:
                return 'daha-once'
            if st['chk'] == 0 or st['subs'] == 0:
                return 'hata:form-bulunamadi'
            self.fill_questions(page, bank or {}, ask)
            page.evaluate('''() => { const c=document.querySelector('input[type=checkbox]'); if(c && !c.checked) c.click(); }''')
            t.sleep(0.5)
            page.evaluate('''() => { const b=document.querySelector('input[type=submit], button[type=submit]'); if(b) b.click(); }''')
            t.sleep(2.5)
            st2 = page.evaluate('''() => /daha\\s*önce\\s*başvurmuşsunuz|başvurunuz\\s*alındı|başvurunuz\\s*alin|başarıyla\\s*başvur|basariyla\\s*basvur/i.test(document.body.innerText||"")''')
            return 'basvuru-alindi' if st2 else 'hata:dogrulanamadi'
        except Exception as e:
            return 'hata:' + type(e).__name__
