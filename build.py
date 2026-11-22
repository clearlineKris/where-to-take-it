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


DEFAULT_BASE_PATH = "/where-to-take-it"


def site_base() -> str:
    """Public URL prefix. Default is the GitHub Pages project path.

    Override with SITE_BASE_PATH. Use an empty value to preview locally
    at the server root: SITE_BASE_PATH= python3 build.py
    """
    if "SITE_BASE_PATH" in os.environ:
        return os.environ["SITE_BASE_PATH"].rstrip("/")
    return DEFAULT_BASE_PATH.rstrip("/")


def href(path: str) -> str:
    """Root-relative URL so links work under /where-to-take-it/."""
    path = str(path).lstrip("/")
    base = site_base()
    return f"{base}/{path}" if base else f"/{path}"


def page_shell(title: str, path: str, content: str, description: str = "") -> str:
    desc = description or "Official drop-off hours, fees, and accepted items, checked against the city or county page."
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} — Where to Take It</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="stylesheet" href="{href('styles.css')}">
</head>
<body>
  <a class="skiplink" href="#content">Skip to content</a>
  <p class="disclaimer">This is an independent directory, not a government website. Hours and fees change — confirm with the facility before you go.</p>
  <header class="site">
    <div class="wrap brandrow">
      <a class="brand" href="{href('index.html')}">Where to Take It<span>Drop-off hours, fees, and what they actually accept</span></a>
      <nav aria-label="Primary">
        <a href="{href('index.html')}">Home</a>
        <a href="{href('metro/twin-cities/index.html')}">Twin Cities</a>
        <a href="{href('about/index.html')}">About &amp; sources</a>
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
      <p><a href="{href('about/index.html')}">How entries are sourced</a></p>
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


def location_card(location: dict, heading: str = "h2") -> str:
    loc_url = href(f"locations/{location['id']}/index.html")
    flags = location.get("item_flags", {})
    chips = " ".join(
        f'{flag_html(flags.get(key, "not_listed"))} <span class="addr">{esc(label)}</span>'
        for key, label in ITEM_COLUMNS
    )
    phone = f'<p>Phone: <span class="phone">{esc(location["phone"])}</span></p>' if location.get("phone") else ""
    return f"""
<article class="loc">
  <{heading}><a href="{loc_url}">{esc(location["name"])}</a></{heading}>
  <p class="addr">{esc(location["address"])}<br>{esc(location["agency"])}</p>
  {hours_html(location)}
  {phone}
  <p>{esc(location["residency"])}</p>
  <p>{chips}</p>
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
    content = f"""
<section class="hero">
  <div>
    <p class="kicker">A practical drop-off directory</p>
    <h1>Find the place that will actually take the thing in your trunk.</h1>
    <p class="dek">People search every day for where to drop off paint, mattresses, batteries, TVs, tires, and used oil. This site answers with official hours, fees, residency rules, and the “do not bring” list — copied from the city or county page and dated.</p>
    <p><a href="{href('metro/twin-cities/index.html')}">Browse Twin Cities drop-off sites</a> · <a href="{href('mn/minneapolis/mattress/index.html')}">Where to take a mattress in Minneapolis</a></p>
  </div>
  <aside class="callout plain">
    <p class="kicker">First metro</p>
    <h2>Minneapolis–Saint Paul</h2>
    <p>Six official city and county sites, with a comparison of who takes mattresses, paint, TVs, tires, appliances, batteries, and used oil.</p>
    <p><a href="{href('metro/twin-cities/index.html')}">Open the Twin Cities listing</a></p>
  </aside>
</section>
<section>
  <h2>Useful pages</h2>
  <div class="grid">{''.join(guide_cards)}</div>
</section>
<section>
  <h2>Featured locations</h2>
  <div class="grid">{loc_preview}</div>
  <p><a href="{href('metro/twin-cities/index.html')}">See all Twin Cities sites</a></p>
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


def build_listing(region: dict, locations: list) -> None:
    rows = []
    for loc in locations:
        flags = loc.get("item_flags", {})
        cells = "".join(f"<td>{flag_html(flags.get(key, 'not_listed'))}</td>" for key, _ in ITEM_COLUMNS)
        rows.append(
            f'<tr><th scope="row"><a href="{href(f"locations/{loc['id']}/index.html")}">{esc(loc["name"])}</a><br><span class="addr">{esc(loc["city"])}</span></th>{cells}</tr>'
        )
    head = "".join(f"<th>{esc(label)}</th>" for _, label in ITEM_COLUMNS)
    cards = "\n".join(location_card(loc, "h2") for loc in locations)
    content = f"""
<p class="kicker">{esc(region["state"])} metro listing</p>
<h1>{esc(region["name"])} drop-off sites</h1>
<p class="dek">{esc(region["summary"])}</p>
<p class="meta">{len(locations)} facilities checked November 20, 2026. The seven-county metro, as used by several of these sites, is {esc(", ".join(region["seven_county"]))}.</p>
<h2>What each site takes</h2>
<p>Green means the official page says they take it. Gold means there is a fee or a confirmation gap. Red means the official page says no, or the item is not part of that facility’s job (for example, a hazardous-waste site that does not take mattresses).</p>
<table>
  <thead><tr><th>Site</th>{head}</tr></thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
<p class="meta">“Likely” or “not listed” is not a yes. Call or read the official page before you load the car.</p>
<h2>The facilities</h2>
{cards}
<section class="sources">
  <h2>Sources</h2>
  <p>Each card links to the official page used for that listing. See also the <a href="{href('about/index.html')}">about page</a>.</p>
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
    chips = " ".join(
        f'{flag_html(flags.get(key, "not_listed"))} <span style="margin-right:0.7rem">{esc(label)}</span>'
        for key, label in ITEM_COLUMNS
    )
    content = f"""
<p class="kicker">{esc(location["city"])}, {esc(location["state"])}</p>
<h1>{esc(location["name"])}</h1>
<p class="dek">{esc(location["agency"])} · {esc(location["address"])}</p>
<p class="meta">Last checked {esc(location["last_checked"])}. <a href="{esc(location["website"])}">Official page</a></p>
<p>{chips}</p>
<h2>Hours</h2>
{hours_html(location)}
<h2>Who can use it</h2>
<p>{esc(location["residency"])}</p>
{"<p>Proof of residency is required.</p>" if location.get("proof_required") else ""}
<p>Phone: <span class="phone">{esc(location.get("phone") or "See official page")}</span></p>
{email}
{appt}
<h2>Fees</h2>
{bullets(location.get("fees", []))}
<h2>Accepted</h2>
{bullets(location.get("accepts", []))}
<h2>Not accepted</h2>
{bullets(location.get("does_not_accept", []))}
<h2>Notes</h2>
{bullets(location.get("notes", []))}
<section class="sources">
  <h2>Sources</h2>
  {sources}
</section>
<p><a href="{href('metro/twin-cities/index.html')}">Back to the Twin Cities listing</a></p>
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
    content = f"""
<p class="kicker">{esc(guide["item_label"])} · {esc(guide["city"])}, {esc(guide["state"])}</p>
<h1>{esc(guide["h1"])}</h1>
<p class="dek">{esc(guide["dek"])}</p>
<p class="meta">Last checked {esc(guide["last_checked"])}.</p>
{''.join(sections)}
<h2>Related drop-off sites</h2>
<div class="grid">{''.join(related)}</div>
<section class="sources">
  <h2>Sources</h2>
  {source_list(guide.get("sources", []))}
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
  <li><a href="{href('metro/twin-cities/index.html')}">Twin Cities drop-off listing</a></li>
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
