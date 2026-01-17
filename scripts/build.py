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
SUBSCRIBE_SRC = ROOT / "subscribe" / "index.md"
LEGAL_SRC = ROOT / "legal" / "index.md"
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

def inject_post_type_label_md(md_body: str, post_type: str) -> str:
    # Insert the visible post-type label as raw HTML so ordering is deterministic.
    # Desired order:
    #   1) H1 title
    #   2) Optional italic subtitle line (single-line *...*)
    #   3) Post type label
    #   4) Date line (single-line *Month Day, Year*)

    lines = md_body.splitlines()
    # Find first H1
    h1_idx = None
    for i, line in enumerate(lines):
        if line.startswith('# '):
            h1_idx = i
            break
    if h1_idx is None:
        return md_body

    def looks_like_date(line: str) -> bool:
        s = line.strip()
        # Expect single-line italic wrapper: *January 16, 2026* or *2026-01-16*
        if not (s.startswith('*') and s.endswith('*') and len(s) >= 3):
            return False
        inner = s[1:-1].strip()
        month = r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        return bool(re.fullmatch(rf'{month} \d{{1,2}}, \d{{4}}', inner)) or bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', inner))

    def is_italic_line(line: str) -> bool:
        s = line.strip()
        return s.startswith('*') and s.endswith('*') and len(s) >= 3

    # Determine insertion point after H1 and optional subtitle.
    j = h1_idx + 1
    # Skip blank lines
    while j < len(lines) and lines[j].strip() == '':
        j += 1

    insert_at = None

    # Case A: First nonblank line is an italic line.
    if j < len(lines) and is_italic_line(lines[j]):
        # If it looks like a date, there is no subtitle; insert BEFORE date.
        if looks_like_date(lines[j]):
            insert_at = j
        else:
            # Treat as subtitle; look for next nonblank line.
            k = j + 1
            while k < len(lines) and lines[k].strip() == '':
                k += 1
            # If next italic looks like a date, insert before it; else insert after subtitle block.
            if k < len(lines) and looks_like_date(lines[k]):
                insert_at = k
            else:
                insert_at = j + 1
    else:
        # No italic line immediately after title; insert right after title block.
        insert_at = j

    label_html = f'<h3 class="post-type">{xml_escape(post_type)}</h3>'
    lines.insert(insert_at, label_html)
    return "\n".join(lines)




def inject_pdf_link_md(md_body: str, date_str: str) -> str:
    """Insert a small 'Download PDF' link near the top of the briefing.

    Preferred placement: immediately after the first italic date line (*Month Day, Year*).
    Fallbacks: after the post-type label HTML; then after the first H1.
    """
    pdf_html = f'<p class="pdf-link"><a href="/briefings/{date_str}.pdf">Download PDF</a></p>'

    lines = md_body.splitlines()

    def is_italic_line(line: str) -> bool:
        s = line.strip()
        return s.startswith('*') and s.endswith('*') and len(s) >= 3

    def is_date_italic(line: str) -> bool:
        inner = line.strip()[1:-1].strip()
        months = ("January|February|March|April|May|June|July|August|September|October|November|December")
        return bool(re.fullmatch(rf"({months}) \d{{1,2}}, \d{{4}}", inner)) or bool(re.fullmatch(r"\d{{4}}-\d{{2}}-\d{{2}}", inner))

    for i, line in enumerate(lines):
        if is_italic_line(line) and is_date_italic(line):
            lines.insert(i + 1, pdf_html)
            return "\n".join(lines)

    for i, line in enumerate(lines):
        if 'class="post-type"' in line:
            lines.insert(i + 1, pdf_html)
            return "\n".join(lines)

    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines.insert(i + 1, "")
            lines.insert(i + 2, pdf_html)
            return "\n".join(lines)

    return md_body


