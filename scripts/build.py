#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape as xml_escape
import re
import shutil

from urllib.parse import urljoin
try:
    import markdown  # pip install markdown
except ImportError:
    markdown = None

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "briefings"
OUT = ROOT / "publish" / "site"
ARCHIVE = OUT / "briefings"
ABOUT_SRC = ROOT / "about" / "index.md"
PORTFOLIO_SRC = ROOT / "portfolio" / "index.md"
ASSETS_SRC = ROOT / "assets"
ASSETS_OUT = OUT / "assets"

SITE_URL = "https://reglag.com"

def md_to_html(text: str) -> str:
    if markdown is None:
        esc = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        paras = "".join(f"<p>{p.strip()}</p>" for p in esc.split("\n\n") if p.strip())
        return paras
    return markdown.markdown(text, extensions=["fenced_code", "tables"])


def extract_title(md_text: str) -> str:
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "RegLag"


def format_spelled_date(dt: datetime) -> str:
    return dt.strftime("%B %d, %Y").replace(" 0", " ")

POST_TYPE_ALIASES = {
    "daily briefing": "Daily Briefing",
    "weekend deep dive": "Weekend Deep Dive",
    "deep dive": "Weekend Deep Dive",
    "weekend edition": "Weekend Deep Dive",
}

H2_RE = re.compile(r"^\s*##\s+(.+?)\s*$", re.MULTILINE)

def extract_first_h2(md_text: str) -> str | None:
    m = H2_RE.search(md_text)
    return m.group(1).strip() if m else None


def normalize_post_type(h2: str | None) -> str | None:
    if not h2:
        return None
    return POST_TYPE_ALIASES.get(h2.strip().lower())


def infer_post_type_from_date(dt: datetime) -> str:
    return "Weekend Deep Dive" if dt.weekday() >= 5 else "Daily Briefing"


def insert_post_type_after_h1(body_html: str, post_type: str) -> str:
    tag = f'<h3 class="post-type">{xml_escape(post_type)}</h3>'
    if "</h1>" in body_html:
        return body_html.replace("</h1>", "</h1>\n" + tag, 1)
    return tag + "\n" + body_html


def build_rss(items: list[tuple[str, str, str]], *, site_url: str) -> str:
    channel_title = "RegLag — Daily Financial Regulatory Briefing"
    channel_desc = "A daily financial regulatory briefing providing neutral, source-based insights. Informational only."
    now = format_datetime(datetime.now(timezone.utc))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{xml_escape(channel_title)}</title>",
        f"    <link>{xml_escape(site_url)}</link>",
        f"    <description>{xml_escape(channel_desc)}</description>",
        f"    <lastBuildDate>{now}</lastBuildDate>",
        f'    <atom:link href="{xml_escape(site_url + "/rss.xml")}" rel="self" type="application/rss+xml" />',
    ]

    for date_str, post_type, title in items:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        pub = format_datetime(dt)
        url = f"{site_url}/briefings/{date_str}.html"
        rss_title = f"{post_type} — {title}"
        lines += [
            "    <item>",
            f"      <title>{xml_escape(rss_title)}</title>",
            f"      <link>{xml_escape(url)}</link>",
            f'      <guid isPermaLink="true">{xml_escape(url)}</guid>',
            f"      <pubDate>{pub}</pubDate>",
            "    </item>",
        ]

    lines += ["  </channel>", "</rss>"]
    return "\n".join(lines) + "\n"


def build_sitemap_from_output(*, site_url: str, out_dir: Path, include_about: bool, include_portfolio: bool) -> str:
    build_date = datetime.now(timezone.utc).date().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    def add(loc: str, lastmod: str) -> None:
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_escape(loc)}</loc>")
        lines.append(f"    <lastmod>{xml_escape(lastmod)}</lastmod>")
        lines.append("  </url>")

    add(f"{site_url}/", build_date)
    add(f"{site_url}/briefings/", build_date)

    briefings_dir = out_dir / "briefings"
    if briefings_dir.exists():
        for p in sorted(briefings_dir.glob("*.html")):
            if p.name == "index.html":
                continue
            date_str = p.stem
            add(f"{site_url}/briefings/{p.name}", date_str)

    if include_about:
        add(f"{site_url}/about/", build_date)
    if include_portfolio:
        add(f"{site_url}/portfolio/", build_date)

    lines.append("</urlset>")
    return "\n".join(lines) + "\n"

# HTML template and main() unchanged from your version
