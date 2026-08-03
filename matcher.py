from cv_reader import normalize_turkish


def build_keywords(cv_text, meslek, ek_kelime=''):
    """CV metni + meslek + ek kelimelerden eslestirme anahtar kelimelerini uretir."""
    from cv_reader import extract_keywords
    kws = set(extract_keywords(cv_text or ''))
    for x in (meslek or '').split():
        x = x.strip()
        if x and len(x) >= 2:
            kws.add(normalize_turkish(x))
    for x in (ek_kelime or '').split(','):
        x = x.strip()
        if x:
            kws.add(normalize_turkish(x))
    return sorted(kws)


def parse_exclude(text):
    return [normalize_turkish(x.strip()) for x in (text or '').split(',') if x.strip()]


def score_job(job, keywords, exclude):
    """Ilani anahtar kelimelere gore puanlar; eslesme durumu dondurur."""
    tl = normalize_turkish((job.title or '') + ' ' + (job.desc or ''))
    hits = [k for k in keywords if k in tl]
    score = len(set(hits))
    job.matched = list(set(hits))
    job.score = score
    excluded = [e for e in exclude if e in normalize_turkish(job.title or '')]
    if excluded:
        job.match_state = 'hariç'
        return job
    # basliktaki meslek kelimesi direkt uygun
    if any(k in normalize_turkish(job.title or '') for k in keywords if len(k) >= 3):
        job.match_state = 'uygun'
    elif score >= 2:
        job.match_state = 'uygun'
    elif score == 1:
        job.match_state = 'dusuk'
    else:
        job.match_state = 'eslesme-yok'
    return job
