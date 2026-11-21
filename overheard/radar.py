"""Disruption radar: before the trip, sweep French, Dutch and English news for strikes, cancellations, closures and
weather that could hit a booking. Hydrogen with Google Search grounding runs one query set per booking (plus one per
country), source URLs come from the grounding metadata, redirect links are resolved to the real article with httpx,
and French and Dutch RSS feeds add keyword-matched items. Every item becomes a `news` Input (see SPEC.md) with its
url, title, quote, published date and the dates its text mentions. Scoring is match.py's job, not ours.

CLI: python -m overheard.radar --today 2026-11-21   (writes data/abroad/radar/snapshot_<today>.json)
"""
from __future__ import annotations

import argparse, hashlib, html as htmllib, json, re, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "abroad" / "radar"
LOG_C = ROOT / "logs" / "calls_C.jsonl"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/130.0 Safari/537.36",
           "Accept-Language": "fr,nl;q=0.9,en;q=0.8"}

# Feeds checked on 2026-11-21: each returned 200 with dated items. NS and Schiphol publish no RSS (404).
FEEDS = {
    "https://feeds.nos.nl/nosnieuwsalgemeen": "nl",
    "https://www.nu.nl/rss/Algemeen": "nl",
    "https://www.dutchnews.nl/feed/": "en",
    "https://www.francetvinfo.fr/titres.rss": "fr",
    "https://www.lemonde.fr/rss/une.xml": "fr",
    "https://www.20minutes.fr/feeds/rss-une.xml": "fr",
    "https://www.lefigaro.fr/rss/figaro_actualites.xml": "fr",
}

# ---------------------------------------------------------------------------------------------------------------
# Date extraction (French, Dutch, English). Pure; tested in tests/test_radar.py.

MONTHS = {
    # French
    "janvier": 1, "janv": 1, "fevrier": 2, "fevr": 2, "fev": 2, "mars": 3, "avril": 4, "avr": 4, "mai": 5,
    "juin": 6, "juillet": 7, "juil": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    # Dutch
    "januari": 1, "februari": 2, "maart": 3, "mrt": 3, "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
    "oktober": 10, "okt": 10,
    # English and shared abbreviations
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
    "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
WEEKDAYS = ("lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|maandag|dinsdag|woensdag|donderdag|vrijdag|"
            "zaterdag|zondag|monday|tuesday|wednesday|thursday|friday|saturday|sunday")
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
_ORD = r"(?:er|re|e|ste|de|st|nd|rd|th)?"
_RANGE_SEP = r"au|a|t/m|tot en met|tot|to|through|until|-|–"
_SEP = rf"\s*(?:,|et|en|and|&|{_RANGE_SEP})\s*(?:(?:le|de|op|the)\s+)?(?:(?:{WEEKDAYS})\s+)?"
DAY_MONTH = re.compile(rf"\b(\d{{1,2}}){_ORD}((?:{_SEP}\d{{1,2}}{_ORD})*)\s+({_MON})\b\.?(?:\s+(\d{{4}}))?")
MONTH_DAY = re.compile(rf"\b({'|'.join(m for m in sorted(MONTHS, key=len, reverse=True) if m != 'may')})\b\.?\s+"
                       rf"(\d{{1,2}})(?:st|nd|rd|th)?(?!\d)(?:\s*(?:-|–|to|through)\s*(\d{{1,2}})(?!\d))?(?:,?\s+(\d{{4}}))?")
ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})")
NUMERIC = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")
RANGE_WORDS = re.compile(rf"^\s*(?:{_RANGE_SEP})\s*$")
LIST_RANGE_WORDS = re.compile(r"^\s*(?:et|and|en)\s*$")
RANGE_CUES = re.compile(r"(?:entre|between|du|van|from)\s*$")
MAX_RANGE_DAYS = 62


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _mk(y: int | None, m: int, d: int, today: date) -> date | None:
    try:
        if y is not None:
            return date(y, m, d)
        options = []
        for yy in (today.year - 1, today.year, today.year + 1):
            try:
                options.append(date(yy, m, d))
            except ValueError:
                pass
        return min(options, key=lambda x: abs((x - today).days)) if options else None
    except ValueError:
        return None


