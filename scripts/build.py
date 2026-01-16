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
    """Insert a styled post-type label (e.g., 'Daily Briefing' / 'Weekend Deep Dive')
    near the top of the post.

    Desired render order:
      1) H1 title
      2) Optional italic subtitle line (a standalone <p><em>…</em></p>)
      3) Post type label
      4) Date line (usually an italic standalone paragraph)

    Rules:
      - If the first italic paragraph after the H1 looks like a date, insert the label BEFORE it.
      - If there are TWO consecutive italic paragraphs after the H1, treat them as:
          subtitle (1st), date (2nd), and insert the label BETWEEN them.
      - Otherwise, insert the label after the H1 (or after a non-date subtitle).
    """
    tag = f'<h3 class="post-type">{xml_escape(post_type)}</h3>'

    if "</h1>" not in body_html:
        return tag + "\n" + body_html

    def _looks_like_date(text: str) -> bool:
        # Accept either 'January 16, 2026' or '2026-01-16'
        t = re.sub(r"\s+", " ", text.strip())
        month = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        return bool(re.fullmatch(rf"{month} \d{{1,2}}, \d{{4}}", t)) or bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", t))

    # Two consecutive italic-only paragraphs after the H1 => subtitle then date.
    two_italics_re = re.compile(
        r"(</h1>\s*)"
        r"(<p>\s*<em>(?P<i1>.*?)</em>\s*</p>\s*)"
        r"(<p>\s*<em>(?P<i2>.*?)</em>\s*</p>\s*)",
        re.IGNORECASE | re.DOTALL,
    )
    m2 = two_italics_re.search(body_html)
    if m2:
        insert_at = m2.start(3)  # start of the second italic paragraph (date)
        return body_html[:insert_at] + tag + "\n" + body_html[insert_at:]

    # One italic-only paragraph after the H1 => either date OR subtitle.
    one_italic_re = re.compile(
        r"(</h1>\s*)(<p>\s*<em>(?P<i1>.*?)</em>\s*</p>\s*)",
        re.IGNORECASE | re.DOTALL,
    )
    m1 = one_italic_re.search(body_html)
    if m1:
        italic_text = re.sub(r"<.*?>", "", m1.group("i1"))
        if _looks_like_date(italic_text):
            insert_at = m1.start(2)  # before date paragraph
            return body_html[:insert_at] + tag + "\n" + body_html[insert_at:]
        else:
            insert_at = m1.end(2)  # after subtitle paragraph
            return body_html[:insert_at] + tag + "\n" + body_html[insert_at:]

    return body_html.replace("</h1>", "</h1>\n" + tag, 1)

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


    # Subscribe page
    if SUBSCRIBE_SRC.exists():
        subscribe_html = md_to_html(SUBSCRIBE_SRC.read_text(encoding="utf-8"))
        subscribe_out = OUT / "subscribe"
        subscribe_out.mkdir(parents=True, exist_ok=True)
        (subscribe_out / "index.html").write_text(
            HTML.format(title="Subscribe", body=subscribe_html, canonical_url=f"{SITE_URL}/subscribe/"),
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
