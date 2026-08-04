from cv_reader import normalize_turkish

# Baslikta tek basina gecince "uygun" sayilmamasi gereken genel gorev ekleri.
# (normalize_turkish ciktisi: ASCII, kucuk harf)
GENERIC_ROLE = frozenset({
    'teknisyeni', 'teknikeri', 'elemani', 'ustasi', 'kalfasi', 'sorumlusu',
    'operat', 'uzmani', 'muhendisi', 'isci', 'personeli', 'gorevli', 'uzm',
})


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
    """Hariç tutulacaklar. Virgül, yeni satir ve ' ve ' ayraci desteklenir;
    çok kelimeli ifadeler (örn. 'proje mühendisi') tek parca kalir."""
    import re
    out = []
    for piece in re.split(r'[,\n]+', text or ''):
        for p in re.split(r'\s+ve\s+', piece.strip()):
            p = normalize_turkish(p.strip())
            if p:
                out.append(p)
    return out


def score_job(job, keywords, exclude, meslek=''):
    """Ilani anahtar kelimelere gore puanlar; eslesme durumu dondurur.

    Genel gorev ekleri (teknisyeni, ustasi ...) tek basina 'uygun' sayilmaz;
    ayrica meslek tam ifadesi veya birincil meslek kelimesi baslikta varsa
    ilan dogrudan 'uygun' olur. Boylece 'dogalgaz teknisyeni' gibi alakasiz
    ilanlar eslesme-yok kalir.
    """
    tl = normalize_turkish((job.title or '') + ' ' + (job.desc or ''))
    strong = [k for k in keywords if len(k) >= 3 and k not in GENERIC_ROLE]
    hits = [k for k in strong if k in tl]
    score = len(set(hits))
    job.matched = list(set(hits))
    job.score = score
    # Hariç tutma: kelime basinda/eslenik önek eşleşmesi (Türkçe ekler için:
    # 'şef' -> 'şefi', 'mühendis' -> 'mühendisi') + çok kelimeli ifade alt dizesi.
    title_n = normalize_turkish(job.title or '')
    words = title_n.split()
    excluded = [e for e in exclude
                if e and (e in title_n or any(w.startswith(e) or e.startswith(w) for w in words))]
    if excluded:
        job.match_state = 'hariç'
        return job
    phrase = normalize_turkish(meslek).strip()
    primary = next((tok for tok in phrase.split() if len(tok) >= 3 and tok not in GENERIC_ROLE), '')
    if phrase and phrase in tl:
        job.match_state = 'uygun'
    elif primary and primary in tl:
        job.match_state = 'uygun'
    elif score >= 2:
        job.match_state = 'uygun'
    elif score == 1:
        job.match_state = 'dusuk'
    else:
        job.match_state = 'eslesme-yok'
    return job