def _span(a: date, b: date) -> list[date]:
    if b < a or (b - a).days > MAX_RANGE_DAYS:
        return [a, b] if b >= a else [a]
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def extract_dates(text: str, today: date) -> list[str]:
    """Every calendar date the text mentions, as sorted unique YYYY-MM-DD. Ranges ("du 24 au 26 novembre",
    "28 t/m 30 november", "entre 25/11/2026 et 27/11/2026") expand to each day, up to 62 days."""
    s = _fold(text or "")
    found: set[date] = set()
    taken = [False] * len(s)

    def claim(m):
        for i in range(m.start(), m.end()):
            taken[i] = True

    # full numeric and ISO dates, with ranges between two of them
    full = []
    for m in list(ISO.finditer(s)):
        d = _mk(int(m[1]), int(m[2]), int(m[3]), today)
        if d:
            full.append((m.start(), m.end(), d))
        claim(m)
    for m in NUMERIC.finditer(s):
        if taken[m.start()]:
            continue
        d = _mk(int(m[3]), int(m[2]), int(m[1]), today)
        if d:
            full.append((m.start(), m.end(), d))
        claim(m)
    full.sort()
    for i, (st, en, d) in enumerate(full):
        found.add(d)
        if i + 1 < len(full):
            gap = s[en:full[i + 1][0]]
            ranged = RANGE_WORDS.match(gap) or (LIST_RANGE_WORDS.match(gap) and RANGE_CUES.search(s[max(0, st - 12):st]))
            if ranged:
                found.update(_span(d, full[i + 1][2]))

    # "28 et 29 novembre 2026", "24 au 26 novembre", "1er decembre", "17 nov."
    for m in DAY_MONTH.finditer(s):
        if taken[m.start()]:
            continue
        month, year = MONTHS[m[3]], int(m[4]) if m[4] else None
        parts = re.split(rf"({_SEP})", m[1] + (m[2] or ""))
        days = [int(re.match(r"\d+", p)[0]) for p in parts[0::2] if re.match(r"\d+", p)]
        seps = parts[1::2]
        dates = [_mk(year, month, d, today) for d in days]
        for j, d in enumerate(dates):
            if d:
                found.add(d)
            if j < len(seps) and d and dates[j + 1] and re.search(rf"(?:^|\s)(?:{_RANGE_SEP})(?:\s|$)", seps[j].strip()):
                found.update(_span(d, dates[j + 1]))
        claim(m)

    # "November 26, 2026", "Nov. 30", "Nov 28-30"
    for m in MONTH_DAY.finditer(s):
        if taken[m.start()]:
            continue
        month, year = MONTHS[m[1]], int(m[4]) if m[4] else None
        a = _mk(year, month, int(m[2]), today)
        if a:
            found.add(a)
            if m[3]:
                b = _mk(year, month, int(m[3]), today)
                if b:
                    found.update(_span(a, b))
        claim(m)
    return sorted(d.isoformat() for d in found)


# ---------------------------------------------------------------------------------------------------------------
# URLs, dedupe, page metadata, language. Pure.

TRACKING = re.compile(r"^(utm_|xtor|at_|ito|fbclid|gclid|mc_|ns_|cmpid|ref$|origin$)")


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k.lower())]
    path = p.path.rstrip("/") or "/"
    return urlunsplit(("https", p.netloc.lower().removeprefix("www."), path, urlencode(q), ""))


def dedupe(items: list[dict]) -> list[dict]:
    """Keep the first item per resolved URL; later duplicates add their dates and bookings to it."""
    out, seen = [], {}
    for it in items:
        key = normalize_url(it["url"])
        if key in seen:
            first = seen[key]
            first["dates"] = sorted(set(first.get("dates") or []) | set(it.get("dates") or []))
            if it.get("found_for"):
                first["found_for"] = sorted(set(first.get("found_for") or []) | set(it["found_for"]))
            continue
        seen[key] = it
        out.append(it)
    return out


