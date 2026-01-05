#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
from datetime import datetime

try:
    import markdown  # pip install markdown
except ImportError:
    markdown = None

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "briefings"
OUT = ROOT / "publish" / "site"
ARCHIVE = OUT / "briefings"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")

HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 0; }}
    .wrap {{ max-width: 900px; margin: 0 auto; padding: 28px 18px 70px; }}
    nav a {{ margin-right: 14px; text-decoration: none; }}
    .muted {{ color: #666; font-size: 14px; margin-top: 10px; }}
    h1 {{ font-size: 26px; margin: 0 0 14px; }}
    h2 {{ margin-top: 22px; }}
    .content {{ line-height: 1.55; }}
    hr {{ border: 0; border-top: 1px solid #eee; margin: 26px 0; }}
    pre {{ padding: 12px; overflow: auto; background: #f6f6f6; }}
    code {{ background: #f6f6f6; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <nav>
        <a href="/index.html">Latest</a>
        <a href="/briefings/index.html">Archive</a>
      </nav>
      <div class="muted">Informational only. Not legal, financial, or compliance advice.</div>
    </header>
    <main class="content">
      {body}
    </main>
  </div>
</body>
</html>
"""

def md_to_html(text: str) -> str:
    if markdown is None:
        esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        paras = "".join(f"<p>{p.strip()}</p>" for p in esc.split("\n\n") if p.strip())
        return paras
    return markdown.markdown(text, extensions=["fenced_code", "tables"])

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ARCHIVE.mkdir(parents=True, exist_ok=True)

    md_files = sorted([p for p in SRC.glob("*.md") if DATE_RE.match(p.name)], reverse=True)
    if not md_files:
        print("No briefings found in ./briefings (expected YYYY-MM-DD.md)")
        return 0

    items = []
    for p in md_files:
        date_str = p.stem
        title = f"RegLag Daily Briefing — {date_str}"
        body = md_to_html(p.read_text(encoding="utf-8"))
        html = HTML.format(title=title, body=body)
        out_path = ARCHIVE / f"{date_str}.html"
        out_path.write_text(html, encoding="utf-8")
        items.append((date_str, f"/briefings/{date_str}.html"))

    # Archive index
    links = "\n".join(f'<li><a href="{href}">{d}</a></li>' for d, href in items)
    archive_body = f"<h1>Briefing Archive</h1><ul>{links}</ul>"
    (ARCHIVE / "index.html").write_text(HTML.format(title="Briefing Archive", body=archive_body), encoding="utf-8")

    # Latest as homepage
    latest_date = items[0][0]
    (OUT / "index.html").write_text((ARCHIVE / f"{latest_date}.html").read_text(encoding="utf-8"), encoding="utf-8")

    print(f"Built {len(items)} briefings. Latest: {latest_date}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