# -----------------------------
# RSS generation (optional: includes post_type prefix)
# -----------------------------
def build_rss(items: list[tuple[str, str, str]], *, site_url: str) -> str:
    """
    items: list of (date_str 'YYYY-MM-DD', post_type, title) in reverse chronological order
    """
    channel_title = "RegLag — Daily Financial Regulatory Briefing"
    channel_desc = (
        "RegLag is a financial regulatory briefing focused on source-based interpretation of regulatory, policy, and market-structure developments, with weekday coverage and weekend deep dives into enforcement and regulatory mechanisms."
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

  <!-- Structured data (Organization) -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "RegLag",
    "url": "https://reglag.com",
    "logo": "https://reglag.com/assets/logo/reglag-mark-128-tight.png"
  }}
  </script>

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

    .portfolio-disclaimer {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 13px;
      color: var(--text-secondary);
      margin: 6px 0 8px;
    }}

    .portfolio-disclaimer-sub {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 12px;
      color: var(--text-muted);
      margin: 0 0 18px;
    }}

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
    .footer-meta {{
      margin-top: 12px;
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 12px;
      color: var(--text-secondary);
    }}

    .footer-meta-line {{
      margin-top: 4px;
    }}

    .footer-meta-muted {{
      font-size: 11px;
      color: var(--text-muted);
    }}

    .footer-disclaimer {{
      margin-top: 12px;
      font-size: 12px;
      color: var(--text-muted);
    }}


    .pdf-link {{
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 12px;
      color: var(--text-secondary);
      margin: 8px 0 18px;
    }}

    .pdf-link a {{
      color: inherit;
      text-decoration: none;
    }}

    .pdf-link a:hover {{
      text-decoration: underline;
      color: var(--link-hover);
    }}


    @media print {{

      /* Align PDF body column to physical page margins (not centered web layout) */
      .wrap {{
        max-width: none !important;
        margin: 0 !important;
        padding: 0 !important;
      }}

      /* Keep headings with first content block to avoid orphan headings */
      h2, h3 {{
        break-after: avoid-page;
        page-break-after: avoid;
        break-inside: avoid;
        page-break-inside: avoid;
      }}

      h2 + p, h3 + p,
      h2 + ul, h3 + ul,
      h2 + ol, h3 + ol {{
        break-inside: avoid;
        page-break-inside: avoid;
      }}


      .footer-meta {{ display: none !important; }}

      /* Hide navigational chrome in PDFs */
      nav,
      .top-nav,
      .footer-nav,
      .masthead-subtitle,
      .masthead-description,
      hr,
      .site-footer,
      .footer-disclaimer {{
        display: none !important;
      }}

      /* Hide PDF download link inside PDFs */
      .pdf-link {{ display: none !important; }}

      /* Keep brand header but tighten spacing */
      header {{
        margin-bottom: 12px !important;
      }}
      .masthead-title {{
        margin-bottom: 0 !important;
      }}

      /* Print-only disclaimer (single source of truth) */
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
      <div class="masthead-description">RegLag is a financial regulatory briefing focused on source-based interpretation of regulatory, policy, and market-structure developments, with weekday coverage and weekend deep dives into enforcement and regulatory mechanisms.</div>
      <hr />
      <nav class="top-nav">
        <a href="/">Latest</a> ·
        <a href="/briefings/index.html">Archive</a> ·
        <a href="/portfolio/index.html">Portfolio</a> ·
        <a href="/about/index.html">About</a> ·
        <a href="/subscribe/">Subscribe</a>
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
        <a href="/subscribe/">Subscribe</a> ·
        <a href="/legal/index.html">Legal &amp; Privacy</a> ·
        <a href="/rss.xml">RSS</a> ·
        <a href="https://x.com/reglag_hq" rel="me noopener" target="_blank">X</a> ·
        <a href="mailto:contact@reglag.com">Contact</a>
      </nav>
      <div class="footer-meta">
        <div class="footer-meta-line">Informational only. Not legal, financial, or compliance advice.</div>
        <div class="footer-meta-line footer-meta-muted">© 2026 RegLag · Original analysis and commentary.</div>
      </div>
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

        md_body = inject_post_type_label_md(md_body, post_type)
        md_body = inject_pdf_link_md(md_body, p.stem)

        body_html = md_to_html(md_body)

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

    md_body = inject_post_type_label_md(md_body, post_type)
    md_body = inject_pdf_link_md(md_body, latest)

    home_body_html = md_to_html(md_body)
    home_html = HTML.format(
        title=latest_title,
        body=home_body_html,
        canonical_url=f"{SITE_URL}/",
    )
    (OUT / "index.html").write_text(home_html, encoding="utf-8")

    
    # Archive index (reorganized by type, then date)
    deep_dives = []
    dailies = []

    for date_str, post_type, title in archive_items:
        if post_type == "Weekend Deep Dive":
            deep_dives.append((date_str, title))
        else:
            dailies.append((date_str, title))

    archive_html = "<h1>Briefing Archive</h1>"
    archive_html += '<p><a href="#weekend-deep-dives">Weekend Deep Dives</a> · <a href="#daily-briefings">Daily Briefings</a></p>'

    # Weekend Deep Dives
    archive_html += '<h2 id="weekend-deep-dives">Weekend Deep Dives</h2>'

    for date_str, title in deep_dives:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        display_date = format_spelled_date(dt)
        pdf_path = ARCHIVE / f"{date_str}.pdf"
        pdf_link = " (PDF)" if pdf_path.exists() else ""
        archive_html += f'<p>{display_date} — <a href="/briefings/{date_str}.html"><em>{xml_escape(title)}</em></a>{pdf_link}</p>'

    # Daily Briefings
    archive_html += '<h2 id="daily-briefings">Daily Briefings</h2>'

    current_month = None
    for date_str, title in dailies:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        month_label = dt.strftime("%B %Y")

        if month_label != current_month:
            archive_html += f"<h3>{month_label}</h3>"
            current_month = month_label

        display_date = format_spelled_date(dt)
        archive_html += f'<p>{display_date} — <a href="/briefings/{date_str}.html"><em>{xml_escape(title)}</em></a></p>'

    (ARCHIVE / "index.html").write_text(
        HTML.format(
            title="Briefing Archive",
            body=archive_html,
            canonical_url=f"{SITE_URL}/briefings/",
        ),
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


    # Subscribe page
    if SUBSCRIBE_SRC.exists():
        subscribe_html = md_to_html(SUBSCRIBE_SRC.read_text(encoding="utf-8"))
        subscribe_out = OUT / "subscribe"
        subscribe_out.mkdir(parents=True, exist_ok=True)
        (subscribe_out / "index.html").write_text(
            HTML.format(title="Subscribe", body=subscribe_html, canonical_url=f"{SITE_URL}/subscribe/"),
            encoding="utf-8",
        )

    # Legal & Privacy page
    if LEGAL_SRC.exists():
        legal_html = md_to_html(LEGAL_SRC.read_text(encoding="utf-8"))
        legal_out = OUT / "legal"
        legal_out.mkdir(parents=True, exist_ok=True)
        (legal_out / "index.html").write_text(
            HTML.format(title="Legal & Privacy", body=legal_html, canonical_url=f"{SITE_URL}/legal/"),
            encoding="utf-8",
        )

    # RSS feed (latest first, with post_type prefix)
    rss = build_rss(archive_items[:50], site_url=SITE_URL)
    (OUT / "rss.xml").write_text(rss, encoding="utf-8")
    (OUT / "feed.xml").write_text(rss, encoding="utf-8")

    print(f"Built {len(md_files)} briefings. Latest: {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
