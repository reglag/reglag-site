# RegLag

RegLag is a **daily briefing** published as a static site.

- Latest briefing: `/index.html`
- Archive: `/briefings/index.html`

This project no longer includes automated web monitoring, diffs, snapshotting, or scoring.

## Write a briefing
Create a file in `./briefings/` named:

`YYYY-MM-DD.md`

## Build the site
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install markdown
python3 scripts/build.py
```

## Notes
Informational only. Not legal, financial, or compliance advice.
