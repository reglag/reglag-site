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

# Canonical URL for RSS links.
SITE_URL = "https://reglag.com"

# -----------------------------
# Markdown helpers
# -----------------------------
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
    # First H1 (# ...)
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "RegLag"


def format_spelled_date(dt: datetime) -> str:
    # Cross-platform “January 6, 2026” (no leading zero).
    return dt.strftime("%B %d, %Y").replace(" 0", " ")


# -----------------------------
# Post type extraction (SOURCE OF TRUTH = first H2)
# -----------------------------
POST_TYPE_ALIASES: dict[str, str] = {
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
    key = h2.strip().lower()
    return POST_TYPE_ALIASES.get(key)


def infer_post_type_from_date(dt: datetime) -> str:
    # Saturday (5) / Sunday (6)
    return "Weekend Deep Dive" if dt.weekday() >= 5 else "Daily Briefing"


def insert_post_type_after_h1(body_html: str, post_type: str) -> str:
    """
    Insert a styled post-type subheading immediately after the first <h1>...</h1>.
    If no <h1> exists, prepend it at the top.
    """
    tag = f'<h3 class="post-type">{xml_escape(post_type)}</h3>'
    if "</h1>" in body_html:
        return body_html.replace("</h1>", "</h1>\n" + tag, 1)
    return tag + "\n" + body_html


# -----------------------------
# RSS generation (optional: includes post_type prefix)
# -----------------------------
def build_rss(items: list[tuple[str, str, str]], *, site_url: str) -> str:
    """
    items: list of (date_str 'YYYY-MM-DD', post_type, title) in reverse chronological order
    """
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



def build_sitemap(
    *,
    site_url: str,
    archive_items: list[tuple[str, str, str]],
    include_about: bool,
    include_portfolio: bool,
) -> str:
    """Deterministic sitemap.xml for RegLag.

    Includes:
      - Homepage
      - Briefings archive index
      - Each briefing HTML page
      - About + Portfolio pages (if present)

    Notes:
      - This is a pure transport/structure artifact (no editorial influence).
      - Uses build date for static pages; uses briefing date for briefing pages.
    """

    def abs_url(path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return urljoin(site_url.rstrip("/") + "/", path.lstrip("/"))

    build_date = datetime.now(timezone.utc).date().isoformat()

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    # Homepage
    lines += [
        "  <url>",
        f"    <loc>{xml_escape(abs_url('/'))}</loc>",
        f"    <lastmod>{build_date}</lastmod>",
        "  </url>",
    ]

    # Archive index
    lines += [
        "  <url>",
        f"    <loc>{xml_escape(abs_url('/briefings/'))}</loc>",
        f"    <lastmod>{build_date}</lastmod>",
        "  </url>",
    ]

    # Optional pages
    if include_about:
        lines += [
            "  <url>",
            f"    <loc>{xml_escape(abs_url('/about/'))}</loc>",
            f"    <lastmod>{build_date}</lastmod>",
            "  </url>",
        ]
    if include_portfolio:
        lines += [
            "  <url>",
            f"    <loc>{xml_escape(abs_url('/portfolio/'))}</loc>",
            f"    <lastmod>{build_date}</lastmod>",
            "  </url>",
        ]

    # Briefings: lastmod = briefing date (already YYYY-MM-DD)
    for date_str, _post_type, _title in archive_items:
        lines += [
            "  <url>",
            f"    <loc>{xml_escape(abs_url(f'/briefings/{date_str}.html'))}</loc>",
            f"    <lastmod>{xml_escape(date_str)}</lastmod>",
            "  </url>",
        ]

    lines.append("</urlset>")
    return "\n".join(lines) + "\n"



# -----------------------------
# HTML template
# -----------------------------
HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RegLag — Daily Financial Regulatory Briefing — {title}</title>

  <!-- Canonical -->
  <link rel="canonical" href="{canonical_url}" />

  <!-- Open Graph -->
  <meta property="og:site_name" content="RegLag" />
  <meta property="og:title" content="RegLag — {title}" />
  <meta property="og:url" content="{canonical_url}" />

  <!-- RSS -->
  <link rel="alternate" type="application/rss+xml" title="RegLag RSS" href="/rss.xml" />

  <!-- Icons -->
  <link rel="icon" href="/favicon.ico" />
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/icons/favicon-32.png" />
  <link rel="icon" type="image/png" sizes="16x16" href="/assets/icons/favicon-16.png" />
  <link rel="apple-touch-icon" sizes="180x180" href="/assets/icons/apple-touch-icon.png" />

  <!-- 100% privacy-first analytics -->
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
      text-rendering: optimizeLegibility;
      -webkit-font-smoothing: antialiased;
    }}

    .wrap {{
      max-width: 820px;
      margin: 0 auto;
      padding: 28px 22px 60px;
    }}

    .masthead-title {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 14px;
      letter-spacing: 0.08em;
      font-weight: 600;
      color: var(--accent);
    }}

    .masthead-title a {{
      color: inherit;
      text-decoration: none;
    }}

    .masthead-title a:hover {{
      text-decoration: none;
    }}

    .masthead-title .brand {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
    }}

    .brand-mark {{
      display: block;
      width: 28px;
      height: 28px;
    }}

    .masthead-subtitle {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 12px;
      color: var(--text-secondary);
      margin-top: 2px;
    }}

    .masthead-description {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 12px;
      color: var(--text-secondary);
      margin-top: 4px;
      font-style: italic;
    }}

    hr {{
      border: none;
      border-top: 1px solid var(--divider);
      margin: 16px 0 28px;
    }}

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

    /* Key: post type should look like a subheading, not a headline */
    .post-type {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 14px;
      font-weight: 600;
      color: var(--text-secondary);
      margin: 10px 0 6px;
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
      .post-type {{ font-size: 13px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="masthead-title">
        <a class="brand" href="/">
          <img
            src="/assets/logo/reglag-mark-128-tight.png"
            alt="RegLag"
            class="brand-mark"
            width="28"
            height="28"
            decoding="async"
          />
          <span>REGLAG</span>
        </a>
      </div>
      <div class="masthead-subtitle">Daily Financial Regulatory Briefing</div>
      <div class="masthead-description">RegLag is a daily briefing providing fast, source-based insights of financial regulatory and policy developments on weekdays, with weekend deep dives into enforcement, market structure, and regulatory mechanisms.</div>
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


# -----------------------------
# Main build
# -----------------------------
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ARCHIVE.mkdir(parents=True, exist_ok=True)

    # Copy static assets (logo + icons) into the published site root.
    if ASSETS_SRC.exists():
        if ASSETS_OUT.exists():
            shutil.rmtree(ASSETS_OUT)
        shutil.copytree(ASSETS_SRC, ASSETS_OUT)

    # Copy root favicon for Safari compatibility
    root_favicon_src = ASSETS_SRC / "icons" / "favicon.ico"
    root_favicon_out = OUT / "favicon.ico"
    if root_favicon_src.exists():
        shutil.copyfile(root_favicon_src, root_favicon_out)
    
    md_files = sorted(
        [p for p in SRC.glob("*.md") if re.match(r"^\d{4}-\d{2}-\d{2}\.md$", p.name)],
        reverse=True,
    )

    if not md_files:
        print("No briefings found in ./briefings")
        return 0

    archive_items: list[tuple[str, str, str]] = []  # (date_str, post_type, title)

    for p in md_files:
        md_text = p.read_text(encoding="utf-8")
        title = extract_title(md_text)

        dt = datetime.strptime(p.stem, "%Y-%m-%d")
        raw_h2 = extract_first_h2(md_text)
        normalized = normalize_post_type(raw_h2)

        # If the first H2 is one of our recognized post-type markers,
        # remove it from the markdown body (so it does not render as a big H2).
        if normalized:
            post_type = normalized
            md_body = H2_RE.sub("", md_text, count=1).lstrip()
        else:
            post_type = infer_post_type_from_date(dt)
            md_body = md_text

        body_html = md_to_html(md_body)
        body_html = insert_post_type_after_h1(body_html, post_type)

        canonical_url = f"{SITE_URL}/briefings/{p.stem}.html"
        html = HTML.format(title=title, body=body_html, canonical_url=canonical_url)
        out_path = ARCHIVE / f"{p.stem}.html"
        out_path.write_text(html, encoding="utf-8")

        # --- Chart of the Day assets (daily briefings only) ---
        day_dir = SRC / p.stem  # e.g. briefings/2026-01-10/
        if day_dir.exists() and day_dir.is_dir():
            chart_png = day_dir / "chart.png"
            chart_json = day_dir / "chart.json"

            # If a chart is present, require metadata and copy the whole folder to output
            if chart_png.exists():
                if not chart_json.exists():
                    raise SystemExit(f"Missing chart.json for {p.stem} (found chart.png)")

                out_day_dir = ARCHIVE / p.stem  # dist/briefings/2026-01-10/
                if out_day_dir.exists():
                    shutil.rmtree(out_day_dir)
                shutil.copytree(day_dir, out_day_dir)

        archive_items.append((p.stem, post_type, title))

    # Latest as homepage (canonical is site root)
    latest_file = md_files[0]
    latest = latest_file.stem
    latest_md = latest_file.read_text(encoding="utf-8")
    latest_title = extract_title(latest_md)

    dt = datetime.strptime(latest, "%Y-%m-%d")
    raw_h2 = extract_first_h2(latest_md)
    normalized = normalize_post_type(raw_h2)
    if normalized:
        post_type = normalized
        md_body = H2_RE.sub("", latest_md, count=1).lstrip()
    else:
        post_type = infer_post_type_from_date(dt)
        md_body = latest_md

    home_body_html = md_to_html(md_body)
    home_body_html = insert_post_type_after_h1(home_body_html, post_type)
    home_html = HTML.format(
        title=latest_title,
        body=home_body_html,
        canonical_url=f"{SITE_URL}/",
    )
    (OUT / "index.html").write_text(home_html, encoding="utf-8")

    # Archive index (clickable + labeled)
    archive_html = "<h1>Briefing Archive</h1>"
    current_month = None

    for date_str, post_type, title in archive_items:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        month_label = dt.strftime("%B %Y")

        if month_label != current_month:
            archive_html += f"<h3>{month_label}</h3>"
            current_month = month_label

        prefix = f"{format_spelled_date(dt)} — {post_type} — "
        display_html = f'{xml_escape(prefix)}<em>{xml_escape(title)}</em>'
        url = f"/briefings/{date_str}.html"
        archive_html += f'<p><a href="{url}">{display_html}</a></p>'

    (ARCHIVE / "index.html").write_text(
        HTML.format(title="Briefing Archive", body=archive_html, canonical_url=f"{SITE_URL}/briefings/"),
        encoding="utf-8",
    )

    # About page
    if ABOUT_SRC.exists():
        about_html = md_to_html(ABOUT_SRC.read_text(encoding="utf-8"))
        about_out = OUT / "about"
        about_out.mkdir(parents=True, exist_ok=True)
        (about_out / "index.html").write_text(
            HTML.format(title="About", body=about_html, canonical_url=f"{SITE_URL}/about/"),
            encoding="utf-8",
        )

    # Portfolio page
    if PORTFOLIO_SRC.exists():
        portfolio_html = md_to_html(PORTFOLIO_SRC.read_text(encoding="utf-8"))
        portfolio_out = OUT / "portfolio"
        portfolio_out.mkdir(parents=True, exist_ok=True)
        (portfolio_out / "index.html").write_text(
            HTML.format(title="RegLag Model Portfolio", body=portfolio_html, canonical_url=f"{SITE_URL}/portfolio/"),
            encoding="utf-8",
        )

    # RSS feed (latest first, with post_type prefix)
    rss = build_rss(archive_items[:50], site_url=SITE_URL)
    (OUT / "rss.xml").write_text(rss, encoding="utf-8")
    (OUT / "feed.xml").write_text(rss, encoding="utf-8")

    # Sitemap (root-level)
    sitemap = build_sitemap(
        site_url=SITE_URL,
        archive_items=archive_items,
        include_about=ABOUT_SRC.exists(),
        include_portfolio=PORTFOLIO_SRC.exists(),
    )
    (OUT / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    print(f"Built {len(md_files)} briefings. Latest: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
