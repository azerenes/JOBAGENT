import os
import uuid

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

from browser import BUNDLE_DIR, DATA_DIR, load_config, save_config
from cv_reader import extract_text
from export import build_tick_html
from worker import get_session, new_session, start_apply, start_search
from sites import ADAPTERS

UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__,
            template_folder=os.path.join(BUNDLE_DIR, 'templates'),
            static_folder=os.path.join(BUNDLE_DIR, 'static'))


@app.route('/')
def index():
    cfg = load_config()
    return render_template('setup.html', cfg=cfg, sites=[(k, v.label) for k, v in ADAPTERS.items()])


@app.route('/search', methods=['POST'])
def search():
    cfg = load_config()
    site = request.form.get('site', 'isinolsun')
    meslek = (request.form.get('meslek') or '').strip()
    sehir = (request.form.get('sehir') or '').strip() or cfg.get('city', 'ankara')
    ek_kelime = (request.form.get('ek_kelime') or '').strip()
    exclude = (request.form.get('exclude') or '').strip()

    cv_path = ''
    cv_text = ''
    f = request.files.get('cv')
    if f and f.filename:
        name = uuid.uuid4().hex + os.path.splitext(f.filename)[1]
        cv_path = os.path.join(UPLOAD_DIR, name)
        f.save(cv_path)
        cv_text = extract_text(cv_path)
    if not meslek:
        return 'Meslek alanı zorunlu', 400

    sid = new_session(site, meslek, sehir, ek_kelime, exclude, cv_path, cv_text)
    start_search(sid)
    return redirect(url_for('sonuc', sid=sid))


@app.route('/sonuc/<sid>')
def sonuc(sid):
    s = get_session(sid)
    if not s:
        return 'Oturum bulunamadı', 404
    return render_template('results.html', s=s)


@app.route('/basvur/<sid>', methods=['POST'])
def basvur(sid):
    selected = request.form.getlist('job_ids')
    if selected:
        start_apply(sid, set(selected))
    return redirect(url_for('ilerleme', sid=sid))


@app.route('/ilerleme/<sid>')
def ilerleme(sid):
    s = get_session(sid)
    if not s:
        return 'Oturum bulunamadı', 404
    return render_template('progress.html', s=s)


@app.route('/api/durum/<sid>')
def api_durum(sid):
    s = get_session(sid)
    if not s:
        return jsonify({'ok': False}), 404
    return jsonify({'ok': True, 'phase': s['phase'], 'progress': s['progress'],
                    'error': s['error'], 'jobs': s['jobs']})


@app.route('/export/<sid>')
def export(sid):
    s = get_session(sid)
    if not s:
        return 'Oturum bulunamadı', 404
    html = build_tick_html(s)
    out = os.path.join(DATA_DIR, f'takip_{sid}.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    return send_file(out, as_attachment=True, download_name=f'takip_{sid}.html')


@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        cfg = load_config()
        br = cfg.setdefault('browser', {})
        br['channel'] = request.form.get('channel') or ''
        br['executable'] = request.form.get('executable') or ''
        br['profile'] = request.form.get('profile') or ''
        cfg['city'] = request.form.get('city') or 'ankara'
        cfg['max_pages'] = int(request.form.get('max_pages') or 2)
        save_config(cfg)
        return redirect(url_for('config'))
    return render_template('config.html', cfg=load_config())


if __name__ == '__main__':
    cfg = load_config()
    app.run(host=cfg.get('host', '127.0.0.1'), port=cfg.get('port', 5000), debug=False)
