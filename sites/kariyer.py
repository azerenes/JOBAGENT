import re
import time as t
from .base import SiteAdapter, Job

CITY_RE = re.compile(r'Ankara|İstanbul|Istanbul|İzmir|Izmir|Bursa|Kocaeli|Eskişehir|Eskisehir|Adana|Antalya|Gaziantep|Konya|Türkiye|Turkiye|Remote|Uzaktan|Hibrit', re.I)


class KariyerAdapter(SiteAdapter):
    name = 'kariyer'
    label = 'Kariyer.net'
    base = 'https://www.kariyer.net'

    def termify(self, s):
        return s

    def _scroll(self, page):
        for _ in range(5):
            try:
                page.mouse.wheel(0, 1400)
            except Exception:
                pass
            t.sleep(1.2)

    def search(self, page, meslek, ek_kelime, sehir, sayfa=2, cv_keywords=None):
        terms = self.search_terms(meslek, ek_kelime, cv_keywords)
        cards = {}
        challenged = False
        for term in terms:
            for cp in range(1, sayfa + 1):
                url = f'{self.base}/is-ilanlari?keywords={term}&cityName={sehir}&cp={cp}'
                try:
                    page.goto(url, timeout=45000, wait_until='domcontentloaded')
                    self._scroll(page)
                    # bot dogrulamasi (px-captcha) tespiti
                    try:
                        if page.evaluate("() => !!document.querySelector('.px-captcha-container,[class*=px-captcha]')"):
                            challenged = True
                            t.sleep(3)
                    except Exception:
                        pass
                    found = page.evaluate('''() => {
                        const out = [];
                        document.querySelectorAll('a[href*="/is-ilani/"]').forEach(a=>{
                            const href = a.getAttribute('href') || '';
                            if (out.some(x=>x.href===href)) return;
                            const lines = (a.innerText||'').split('\\n').map(s=>s.trim()).filter(Boolean);
                            const skip = new Set(['Sponsorlu İlan','Sponsorlu','İş Yerinde','Uzaktan / Remote','Hibrit','Tam zamanlı','Yarı zamanlı','bookmark_border','more_vert','update','schedule','Hızlı Başvuru']);
                            const data = lines.filter(l => !skip.has(l));
                            let applied = lines.some(l => l==='Başvuruldu' || l==='Basvuruldu');
                            const cityRe = /Ankara|İstanbul|Istanbul|İzmir|Izmir|Bursa|Kocaeli|Eskişehir|Eskisehir|Adana|Antalya|Gaziantep|Konya|Türkiye|Turkiye/i;
                            let title='', company='', location='';
                            if (data.length>=3) { title=data[0]; company=data[1]; location=data[2]; }
                            else if (data.length===2) { title=data[0]; company=data[1]; }
                            else { title=data[0]||''; }
                            const loc = data.find(l=>cityRe.test(l)) || location;
                            out.push({href, title, company, location: loc, applied});
                        });
                        return out;
                    }''')
                    for c in found:
                        m = re.search(r'-(\d+)$', c['href'])
                        jid = m.group(1) if m else c['href']
                        if not jid:
                            continue
                        if jid in cards:
                            cards[jid].applied = cards[jid].applied or c['applied']
                            continue
                        cards[jid] = Job(
                            title=c['title'], company=c['company'], location=c['location'],
                            url=self.base + c['href'] if c['href'].startswith('/') else c['href'],
                            site='kariyer', job_id=jid, applied=c['applied'])
                except Exception:
                    pass
                t.sleep(1.0)
        if not cards and challenged:
            raise RuntimeError(
                'Kariyer.net bot doğrulaması istedi (px-captcha). '
                'Lütfen kariyer.net sitesine kendi tarayıcınızla giriş yapıp doğrulamayı geçin, '
                'sonra bu aramayı tekrar çalıştırın.')
        return list(cards.values())

    def login_url(self):
        return f'{self.base}/giris'

    def is_logged_in(self, page):
        try:
            page.goto(self.base, timeout=40000, wait_until='domcontentloaded')
            t.sleep(1.5)
            r = page.evaluate('''() => [...document.querySelectorAll('a')].some(a=>{
                const h=(a.getAttribute('href')||'').toLowerCase();
                return h.includes('/hesabim') || h.includes('/gelen-kutusu');
            })''')
            return bool(r)
        except Exception:
            return False

    def apply(self, page, job, ask=None, bank=None):
        try:
            page.goto(job.url, timeout=45000, wait_until='domcontentloaded')
            t.sleep(3)
            st = page.evaluate('''() => {
                const txt = (document.body.innerText||'');
                const applied = /Başvuruldu|Basvuruldu/.test(txt);
                const btn = [...document.querySelectorAll('button,a,span')].find(b=>{
                    const tx=(b.innerText||'').trim().replace(/\\s+/g,' ');
                    return (tx==='Hemen Başvur' || tx==='Hemen Basvur') && b.getBoundingClientRect().height>0;
                });
                const login = /giriş yap|giris yap|üye girişi/i.test(txt);
                return {applied, hasBtn: !!btn, login};
            }''')
            if st['login']:
                return 'giris-gerekli'
            if st['applied']:
                return 'daha-once'
            if not st['hasBtn']:
                return 'belirsiz'
            page.evaluate('''() => {
                const btn=[...document.querySelectorAll('button,a,span')].find(b=>{
                    const tx=(b.innerText||'').trim().replace(/\\s+/g,' ');
                    return (tx==='Hemen Başvur'||tx==='Hemen Basvur') && b.getBoundingClientRect().height>0;
                });
                if(btn) btn.click();
            }''')
            t.sleep(3)
            # modal cikarsa sorulari doldur + onayla
            modal = page.evaluate('''() => {
                const vis=[...document.querySelectorAll('[class*="modal"],[role="dialog"]')].filter(d=>d.getBoundingClientRect().height>100 && (d.innerText||'')!=='');
                const btn=[...document.querySelectorAll('button,a')].find(b=>{
                    const tx=(b.innerText||'').trim().toLowerCase();
                    const r=b.getBoundingClientRect();
                    return r.width>0&&r.height>0&&(/başvur|basvur|onayla|gönder|gonder/.test(tx))&&tx.length<40;
                });
                return {hasModal: vis.length>0, hasConfirm: !!btn};
            }''')
            if modal['hasModal']:
                self.fill_questions(page, bank or {}, ask)
                t.sleep(0.5)
            if modal['hasModal'] and modal['hasConfirm']:
                page.evaluate('''() => {
                    const btn=[...document.querySelectorAll('button,a')].find(b=>{
                        const tx=(b.innerText||'').trim().toLowerCase();
                        const r=b.getBoundingClientRect();
                        return r.width>0&&r.height>0&&(/başvur|basvur|onayla|gönder|gonder/.test(tx))&&tx.length<40;
                    });
                    if(btn) btn.click();
                }''')
                t.sleep(2)
            # dogrula
            ok = page.evaluate('''() => {
                const txt=(document.body.innerText||'');
                return /Başvuruldu|Basvuruldu|başvurunuz alındı|basvurunuz alindi/i.test(txt);
            }''')
            if ok:
                return 'basvuru-alindi'
            # sayfa degisti mi (kariyer basvuru sonrasi listeye doner)
            if 'is-ilanlari' in page.url and job.job_id not in page.url:
                return 'basvuru-alindi'
            return 'hata:dogrulanamadi'
        except Exception as e:
            return 'hata:' + type(e).__name__
