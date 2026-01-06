#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape as xml_escape

try:
    import markdown  # pip install markdown
except ImportError:
    markdown = None

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "briefings"
OUT = ROOT / "publish" / "site"
ARCHIVE = OUT / "briefings"
ABOUT_SRC = ROOT / "about" / "index.md"

# Canonical URL for RSS links.
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
    return "RegLag Daily Briefing"

def format_spelled_date(dt: datetime) -> str:
    # Cross-platform “January 6, 2026” (no leading zero).
    return dt.strftime("%B %d, %Y").replace(" 0", " ")

def build_rss(items: list[tuple[str, str]], *, site_url: str) -> str:
    """
    items: list of (date_str 'YYYY-MM-DD', title) in reverse chronological order
    """
    channel_title = "RegLag — Daily Financial Regulatory Briefing"
    channel_desc = "RegLag is a daily briefing providing fast, source-based analysis of financial regulatory and policy developments, with forward-looking context."
    

    now = format_datetime(datetime.now(timezone.utc))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{xml_escape(channel_title)}</title>",
        f"    <link>{xml_escape(channel_link)}</link>",
        f"    <description>{xml_escape(channel_desc)}</description>",
        f"    <lastBuildDate>{now}</lastBuildDate>",
        f'    <atom:link href="{xml_escape(site_url + "/rss.xml")}" rel="self" type="application/rss+xml" />',
    ]

    for date_str, title in items:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        pub = format_datetime(dt)
        url = f"{site_url}/briefings/{date_str}.html"
        rss_title = title or f"RegLag Daily Briefing — {format_spelled_date(dt)}"
        lines += [
            "    <item>",
            f"      <title>{xml_escape(rss_title)}</title>",
            f"      <link>{xml_escape(url)}</link>",
            f"      <guid isPermaLink=\"true\">{xml_escape(url)}</guid>",
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
  <title>RegLag - Daily Financial Regulatory Briefing - {title}</title>

  <!-- RSS -->
  <link rel="alternate" type="application/rss+xml" title="RegLag RSS" href="/rss.xml" />

  <style>
    :root {{
      --bg: #ffffff;
      --text-primary: #111111;
      --text-secondary: #555555;
      --text-muted: #777777;
      --divider: #e5e5e5;
      --accent: #243447;
      --accent-muted: #4a5a6a;
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
      text-rendering: optimizeLegibility;
      -webkit-font-smoothing: antialiased;
    }}

    .wrap {{
      max-width: 820px;
      margin: 0 auto;
      padding: 28px 18px 64px;
    }}

    .masthead-description{ {
        font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
        font-size: 12px;
        color: var(--text-secondary);
        margin-top: 2px;
    }}

    .masthead-title {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 14px;
      letter-spacing: 0.08em;
      font-weight: 600;
      color: var(--accent);
    }}

    .masthead-subtitle {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 12px;
      color: var(--text-secondary);
      margin-top: 2px;
    }}

    hr {{
      border: none;
      border-top: 1px solid var(--divider);
      margin: 16px 0 28px;
    }}

    /* Top navigation under masthead */
    .top-nav {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 13px;
      color: var(--text-secondary);
      margin: -8px 0 24px;
    }}

    .top-nav a {{
      color: inherit;
      text-decoration: none;
    }}

    .top-nav a:hover {{
      text-decoration: underline;
      color: var(--link-hover);
    }}

    h1 {{
      font-size: 26px;
      line-height: 1.25;
      margin: 0 0 14px;
    }}

    h2 {{
      margin-top: 32px;
      line-height: 1.25;
    }}

    h3 {{
      margin-top: 22px;
      line-height: 1.25;
    }}

    p {{
      margin: 0 0 14px;
    }}

    ul, ol {{
      margin: 0 0 14px 1.1em;
      padding: 0;
    }}

    li {{
      margin: 0 0 6px;
    }}

    a {{
      color: var(--link);
      text-decoration: none;
    }}

    a:hover {{
      text-decoration: underline;
      color: var(--link-hover);
    }}

    .site-footer {{
      margin-top: 48px;
    }}

    .footer-nav {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 13px;
      color: var(--text-secondary);
    }}

    .footer-disclaimer {{
      margin-top: 12px;
      font-size: 12px;
      color: var(--text-muted);
    }}

    @media (max-width: 520px) {{
      body {{ font-size: 16px; line-height: 1.68; }}
      h1 {{ font-size: 22px; }}
      .wrap {{ padding: 22px 16px 56px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="masthead-title">REGLAG</div>
      <div class="masthead-subtitle">Daily Financial Regulatory Briefing</div>
              <div class="masthead-description">RegLag is a daily briefing providing fast, source-based analysis of financial regulatory and policy developments, with forward-looking context.</div>
      <hr />
      <nav class="top-nav">
        <a href="/">Latest</a> ·
        <a href="/briefings/index.html">Archive</a> ·
        <a href="/about/index.html">About</a> ·
        <a href="/rss.xml">RSS</a> ·
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
        <a href="/about/index.html">About</a> ·
        <a href="/rss.xml">RSS</a> ·
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

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ARCHIVE.mkdir(parents=True, exist_ok=True)

    md_files = sorted([p for p in SRC.glob("*.md") if p.name[:10].count("-") == 2], reverse=True)
    md_files = [p for p in md_files if len(p.stem) == 10]  # YYYY-MM-DD
    if not md_files:
        print("No briefings found in ./briefings")
        return 0

    archive_items: list[tuple[str, str]] = []

    # Build briefing pages
    for p in md_files:
        md_text = p.read_text(encoding="utf-8")
        title = extract_title(md_text)
        body = md_to_html(md_text)
        html = HTML.format(title=title, body=body)
        out_path = ARCHIVE / f"{p.stem}.html"
        out_path.write_text(html, encoding="utf-8")
        archive_items.append((p.stem, title))

    # Latest as homepage
    latest = md_files[0].stem
    (OUT / "index.html").write_text(
        (ARCHIVE / f"{latest}.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    # Archive index (clickable)
    archive_html = "<h1>Briefing Archive</h1>"
    current_month = None

    for date_str, title in archive_items:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        month_label = dt.strftime("%B %Y")

        if month_label != current_month:
            archive_html += f"<h2>{month_label}</h2>"
            current_month = month_label

        archive_html += (
            f'<p><a href="/briefings/{date_str}.html">'
            f"<strong>{format_spelled_date(dt)}</strong><br />"
            f"<em>{title}</em>"
            "</a></p>"
        )

    (ARCHIVE / "index.html").write_text(
        HTML.format(title="Briefing Archive — RegLag", body=archive_html),
        encoding="utf-8",
    )

    # About page
    if ABOUT_SRC.exists():
        about_html = md_to_html(ABOUT_SRC.read_text(encoding="utf-8"))
        about_out = OUT / "about"
        about_out.mkdir(parents=True, exist_ok=True)
        (about_out / "index.html").write_text(
            HTML.format(title="About — RegLag", body=about_html),
            encoding="utf-8",
        )

    # RSS feed (latest first)
    rss = build_rss(archive_items[:50], site_url=SITE_URL)
    (OUT / "rss.xml").write_text(rss, encoding="utf-8")
    (OUT / "feed.xml").write_text(rss, encoding="utf-8")

    print(f"Built {len(md_files)} briefings. Latest: {latest}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
