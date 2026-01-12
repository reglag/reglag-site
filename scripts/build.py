#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape as xml_escape
import re
import shutil

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


def build_rss(items, *, site_url: str) -> str:
    channel_title = "RegLag — Daily Financial Regulatory Briefing"
    channel_desc = (
        "A daily financial regulatory briefing providing neutral, source-based insights. "
        "Informational only."
    )

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


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RegLag — Daily Financial Regulatory Briefing — {title}</title>

  <link rel="canonical" href="{canonical_url}" />
  <meta property="og:site_name" content="RegLag" />
  <meta property="og:title" content="RegLag — {title}" />
  <meta property="og:url" content="{canonical_url}" />

  <link rel="alternate" type="application/rss+xml" title="RegLag RSS" href="/rss.xml" />

  <link rel="icon" href="/favicon.ico" />
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/icons/favicon-32.png" />
  <link rel="icon" type="image/png" sizes="16x16" href="/assets/icons/favicon-16.png" />
  <link rel="apple-touch-icon" sizes="180x180" href="/assets/icons/apple-touch-icon.png" />

  <script async src="https://scripts.simpleanalyticscdn.com/latest.js"></script>

  <style>
    :root {{
      --bg: #ffffff;
      --text-primary: #111111;
      --text-secondary: #555555;
      --text-muted: #777777;
      --divider: #e5e5e5;
      --accent: #243447;
      --link: #243447;
      --link-hover: #111111;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text-primary);
      font-family: Georgia, "Source Serif 4", serif;
      font-size: 17px;
      line-height: 1.62;
    }}
    .wrap {{
      max-width: 820px;
      margin: 0 auto;
      padding: 28px 22px 60px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="masthead-title">
        <a class="brand" href="/">
          <img src="/assets/logo/reglag-mark-128-tight.png" alt="RegLag" width="28" height="28" />
          <span>REGLAG</span>
        </a>
      </div>
      <div class="masthead-subtitle">Daily Financial Regulatory Briefing</div>
      <div class="masthead-description">
        RegLag is a daily briefing providing fast, source-based insights of financial regulatory and policy developments on weekdays, with weekend deep dives into enforcement, market structure, and regulatory mechanisms.
      </div>
      <hr />
      <nav class="top-nav">
        <a href="/">Latest</a> ·
        <a href="/briefings/index.html">Archive</a> ·
        <a href="/portfolio/index.html">Portfolio</a> ·
        <a href="/about/index.html">About</a> ·
        <a href="mailto:contact@reglag.com">Contact</a>
      </nav>
    </header>

    <main>
      {body}
    </main>

    <footer class="site-footer">
      <hr />
      <nav class="footer-nav">
        <a href="/">Latest</a> ·
        <a href="/briefings/index.html">Archive</a> ·
        <a href="/portfolio/index.html">Portfolio</a> ·
        <a href="/about/index.html">About</a> ·
        <a href="/rss.xml">RSS</a> ·
        <a href="https://x.com/reglag_hq" rel="me noopener" target="_blank">X</a> ·
        <a href="mailto:contact@reglag.com">Contact</a>
      </nav>
      <div class="footer-disclaimer">
        Informational only. Not legal, financial, or compliance advice.
      </div>
    </footer>
  </div>
</body>
</html>
"""
