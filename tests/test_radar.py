"""Tests for the disruption radar: date extraction (French, Dutch, English), URL dedupe, and a live check that every
URL in the saved snapshot still answers 200 after redirects. The live check runs only with `-m live`."""
import json
from datetime import date
from pathlib import Path

import pytest

from overheard import radar

TODAY = date(2026, 11, 21)


@pytest.mark.parametrize("text,expected", [
    ("Grève SNCF le 28 novembre 2026", ["2026-11-28"]),
    ("le samedi 28 et le dimanche 29 novembre 2026", ["2026-11-28", "2026-11-29"]),
    ("du 24 au 26 novembre", ["2026-11-24", "2026-11-25", "2026-11-26"]),
    ("Préavis de grève à partir du 1er décembre", ["2026-12-01"]),
    ("Staking bij NS op zaterdag 28 november", ["2026-11-28"]),
    ("werkzaamheden van 28 t/m 30 november 2026", ["2026-11-28", "2026-11-29", "2026-11-30"]),
    ("zaterdag 28 en zondag 29 november", ["2026-11-28", "2026-11-29"]),
    ("Strike on November 26, 2026 at CDG", ["2026-11-26"]),
    ("Nov. 30 walkout", ["2026-11-30"]),
    ("Trains cancelled 28/11/2026", ["2026-11-28"]),
    ("Published 2026-11-19T10:00:00Z", ["2026-11-19"]),
    ("entre 25/11/2026 et 27/11/2026", ["2026-11-25", "2026-11-26", "2026-11-27"]),
    ("nothing dated here, 9315 at 09:25", []),
    ("le 17 nov. dernier", ["2026-11-17"]),
    ("14 januari", ["2027-01-14"]),
])
def test_extract_dates(text, expected):
    assert radar.extract_dates(text, TODAY) == expected


def test_extract_dates_skips_impossible_day():
    assert radar.extract_dates("le 32 novembre", TODAY) == []


def test_long_range_is_capped():
    out = radar.extract_dates("entre 02/11/2026 et 13/12/2026", TODAY)
    assert out[0] == "2026-11-02" and out[-1] == "2026-12-13" and "2026-11-28" in out


@pytest.mark.parametrize("a,b", [
    ("https://www.Example.com/a/b/?utm_source=x#top", "https://www.example.com/a/b"),
    ("http://example.com/a?id=3&utm_medium=rss", "https://example.com/a?id=3"),
])
def test_normalize_url(a, b):
    assert radar.normalize_url(a) == radar.normalize_url(b)


def test_dedupe_keeps_first_and_merges_dates():
    items = [
        {"url": "https://x.fr/a?utm_source=g", "dates": ["2026-11-28"], "quote": "q1"},
        {"url": "https://x.fr/a", "dates": ["2026-11-29"], "quote": "q2"},
        {"url": "https://y.nl/b", "dates": [], "quote": "q3"},
    ]
    out = radar.dedupe(items)
    assert [i["quote"] for i in out] == ["q1", "q3"]
    assert out[0]["dates"] == ["2026-11-28", "2026-11-29"]


def test_dedupe_same_page_two_locales():
    items = [{"url": "https://eurostar.com/us-en/travel-updates", "source": "eurostar.com", "title": "Disruptions", "dates": []},
             {"url": "https://eurostar.com/travel-updates", "source": "eurostar.com", "title": "Disruptions", "dates": []}]
    assert len(radar.dedupe(items)) == 1


def test_build_input_never_publishes_after_today():
    html = ('<html><head><title>Storingen</title><meta name="date" content="2026-11-28">'
            '<meta name="description" content="Geen treinen op zaterdag 28 november."></head></html>')
    inp = radar.build_input("https://www.b-europe.com/NL/Storingen", html, TODAY, via="search")
    assert inp["published"] == "2026-11-21" and inp["published_src"] == "fetched"
    assert inp["dates"] == ["2026-11-28"] and inp["kind"] == "news" and inp["lang"] == "nl"


def test_build_input_drops_stale_pages():
    html = '<html><head><title>Old</title><meta property="article:published_time" content="2017-01-01"></head></html>'
    assert radar.build_input("https://example.fr/old/page", html, TODAY, via="search") is None


def test_rss_filter_needs_disruption_and_travel_word():
    ok = radar._fold("Maandag alle Belgische vluchten geannuleerd wegens staking")
    noise = radar._fold("Sonde komt na 8 jaar aan bij Mercurius voor onderzoek")
    assert radar.DISRUPT_WORDS.search(ok) and radar.TRAVEL_WORDS.search(ok)
    assert not (radar.DISRUPT_WORDS.search(noise) and radar.TRAVEL_WORDS.search(noise))


def test_page_meta_reads_title_published_and_description():
    html = """<html><head><title>Fallback</title>
    <meta property="og:title" content="Grève SNCF : le trafic perturbé" />
    <meta property="article:published_time" content="2026-11-20T08:12:00+01:00">
    <meta name="description" content="Le trafic sera très perturbé le 26 novembre.">
    </head><body><p>Texte.</p></body></html>"""
    m = radar.page_meta(html)
    assert m["title"] == "Grève SNCF : le trafic perturbé"
    assert m["published"] == "2026-11-20"
    assert "26 novembre" in m["description"]


def test_page_meta_reads_json_ld_date():
    html = '<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-11-18T07:00:00Z"}</script>'
    assert radar.page_meta(html)["published"] == "2026-11-18"


def test_lang_of_url():
    assert radar.lang_of("https://www.francetvinfo.fr/x", "Grève") == "fr"
    assert radar.lang_of("https://nos.nl/artikel/1", "Staking") == "nl"


@pytest.mark.live
def test_snapshot_urls_answer_200(request):
    if "live" not in (request.config.getoption("markexpr") or ""):
        pytest.skip("network check: run with -m live")
    import httpx
    snaps = sorted(Path(radar.OUT_DIR).glob("snapshot_*.json"))
    assert snaps, "run python -m overheard.radar first"
    items = json.loads(snaps[-1].read_text())["items"]
    assert len(items) >= 10
    bad = []
    with httpx.Client(follow_redirects=True, timeout=30, headers=radar.HEADERS) as c:
        for it in items:
            for k in ("url", "published", "quote", "dates"):
                assert k in it and it[k] is not None, (k, it.get("url"))
            status = None
            for _ in range(3):  # one slow host should not fail the check
                try:
                    status = c.get(it["url"]).status_code
                    break
                except httpx.TransportError as e:
                    status = type(e).__name__
            if status != 200:
                bad.append((status, it["url"]))
    assert not bad, bad
