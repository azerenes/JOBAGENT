def build_tick_html(s):
    jobs = s['jobs']
    n_ok = sum(1 for j in jobs if j['durum'] == 'basvuru-alindi')
    n_once = sum(1 for j in jobs if j['durum'] == 'daha-once')
    n_kalan = len(jobs) - n_ok - n_once
    trs = []
    for i, j in enumerate(jobs, 1):
        d = j['durum']
        if d == 'basvuru-alindi':
            tik, cls, label = '✓', 'ok', 'Başvuruldu'
        elif d == 'daha-once':
            tik, cls, label = '✓', 'once', 'Daha önce başvuruldu'
        elif d:
            tik, cls, label = '✗', 'hata', d
        else:
            tik, cls, label = '—', 'yok', 'Başvurulmadı'
        trs.append(f"""<tr class="{cls}">
  <td class="num">{i}</td><td class="tik">{tik}</td>
  <td class="baslik"><a href="{j['url']}" target="_blank">{j['title']}</a></td>
  <td class="sirket">{j['company']}</td>
  <td class="yer">{j['location']}</td>
  <td class="durum">{label}</td></tr>""")
    title = f"{s['meslek']} — {s['site']} Başvuru Takip Listesi"
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<title>{title}</title><style>
body{{font-family:'Segoe UI',Tahoma,Arial,sans-serif;margin:24px;background:#f4f6f9;color:#222;}}
h1{{font-size:22px;margin:0 0 6px;}}.ozet{{display:flex;gap:14px;margin:12px 0 18px;flex-wrap:wrap;}}
.kutu{{padding:8px 16px;border-radius:8px;font-weight:600;font-size:14px;}}
.k-ok{{background:#e4f5e6;color:#1a7a2e;border:1px solid #b8e3bd;}}
.k-once{{background:#eef5ff;color:#2b5fa8;border:1px solid #c3d8f5;}}
.k-kalan{{background:#fff2e0;color:#b06a00;border:1px solid #f2d5a8;}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);}}
th{{text-align:left;background:#eef1f5;padding:10px 12px;font-size:13px;text-transform:uppercase;color:#555;border-bottom:2px solid #dde3ea;}}
td{{padding:9px 12px;border-bottom:1px solid #eef1f4;font-size:14px;vertical-align:middle;}}
tr.ok td.tik{{color:#1a9e37;font-weight:700;font-size:18px;}}
tr.once td.tik{{color:#3a7bd5;font-weight:700;font-size:18px;}}
tr.yok td.tik,tr.hata td.tik{{color:#c8ccd2;font-weight:700;font-size:18px;}}
tr.once td.durum{{color:#2b5fa8;}}tr.hata td.durum{{color:#b06a00;}}
td.num{{color:#8a94a3;font-size:12px;width:32px;}}td.baslik a{{color:#14407f;text-decoration:none;font-weight:600;}}
td.durum{{font-weight:600;}}</style></head><body>
<h1>{title}</h1>
<div class="ozet">
<div class="kutu k-ok">✓ Başvuruldu: {n_ok}</div>
<div class="kutu k-once">✓ Daha önce başvuruldu: {n_once}</div>
<div class="kutu k-kalan">✗ Kalan: {n_kalan}</div>
</div>
<table><thead><tr><th>#</th><th></th><th>İlan</th><th>Firma</th><th>Yer</th><th>Durum</th></tr></thead>
<tbody>{''.join(trs)}</tbody></table></body></html>"""
