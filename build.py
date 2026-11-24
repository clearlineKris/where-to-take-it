#!/usr/bin/env python3
"""Build the Where to Take It static directory from JSON data."""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SITE = ROOT / "site"
TEMPLATES = ROOT / "templates"
LOGS = ROOT / "logs"
TODAY = datetime.date.today().isoformat()

FLAG_LABELS = {
    "yes": ("Takes it", "flag-yes"),
    "yes_fee": ("Takes it, fee", "flag-fee"),
    "yes_fee_or_voucher": ("Takes it, voucher or fee", "flag-fee"),
    "liquid_only": ("Liquid only", "flag-maybe"),
    "likely_hhw": ("Likely as HHW — confirm", "flag-maybe"),
    "likely_electronics": ("Likely as electronics — confirm", "flag-maybe"),
    "small_only": ("Small items only — confirm", "flag-maybe"),
    "limited": ("Limited", "flag-maybe"),
    "not_listed": ("Not listed", "flag-maybe"),
    "no": ("Does not take it", "flag-no"),
}

ITEM_COLUMNS = [
    ("mattresses", "Mattresses"),
    ("paint", "Paint"),
    ("batteries_hhw", "Batteries"),
    ("tvs", "TVs"),
    ("tires", "Tires"),
    ("appliances", "Appliances"),
    ("used_oil", "Used oil"),
]


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


DEFAULT_BASE_PATH = ""


def site_base() -> str:
    """Public URL prefix. Default is the site root (Vercel).

    Override with SITE_BASE_PATH if the site is ever served from a
    subdirectory. An empty value keeps links at the domain root.
    """
    if "SITE_BASE_PATH" in os.environ:
        return os.environ["SITE_BASE_PATH"].rstrip("/")
    return DEFAULT_BASE_PATH.rstrip("/")


def href(path: str) -> str:
    """Root-relative URL. Directories keep a trailing slash when given."""
    raw = str(path)
    trailing = raw.endswith("/")
    path = raw.lstrip("/")
    base = site_base()
    url = f"{base}/{path}" if base else f"/{path}"
    if trailing and not url.endswith("/"):
        url += "/"
    return url