_META = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r"""([\w:.-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
PUB_KEYS = ("article:published_time", "og:article:published_time", "datepublished", "publishdate", "pubdate",
            "date", "dc.date.issued", "dc.date", "parsely-pub-date", "sailthru.date", "article.published")


def _iso_day(v: str) -> str | None:
    v = (v or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        return m[0]
    try:
        return parsedate_to_datetime(v).date().isoformat()
    except Exception:  # noqa: BLE001
        return None


def page_meta(html: str) -> dict:
    """Title, published day (YYYY-MM-DD) and description from an article's HTML head."""
    metas = {}
    for tag in _META.findall(html or ""):
        attrs = {k.lower(): htmllib.unescape(a or b) for k, a, b in _ATTR.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").lower()
        if key and "content" in attrs and key not in metas:
            metas[key] = attrs["content"].strip()
    title = metas.get("og:title") or metas.get("twitter:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
        title = htmllib.unescape(re.sub(r"\s+", " ", m[1])).strip() if m else ""
    published = next((d for k in PUB_KEYS if (d := _iso_day(metas.get(k, "")))), None)
    if not published:
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html or "")
        published = _iso_day(m[1]) if m else None
    if not published:
        m = re.search(r"<time[^>]+datetime=[\"']([^\"']+)", html or "", re.I)
        published = _iso_day(m[1]) if m else None
    desc = metas.get("og:description") or metas.get("description") or metas.get("twitter:description") or ""
    return {"title": title, "published": published, "description": desc}


def page_text(html: str) -> str:
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html or "")
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", htmllib.unescape(s)).strip()


TLD_LANG = {"fr": "fr", "nl": "nl", "be": "fr", "uk": "en", "com": None}
STOP = {"fr": {"le", "la", "les", "des", "du", "est", "sur", "pour", "une", "dans"},
        "nl": {"de", "het", "een", "van", "is", "op", "voor", "niet", "zijn", "bij"},
        "en": {"the", "and", "of", "is", "on", "for", "to", "in", "will", "with"}}


