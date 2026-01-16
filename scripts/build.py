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
      1) <h1>Title</h1>
      2) Optional italic subtitle line as a standalone paragraph: <p><em>Subtitle</em></p>
      3) Post type label
      4) Date line (usually an italic standalone paragraph)

    Behavior:
      - If there are TWO consecutive italic-only paragraphs immediately after the H1,
        treat them as subtitle then date and insert the label BETWEEN them.
      - If there is ONE italic-only paragraph immediately after the H1 and it looks like a date,
        insert the label BEFORE it (so date stays after post type on dailies).
      - Otherwise, insert the label after the H1 (or after a non-date subtitle).
    """
    tag = f'<h3 class="post-type">{xml_escape(post_type)}</h3>'

    if "</h1>" not in body_html:
        return tag + "\n" + body_html

    def _looks_like_date(text: str) -> bool:
        t = re.sub(r"\s+", " ", text.strip())
        month = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        return bool(re.fullmatch(rf"{month} \d{{1,2}}, \d{{4}}", t)) or bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", t))

    # Two consecutive italic-only paragraphs right after </h1>:
    # <p><em>Subtitle</em></p><p><em>Date</em></p>
    two_italics_re = re.compile(
        r"(</h1>\s*)"
        r"(<p>\s*<em>(?P<i1>.*?)</em>\s*</p>\s*)"
        r"(<p>\s*<em>(?P<i2>.*?)</em>\s*</p>\s*)",
        re.IGNORECASE | re.DOTALL,
    )
    m2 = two_italics_re.search(body_html)
    if m2:
        # Insert at the start of the second italic paragraph (date),
        # so output order is: H1, subtitle, post_type, date.
        insert_at = m2.start(3)
        return body_html[:insert_at] + tag + "\n" + body_html[insert_at:]

    # One italic-only paragraph right after </h1>:
    one_italic_re = re.compile(
        r"(</h1>\s*)(<p>\s*<em>(?P<i1>.*?)</em>\s*</p>\s*)",
        re.IGNORECASE | re.DOTALL,
    )
    m1 = one_italic_re.search(body_html)
    if m1:
        italic_text = re.sub(r"<.*?>", "", m1.group("i1"))
        if _looks_like_date(italic_text):
            # Insert BEFORE date paragraph (daily briefings)
            insert_at = m1.start(2)
            return body_html[:insert_at] + tag + "\n" + body_html[insert_at:]
        else:
            # Treat as subtitle; insert AFTER it
            insert_at = m1.end(2)
            return body_html[:insert_at] + tag + "\n" + body_html[insert_at:]

    # Default: insert immediately after the H1.
    return body_html.replace("</h1>", "</h1>\n" + tag, 1)
