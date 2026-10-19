# File Splitter · Techi with Helmet

A Flask app with an HTML upload form and ZIP downloads. Requires Python 3.10+.

## Run locally

Open a terminal in this folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Stop with Control+C.

## Deploy on Railway

Create a GitHub repository for this folder's contents. In Railway, create a project from that repository.

Build/install command: `pip install -r requirements.txt`

Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120`

Generate a Railway public domain first and test an upload. Then optionally connect splitter.techiwithhelmet.com using Railway's custom-domain instructions. Link that address from your existing GitHub Pages homepage. GitHub Pages cannot run this Python backend. Do not upload this template as your portfolio's index.html.

## Supported input

- JSON: top-level array, or top-level object with an array property selected by exact key. Dots in keys are literal; nested paths are not supported. Remaining properties repeat in each output. Duplicate keys and non-standard NaN/Infinity are rejected.
- XML: each direct child of the document root is a record. The root name and attributes repeat in each file. Namespace URIs remain, but prefixes and formatting can change. Comments and processing instructions are not retained. Mixed text between records and DTD/entities are rejected.
- Mode: maximum records per file, or an exact number of balanced, non-empty files. Order is preserved. This is record-count splitting, not a target byte size.
- Limits: 10 MiB input, 500 outputs, 40 MiB total uncompressed output. In-memory processing is for small files; larger workloads need a streaming design.

## Privacy and operations

Uploads/results are not written to disk by this application. Files do leave the user's browser and enter the hosting service. No analytics or file-content logging is included. Public deployment should add provider/proxy rate limiting and monitoring before broad promotion; per-request limits do not cap total concurrent traffic. Do not enable Flask debug mode publicly.

## Tests

```sh
python -m unittest discover -s tests -v
```