def lang_of(url: str, text: str) -> str:
    host = urlsplit(url).netloc.lower()
    path = urlsplit(url).path.lower()
    for code in ("fr", "nl", "en"):
        if path.startswith(f"/{code}/") or path.startswith(f"/{code}-"):
            return code
    tld = TLD_LANG.get(host.rsplit(".", 1)[-1])
    if tld and host.rsplit(".", 1)[-1] in ("fr", "nl"):
        return tld
    words = re.findall(r"[a-zà-ÿ]+", (text or "").lower())
    scores = {k: sum(w in v for w in words) for k, v in STOP.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else (tld or "en")


def _clean(s: str) -> str:
    s = re.sub(r"\*\*|__|^\s*[-*\d.]+\s+", "", s or "", flags=re.M)
    return re.sub(r"\s+", " ", s).strip()


def _quoted(s: str) -> list[str]:
    return [q.strip() for q in re.findall(r"[«“\"]\s*([^«»“”\"]{25,400}?)\s*[»”\"]", s or "")]


# ---------------------------------------------------------------------------------------------------------------
# Query sets

DISRUPTION = {"fr": "grève OR annulation OR perturbation OR fermeture", "nl": "staking OR storing OR geannuleerd OR gesloten",
              "en": "strike OR cancellation OR disruption OR closure"}


def query_jobs(it: dict, today: date) -> list[dict]:
    """One search job per booking, plus one per country for national strikes and weather warnings."""
    jobs = []
    for b in it["bookings"]:
        start, end = b["start"][:10], b["end"][:10]
        names = " ".join(x for x in (b.get("operator"), b.get("number")) if x)
        hints = []
        if "fr" in b["langs"]:
            hints += [f"grève {b.get('operator')} novembre 2026", f"{names} annulation perturbation",
                      f"{b.get('from_place') or b.get('city')} fermeture travaux novembre 2026"]
        if "nl" in b["langs"]:
            hints += [f"staking {b.get('operator')} november 2026", f"{names} storing geannuleerd",
                      f"{b.get('to_place') or b.get('from_place') or b.get('city')} drukte werkzaamheden november 2026"]
        hints += [f"{names} strike cancellation November 2026"]
        jobs.append({"id": b["id"], "booking_ids": [b["id"]], "langs": b["langs"], "hints": hints,
                     "brief": f"{b['title']} ({b['kind']}), {start} to {end}, from {b.get('from_place')} "
                              f"to {b.get('to_place') or '-'}, city {b['city']}"})
    by_country: dict[str, list[dict]] = {}
    for b in it["bookings"]:
        by_country.setdefault(b["country"], []).append(b)
    for c, bs in by_country.items():
        start = min(b["start"][:10] for b in bs)
        end = max(b["end"][:10] for b in bs)
        if c == "FR":
            hints = ["grève transports France fin novembre 2026", "préavis de grève SNCF RATP aéroports novembre 2026",
                     "Météo-France vigilance Paris novembre 2026", "manifestation Paris 28 novembre 2026"]
            langs = ["fr", "en"]
        else:
            hints = ["staking NS ov november 2026", "KNMI code oranje storm november 2026",
                     "Schiphol drukte storing november 2026", "storing treinverkeer Amsterdam november 2026"]
            langs = ["nl", "en"]
        jobs.append({"id": f"country_{c.lower()}", "booking_ids": [b["id"] for b in bs], "langs": langs,
                     "hints": hints, "brief": f"travel in {c} ({', '.join(sorted({b['city'] for b in bs}))}) "
                                              f"from {start} to {end}"})
    return jobs


PROMPT = """You are the disruption radar for a traveller. Today is {today}.
Trip part to protect: {brief}.

Use Google Search, in these languages: {langs}. Start with these queries and add your own:
{hints}

Find real news articles, operator notices or official warnings, published in the last 30 days or announcing
something for the trip dates, about anything that could disrupt this: strikes and strike notices, cancellations,
delays, engineering works, closures, protests, crowding, weather warnings.

For each article you found, write one numbered entry:
- the article title, as published
- its publication date (YYYY-MM-DD)
- the dates it says the disruption happens
- one sentence copied word for word from the article, in its original language, inside « »

Report only articles that the search returned. Include items whose dates are near but outside the trip, and say so.
If nothing relevant exists, say that plainly."""


def _log_c(model: str, summary: str, latency: float, **extra):
    LOG_C.parent.mkdir(exist_ok=True)
    with LOG_C.open("a") as f:
        f.write(json.dumps({"t": time.strftime("%H:%M:%S"), "model": model, "summary": summary[:120],
                            "latency_s": round(latency, 3), **extra}) + "\n")


def search_job(job: dict, today: date) -> dict:
    """One Hydrogen call with the google_search tool. Returns cited sources and the text that cites them."""
    from google.genai import types
    from overheard import config
    from overheard.gemini import client, timed
    prompt = PROMPT.format(today=today.isoformat(), brief=job["brief"], langs=", ".join(job["langs"]),
                           hints="\n".join(f"- {h}" for h in job["hints"]))
    t0 = time.time()
    r = timed(config.HYDROGEN, f"radar search {job['id']}", client().models.generate_content,
              model=config.HYDROGEN, contents=prompt,
              config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())],
                                                 thinking_config=types.ThinkingConfig(thinking_level="low")))
    gm = r.candidates[0].grounding_metadata if r.candidates else None
    chunks = list(gm.grounding_chunks or []) if gm else []
    queries = list(gm.web_search_queries or []) if gm else []
    _log_c(config.HYDROGEN, f"radar search {job['id']}", time.time() - t0, n_sources=len(chunks), queries=queries)
    cited: dict[int, list[str]] = {}
    for s in (gm.grounding_supports or []) if gm else []:
        for i in s.grounding_chunk_indices or []:
            cited.setdefault(i, []).append(s.segment.text or "")
    text = r.text or ""
    sources = []
    for i, ch in enumerate(chunks):
        if i not in cited or not ch.web or not ch.web.uri:
            continue
        sources.append({"uri": ch.web.uri, "domain": ch.web.title or "", "segments": cited[i],
                        "found_for": job["booking_ids"], "context": _entry_around(text, cited[i])})
    return {"job": job["id"], "queries": queries, "answer": text, "sources": sources}