def page_shell(title: str, path: str, content: str, description: str = "") -> str:
    desc = description or "Official drop-off hours, fees, and accepted items, checked against the city or county page."
    fonts = (
        "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,650;9..144,700"
        "&family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title) if title.strip() != "Where to Take It" else "Where to Take It"}</title>
  <meta name="description" content="{esc(desc)}">
  <meta name="theme-color" content="#f3eee3">
  <link rel="icon" href="{href('favicon.svg')}" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="{esc(fonts)}">
  <link rel="stylesheet" href="{href('styles.css')}">
  <script src="{href('search.js')}" defer></script>
</head>
<body>
  <a class="skiplink" href="#content">Skip to content</a>
  <p class="disclaimer">This is an independent directory, not a government website. Hours and fees change — confirm with the facility before you go.</p>
  <header class="site">
    <div class="wrap brandrow">
      <a class="brand" href="{href('index.html')}">
        <span class="logo-mark" aria-hidden="true"><span class="logo-pin"></span></span>
        <span class="brand-text">
          <span class="brand-name">Where to Take It</span>
          <span class="brand-tag">Drop-off hours, fees, and what they actually accept</span>
        </span>
      </a>
      <nav class="primary" aria-label="Primary">
        <a href="{href('index.html')}">Home</a>
        <a href="{href('metro/twin-cities/')}">Twin Cities</a>
        <a href="{href('about/')}">About &amp; sources</a>
        <a class="nav-cta" href="{href('metro/twin-cities/')}">Browse sites</a>
      </nav>
    </div>
  </header>
  <main id="content">
    <div class="wrap">
{content}
    </div>
  </main>
  <footer class="site">
    <div class="wrap">
      <p>Where to Take It is an independent, unofficial directory. Listing a site does not mean the facility endorses this project. Always check the official page or call before you drive.</p>
      <p><a href="{href('about/')}">How entries are sourced</a></p>
    </div>
  </footer>
</body>
</html>
"""


def source_list(sources: list) -> str:
    items = []
    for s in sources:
        updated = ""
        if s.get("page_updated"):
            updated = f" (page dated {esc(s['page_updated'])})"
        items.append(
            f'<li><a href="{esc(s["url"])}">{esc(s["title"])}</a>{updated}</li>'
        )
    return "<ol>\n" + "\n".join(items) + "\n</ol>"


def hours_html(location: dict) -> str:
    rows = "".join(
        f'<li><span class="d">{esc(h["days"])}</span><span>{esc(h["time"])}</span></li>'
        for h in location.get("hours", [])
    )
    extra = ""
    if location.get("office_hours"):
        extra = f'<p>{esc(location["office_hours"])}</p>'
    return f'<ul class="hours">{rows}</ul>{extra}'


def flag_html(code: str) -> str:
    label, cls = FLAG_LABELS.get(code, (code or "Unknown", "flag-maybe"))
    return f'<span class="flag {cls}">{esc(label)}</span>'


def location_search_blob(location: dict) -> str:
    flags = location.get("item_flags", {})
    parts = [
        location.get("name", ""),
        location.get("agency", ""),
        location.get("city", ""),
        location.get("address", ""),
        location.get("residency", ""),
        " ".join(location.get("accepts", [])),
        " ".join(location.get("fees", [])),
    ]
    for key, label in ITEM_COLUMNS:
        parts.append(label)
        parts.append(key.replace("_", " "))
        if flags.get(key) in {"yes", "yes_fee", "yes_fee_or_voucher", "liquid_only", "small_only", "limited"}:
            parts.append(label)
    return " ".join(parts)


def accepted_item_keys(location: dict) -> str:
    flags = location.get("item_flags", {})
    keys = []
    for key, _label in ITEM_COLUMNS:
        code = flags.get(key, "not_listed")
        if code not in {"no", "not_listed"}:
            keys.append(key)
    return " ".join(keys)


def location_card(location: dict, heading: str = "h2") -> str:
    loc_url = href(f"locations/{location['id']}/")
    flags = location.get("item_flags", {})
    chips = "".join(
        f'<span class="item-row"><span class="addr">{esc(label)}</span>{flag_html(flags.get(key, "not_listed"))}</span>'
        for key, label in ITEM_COLUMNS
    )
    phone = f'<p>Phone: <span class="phone">{esc(location["phone"])}</span></p>' if location.get("phone") else ""
    search = esc(location_search_blob(location))
    items = esc(accepted_item_keys(location))
    return f"""
<article class="loc" data-filter-item data-search="{search}" data-items="{items}">
  <{heading}><a href="{loc_url}">{esc(location["name"])}</a></{heading}>
  <p class="addr">{esc(location["address"])}<br>{esc(location["agency"])}</p>
  {hours_html(location)}
  {phone}
  <p>{esc(location["residency"])}</p>
  <div class="item-row">{chips}</div>
  <p class="meta">Last checked {esc(location["last_checked"])}. <a href="{loc_url}">Full listing</a> · <a href="{esc(location["website"])}">Official page</a></p>
</article>
"""


def bullets(items: list) -> str:
    return "<ul class=\"facts\">" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


def write(path: Path, title: str, rel: str, content: str, description: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page_shell(title, rel, content, description), encoding="utf-8")


def build_home(locations: list, guides: list) -> None:
    published = [g for g in guides if g.get("status") == "published"]
    loc_preview = "\n".join(location_card(loc, "h3") for loc in locations[:3])
    guide_cards = []
    for g in published:
        guide_cards.append(
            f"""<article class="card">
  <p class="kicker">Item guide</p>
  <h2><a href="{href(g['path'])}">{esc(g["title"])}</a></h2>
  <p>{esc(g["dek"])}</p>
  <p class="meta">Checked {esc(g["last_checked"])}</p>
</article>"""
        )
    if not guide_cards:
        guide_cards.append("<p>No guides published yet.</p>")
    listing = href("metro/twin-cities/")
    mattress = href("mn/minneapolis/mattress/")
    shortcuts = [
        ("Mattresses", f"{mattress}"),
        ("Paint", f"{listing}?q=paint"),
        ("Batteries", f"{listing}?item=batteries_hhw"),
        ("TVs", f"{listing}?item=tvs"),
        ("Tires", f"{listing}?item=tires"),
        ("Appliances", f"{listing}?item=appliances"),
        ("Used oil", f"{listing}?item=used_oil"),
    ]
    chips = "".join(
        f'<li><a href="{esc(url)}">{esc(label)}</a></li>' for label, url in shortcuts
    )
    content = f"""
<section class="hero">
  <div class="hero-copy">
    <p class="kicker">A practical drop-off directory</p>
    <h1>Find the place that will actually take the thing in your trunk.</h1>
    <div class="hero-rule" aria-hidden="true"></div>
    <p class="dek">People search every day for where to drop off paint, mattresses, batteries, TVs, tires, and used oil. This site answers with official hours, fees, residency rules, and the “do not bring” list — copied from the city or county page and dated.</p>
    <ul class="hero-principles" aria-label="How this directory works">
      <li>Official hours and fees</li>
      <li>Residency rules, written plainly</li>
      <li>Sourced and dated</li>
    </ul>
    <form class="hero-search" action="{listing}" method="get" role="search">
      <label for="home-q">What do you need to drop off?</label>
      <div class="hero-search-row">
        <input id="home-q" type="search" name="q" placeholder="Mattress, paint, batteries, a TV…">
        <button type="submit">Find a site</button>
      </div>
      <ul class="item-shortcuts">{chips}</ul>
    </form>
  </div>
  <aside class="hero-aside">
    <p class="kicker">First metro</p>
    <h2>Minneapolis–Saint Paul</h2>
    <p>Six official city and county sites, with a comparison of who takes mattresses, paint, TVs, tires, appliances, batteries, and used oil.</p>
    <p><a class="nav-cta" href="{listing}">Open the Twin Cities listing</a></p>
  </aside>
</section>
<section>
  <h2>Useful pages</h2>
  <div class="grid">{''.join(guide_cards)}</div>
</section>
<section data-filter-root data-filter-sync="off">
  <h2>Featured locations</h2>
  <div class="filter-bar">
    <label for="home-sites">Filter these sites</label>
    <div class="filter-controls">
      <input id="home-sites" type="search" data-filter-input placeholder="Name, city, or item…">
    </div>
    <p class="filter-status" data-filter-status aria-live="polite"></p>
  </div>
  <div class="grid">{loc_preview}</div>
  <p class="filter-empty callout" data-filter-empty>No featured site matches that search. Try the full <a href="{listing}">Twin Cities listing</a>.</p>
  <p><a href="{listing}">See all Twin Cities sites</a></p>
</section>
<section>
  <h2>How this is built</h2>
  <p>Each listing is written from a public official page, with a last-checked date and a link back to the source. The site ships one new useful page at a time — one item in one city, or one newly researched facility — rather than scraping a national database and hoping the hours are still right.</p>
  <p>It is not affiliated with any city, county, or waste hauler.</p>
</section>
"""
    write(
        SITE / "index.html",
        "Where to Take It",
        "index.html",
        content,
        "Official drop-off hours, fees, and accepted items for household junk that does not belong in the trash.",
    )


def filter_chips_html() -> str:
    buttons = []
    for key, label in ITEM_COLUMNS:
        buttons.append(
            f'<button type="button" data-filter-chip="{esc(key)}" aria-pressed="false">{esc(label)}</button>'
        )
    return "".join(buttons)


def build_listing(region: dict, locations: list) -> None:
    rows = []
    for loc in locations:
        flags = loc.get("item_flags", {})
        cells = "".join(f"<td>{flag_html(flags.get(key, 'not_listed'))}</td>" for key, _ in ITEM_COLUMNS)
        rows.append(
            f'<tr><th scope="row"><a href="{href(f"locations/{loc["id"]}/")}">{esc(loc["name"])}</a><br><span class="addr">{esc(loc["city"])}</span></th>{cells}</tr>'
        )
    head = "".join(f"<th>{esc(label)}</th>" for _, label in ITEM_COLUMNS)
    cards = "\n".join(location_card(loc, "h2") for loc in locations)
    content = f"""
<p class="kicker">{esc(region["state"])} metro listing</p>
<h1>{esc(region["name"])} drop-off sites</h1>
<p class="dek">{esc(region["summary"])}</p>
<p class="meta">{len(locations)} facilities checked November 20, 2026. The seven-county metro, as used by several of these sites, is {esc(", ".join(region["seven_county"]))}.</p>
<div data-filter-root>
  <form class="filter-bar" role="search">
    <label for="site-filter">Search or filter sites</label>
    <div class="filter-controls">
      <input id="site-filter" type="search" name="q" data-filter-input placeholder="Name, city, agency, or item…">
      <button type="submit">Filter</button>
    </div>
    <div class="filter-chips" role="group" aria-label="Filter by item">{filter_chips_html()}</div>
    <p class="filter-status" data-filter-status aria-live="polite"></p>
  </form>
  <h2>What each site takes</h2>
  <p>Green means the official page says they take it. Gold means there is a fee or a confirmation gap. Red means the official page says no, or the item is not part of that facility’s job (for example, a hazardous-waste site that does not take mattresses).</p>
  <div class="table-wrap">
  <table>
    <thead><tr><th>Site</th>{head}</tr></thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
  </div>
  <p class="meta">“Likely” or “not listed” is not a yes. Call or read the official page before you load the car.</p>
  <h2>The facilities</h2>
  {cards}
  <p class="filter-empty callout" data-filter-empty>No facility matches that search. Clear the filters or try another item.</p>
</div>
<section class="sources">
  <h2>Sources</h2>
  <p>Each card links to the official page used for that listing. See also the <a href="{href('about/')}">about page</a>.</p>
</section>
"""
    write(
        SITE / "metro/twin-cities/index.html",
        "Twin Cities drop-off sites",
        "metro/twin-cities/index.html",
        content,
        region["summary"],
    )


def build_location(location: dict) -> None:
    sources = source_list(location.get("sources", []))
    email = f'<p>Email: <a href="mailto:{esc(location["email"])}">{esc(location["email"])}</a></p>' if location.get("email") else ""
    appt = f'<h2>Before you go</h2><p>{esc(location["appointment"])}</p>' if location.get("appointment") else ""
    flags = location.get("item_flags", {})
    chips = "".join(
        f'<span class="item-row"><span class="addr">{esc(label)}</span>{flag_html(flags.get(key, "not_listed"))}</span>'
        for key, label in ITEM_COLUMNS
    )
    official = esc(location["website"])
    first_source = (location.get("sources") or [{}])[0]
    source_title = esc(first_source.get("title") or "Official page")
    source_url = esc(first_source.get("url") or location.get("website") or "")
    content = f"""
<p class="kicker">{esc(location["city"])}, {esc(location["state"])}</p>
<h1>{esc(location["name"])}</h1>
<p class="dek">{esc(location["agency"])} · {esc(location["address"])}</p>
<p class="meta">Last checked {esc(location["last_checked"])}. <a href="{official}">Official page</a></p>
<div class="item-row">{chips}</div>
<div class="fact-grid">
  <article class="fact-card">
    <h2>Hours</h2>
    {hours_html(location)}
  </article>
  <article class="fact-card">
    <h2>Fees</h2>
    {bullets(location.get("fees", []))}
  </article>
  <article class="fact-card">
    <h2>Accepts</h2>
    {bullets(location.get("accepts", [])[:8])}
  </article>
  <article class="fact-card">
    <h2>Source</h2>
    <p>Last checked {esc(location["last_checked"])}.</p>
    <p><a href="{source_url}">{source_title}</a></p>
    <p>Always confirm on the official page before you go.</p>
  </article>
</div>
<h2>Who can use it</h2>
<p>{esc(location["residency"])}</p>
{"<p>Proof of residency is required.</p>" if location.get("proof_required") else ""}
<p>Phone: <span class="phone">{esc(location.get("phone") or "See official page")}</span></p>
{email}
{appt}
<h2>Not accepted</h2>
{bullets(location.get("does_not_accept", []))}
<h2>Notes</h2>
{bullets(location.get("notes", []))}
<section class="sources">
  <h2>Sources</h2>
  {sources}
</section>
<p><a href="{href('metro/twin-cities/')}">Back to the Twin Cities listing</a></p>
"""
    rel = f"locations/{location['id']}/index.html"
    write(SITE / rel, location["name"], rel, content, f"Hours, fees, and accepted items at {location['name']}.")


def build_guide(guide: dict, locations_by_id: dict) -> None:
    sections = []
    for sec in guide.get("sections", []):
        paras = "".join(f"<p>{esc(p)}</p>" for p in sec.get("paragraphs", []))
        callout = ""
        if sec.get("callout"):
            callout = f'<div class="callout">{esc(sec["callout"])}</div>'
        sections.append(f"<h2>{esc(sec['heading'])}</h2>\n{paras}\n{callout}")
    related = []
    for lid in guide.get("related_location_ids", []):
        loc = locations_by_id.get(lid)
        if loc:
            related.append(location_card(loc, "h3"))
    sources = guide.get("sources") or []
    first = sources[0] if sources else {}
    content = f"""
<p class="kicker">{esc(guide["item_label"])} · {esc(guide["city"])}, {esc(guide["state"])}</p>
<h1>{esc(guide["h1"])}</h1>
<p class="dek">{esc(guide["dek"])}</p>
<div class="fact-grid">
  <article class="fact-card">
    <h2>Accepts</h2>
    <p>This guide covers {esc(guide["item_label"]).lower()} in {esc(guide["city"])}. Each related site below shows whether it takes the item, and whether there is a fee.</p>
  </article>
  <article class="fact-card">
    <h2>Fees</h2>
    <p>Fees vary by facility and sometimes by size. Read the site cards and confirm on the official page before you load the car.</p>
  </article>
  <article class="fact-card">
    <h2>Hours</h2>
    <p>Hours are listed on each related drop-off site. They change — check the official page for the day you plan to go.</p>
  </article>
  <article class="fact-card">
    <h2>Source</h2>
    <p>Last checked {esc(guide["last_checked"])}.</p>
    <p><a href="{esc(first.get("url") or href("about/"))}">{esc(first.get("title") or "Sources")}</a></p>
  </article>
</div>
{''.join(sections)}
<section data-filter-root data-filter-sync="off">
  <h2>Related drop-off sites</h2>
  <div class="filter-bar" role="search">
    <label for="guide-filter">Search these sites</label>
    <div class="filter-controls">
      <input id="guide-filter" type="search" data-filter-input placeholder="Name, city, or rule…">
    </div>
    <p class="filter-status" data-filter-status aria-live="polite"></p>
  </div>
  <div class="grid">{''.join(related)}</div>
  <p class="filter-empty callout" data-filter-empty>No related site matches that search.</p>
</section>
<section class="sources">
  <h2>Sources</h2>
  {source_list(sources)}
</section>
"""
    rel = guide["path"]
    write(SITE / rel, guide["title"], rel, content, guide["dek"])


def build_about(locations: list, guides: list) -> None:
    published = [g for g in guides if g["status"] == "published"]
    queued = [g for g in guides if g["status"] == "queued"]
    content = f"""
<p class="kicker">About this directory</p>
<h1>How Where to Take It is sourced</h1>
<p class="dek">This is a small, independent directory of official household drop-off sites. It is not a city, county, or state website, and it does not take appointments or fees.</p>
<h2>What gets published</h2>
<p>A page goes up only when the hours, fees, residency rules, and accepted-item list can be tied to a public official page, with a last-checked date. If a facility’s page does not mention an item, this site says “not listed” instead of guessing.</p>
<p>The first metro is Minneapolis–Saint Paul, because that is a place these rules can be checked carefully, site by site. Later pages add one city or one item at a time.</p>
<h2>What is on the site now</h2>
<p>{len(locations)} Twin Cities facilities and {len(published)} published item guide{'' if len(published)==1 else 's'}. {len(queued)} researched guide{'' if len(queued)==1 else 's'} {('is' if len(queued)==1 else 'are')} queued for a later nightly build.</p>
<ul class="facts">
  <li><a href="{href('metro/twin-cities/')}">Twin Cities drop-off listing</a></li>
  {''.join(f'<li><a href="{href(g["path"])}">{esc(g["title"])}</a></li>' for g in published)}
</ul>
<h2>Reuse of the data</h2>
<p>Facility facts are taken from public pages published by cities and counties. Those agencies own their information. This site’s write-ups, comparisons, and HTML are written here. If you reuse anything, keep the official source links and the “confirm before you go” warning.</p>
<h2>Corrections</h2>
<p>If a fee or hour is wrong, treat the official facility page as right. This project records the date it checked each source so stale pages can be fixed.</p>
"""
    write(SITE / "about/index.html", "About and sources", "about/index.html", content)


def build_all() -> dict:
    loc_data = load_json(DATA / "locations.json")
    guide_data = load_json(DATA / "guides.json")
    locations = loc_data["locations"]
    guides = guide_data["guides"]
    published = [g for g in guides if g.get("status") == "published"]
    locations_by_id = {loc["id"]: loc for loc in locations}

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    shutil.copy(TEMPLATES / "styles.css", SITE / "styles.css")
    shutil.copy(TEMPLATES / "search.js", SITE / "search.js")
    shutil.copy(TEMPLATES / "favicon.svg", SITE / "favicon.svg")
    # Harmless if a static host ever runs Jekyll on the output folder.
    (SITE / ".nojekyll").touch()

    build_home(locations, guides)
    build_listing(loc_data["region"], locations)
    for loc in locations:
        build_location(loc)
    for guide in published:
        build_guide(guide, locations_by_id)
    build_about(locations, guides)
    return {
        "locations": len(locations),
        "published_guides": [g["id"] for g in published],
        "queued_guides": [g["id"] for g in guides if g.get("status") == "queued"],
    }


def guide_is_complete(guide: dict) -> bool:
    if not guide.get("sections"):
        return False
    if not guide.get("path") or not guide.get("title") or not guide.get("dek"):
        return False
    if not guide.get("sources"):
        return False
    return all(sec.get("heading") and sec.get("paragraphs") for sec in guide["sections"])


def nightly() -> int:
    LOGS.mkdir(exist_ok=True)
    log_path = LOGS / "nightly.log"
    guide_data = load_json(DATA / "guides.json")
    queued = [g for g in guide_data["guides"] if g.get("status") == "queued"]
    if not queued:
        msg = f"{TODAY} no queued guide with complete data; nothing published"
        print(msg)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
        build_all()
        return 0

    chosen = None
    skipped = []
    for guide in queued:
        if guide_is_complete(guide):
            chosen = guide
            break
        skipped.append(guide["id"])

    if chosen is None:
        msg = f"{TODAY} queued guides are incomplete ({', '.join(skipped)}); add sourced sections before publishing"
        print(msg, file=sys.stderr)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
        return 1

    chosen["status"] = "published"
    chosen["published"] = TODAY
    chosen["last_checked"] = chosen.get("last_checked") or TODAY
    save_json(DATA / "guides.json", guide_data)
    summary = build_all()
    msg = f"{TODAY} published {chosen['id']} -> {chosen['path']}; site has {summary['locations']} locations and guides {', '.join(summary['published_guides'])}"
    print(msg)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Where to Take It")
    parser.add_argument("--nightly", action="store_true", help="Publish the next complete queued guide, then rebuild")
    parser.add_argument("--status", action="store_true", help="Print queue status and exit")
    args = parser.parse_args()
    if args.status:
        guide_data = load_json(DATA / "guides.json")
        for g in guide_data["guides"]:
            complete = "complete" if guide_is_complete(g) else "incomplete"
            print(f"{g['status']:10} {complete:11} {g['id']} ({g.get('path')})")
        queue = load_json(DATA / "queue.json")
        for item in queue.get("upcoming_research", []):
            print(f"{item['status']:10} {'n/a':11} {item['id']}")
        return 0
    if args.nightly:
        return nightly()
    summary = build_all()
    print(
        f"Built {summary['locations']} locations and {len(summary['published_guides'])} guide(s) into {SITE} (base {site_base() or '/'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