def _entry_around(text: str, segments: list[str]) -> str:
    """The numbered entry of the model's answer that holds the first cited segment."""
    entries = re.split(r"\n(?=\s*(?:\d+\.|\*\*\d+|#+ ))", text)
    for seg in segments:
        for e in entries:
            if seg.strip() and seg.strip()[:60] in e:
                return e
    return " ".join(segments)


# ---------------------------------------------------------------------------------------------------------------
# Fetching and building Inputs

def fetch(c, url: str) -> tuple[str, str] | None:
    """Resolve redirects and fetch the article. Returns (final_url, html) when it answers 200 with HTML."""
    try:
        r = c.get(url)
    except Exception:  # noqa: BLE001
        return None
    if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
        return None
    return str(r.url), r.text


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?»])\s+", text) if 30 <= len(s.strip()) <= 400]


def build_input(final_url: str, html: str, today: date, *, segments=(), context: str = "", found_for=(),
                via: str, rss: dict | None = None) -> dict | None:
    meta = page_meta(html)
    body = page_text(html)
    title = _clean((rss or {}).get("title") or meta["title"])
    published = (rss or {}).get("published") or meta["published"] or _iso_day(_first_model_date(context))
    if not title or not published:
        return None
    folded_body = _fold(body)
    quote, verified = "", False
    for q in _quoted(context) + [_clean(s) for s in segments]:
        if q and _fold(q)[:80] in folded_body:
            quote, verified = q, True
            break
    if not quote:
        quote = _clean((rss or {}).get("summary") or meta["description"]) or next(iter(_quoted(context)), "")
    if not quote:
        quote = next(iter(_sentences(body)), "")
    if not quote:
        return None
    summary = _clean(" ".join(segments)) or _clean(meta["description"])
    dated_text = " ".join([title, quote, meta["description"], summary])
    lang = lang_of(final_url, f"{title} {quote}")
    return {"id": "news_" + hashlib.sha1(normalize_url(final_url).encode()).hexdigest()[:10],
            "kind": "news", "origin": "radar", "mime": "text/plain",
            "text": f"{title}. {summary}" if summary and summary not in title else title,
            "url": final_url, "title": title, "quote": quote[:400], "quote_verified": verified,
            "published": published, "dates": extract_dates(dated_text, today), "lang": lang,
            "source": urlsplit(final_url).netloc.removeprefix("www."), "found_for": sorted(set(found_for)),
            "via": via}


def _first_model_date(context: str) -> str:
    m = re.search(r"\d{4}-\d{2}-\d{2}", context or "")
    return m[0] if m else ""


KEYWORDS = re.compile(r"\b(greve|greves|preavis|staking|staken|sncf|ratp|eurostar|thalys|schiphol|klm|air france|"
                      r"louvre|annul\w*|geannuleerd|storing\w*|vertraging\w*|perturb\w*|tempete|storm|code oranje|"
                      r"code rood|vigilance|neige|sneeuw|fermeture|gesloten|manifestation|demonstratie|"
                      r"cdg|roissy|orly|gare du nord|ns\b|prorail|trafic|treinverkeer|aeroport|luchthaven)", re.I)


def rss_items(today: date, days: int = 14) -> list[dict]:
    """Keyword-matched items from the French and Dutch feeds, published in the last `days` days."""
    import feedparser, httpx
    out = []
    for url, lang in FEEDS.items():
        try:
            r = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
            feed = feedparser.parse(r.content)
        except Exception:  # noqa: BLE001
            continue
        for e in feed.entries:
            pp = e.get("published_parsed") or e.get("updated_parsed")
            if not pp:
                continue
            pub = date(*pp[:3])
            if (today - pub).days > days or pub > today + timedelta(days=1):
                continue
            summary = re.sub(r"<[^>]+>", " ", e.get("summary", "") or "")
            if not KEYWORDS.search(_fold(f"{e.get('title', '')} {summary}")):
                continue
            out.append({"link": e.get("link"), "title": e.get("title", ""), "summary": _clean(summary)[:400],
                        "published": pub.isoformat(), "feed": url, "lang": lang})
    return out


def sweep(it: dict, today: date | str, *, workers: int = 8, use_rss: bool = True) -> list[dict]:
    """Search, resolve, fetch and dedupe. Returns `news` Inputs, newest first."""
    import httpx
    today = date.fromisoformat(today) if isinstance(today, str) else today
    jobs = query_jobs(it, today)
    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(lambda j: _safe_search(j, today), jobs))
    sweep.last_results = results  # kept for the snapshot's proof section
    sources = [s for r in results for s in r["sources"]]
    rss = rss_items(today) if use_rss else []
    with httpx.Client(follow_redirects=True, timeout=20, headers=HEADERS) as c:
        def from_source(s):
            got = fetch(c, s["uri"])
            if not got:
                return None
            return build_input(got[0], got[1], today, segments=s["segments"], context=s["context"],
                               found_for=s["found_for"], via="search")

        def from_rss(e):
            got = fetch(c, e["link"])
            if not got:
                return None
            return build_input(got[0], got[1], today, found_for=[], via="rss", rss=e)

        with ThreadPoolExecutor(workers) as ex:
            built = list(ex.map(from_source, sources)) + list(ex.map(from_rss, rss))
    items = [b for b in built if b and _is_article(b["url"])]
    items = dedupe(items)
    items.sort(key=lambda x: x["published"], reverse=True)
    return items


def _is_article(url: str) -> bool:
    return len(urlsplit(url).path.strip("/")) > 3


def _safe_search(job, today):
    try:
        return search_job(job, today)
    except Exception as e:  # noqa: BLE001
        print(f"[radar] search {job['id']} failed: {str(e)[:120]}", flush=True)
        return {"job": job["id"], "queries": [], "answer": "", "sources": [], "error": str(e)[:200]}


def save(items: list[dict], it: dict, today: date) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"snapshot_{today.isoformat()}.json"
    results = getattr(sweep, "last_results", [])
    path.write_text(json.dumps({
        "today": today.isoformat(), "itinerary_id": it["id"], "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_items": len(items), "items": items,
        "searches": [{"job": r["job"], "queries": r["queries"], "n_sources": len(r["sources"])} for r in results],
    }, ensure_ascii=False, indent=2))
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--itinerary", default=str(ROOT / "data" / "abroad" / "itinerary.json"))
    ap.add_argument("--no-rss", action="store_true")
    a = ap.parse_args()
    today = date.fromisoformat(a.today)
    it = json.loads(Path(a.itinerary).read_text())
    t0 = time.time()
    items = sweep(it, today, use_rss=not a.no_rss)
    path = save(items, it, today)
    fr_nl = sum(i["lang"] in ("fr", "nl") for i in items)
    print(f"[radar] {len(items)} items ({fr_nl} French or Dutch) in {time.time() - t0:.1f}s -> {path.relative_to(ROOT)}")
    for i in items:
        print(f"  {i['published']} {i['lang']} {i['via']:6} {i['source'][:24]:24} {i['title'][:70]}  dates={i['dates'][:4]}")


if __name__ == "__main__":
    main()
