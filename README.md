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

Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 300`

Generate a Railway public domain first and test an upload. Then optionally connect splitter.techiwithhelmet.com using Railway's custom-domain instructions. Link that address from your existing GitHub Pages homepage. GitHub Pages cannot run this Python backend. Do not upload this template as your portfolio's index.html.

## Supported input

- JSON: top-level array, or top-level object with an array property selected by exact key. Dots in keys are literal; nested paths are not supported. Remaining properties repeat in each output. Duplicate keys and non-standard NaN/Infinity are rejected.
- XML: each direct child of the document root is a record. The root name and attributes repeat in each file. Namespace URIs remain, but prefixes and formatting can change. Comments and processing instructions are not retained. Mixed text between records and DTD/entities are rejected.
- Mode: maximum records per file, or an exact number of balanced, non-empty files. Order is preserved. This is record-count splitting, not a target byte size.
- Limits: 200 MB input (200,000,000 bytes), 500 outputs, 1 GB total uncompressed output. Streaming uses two passes and temporary disk. Memory scales with the largest individual record; a single giant record can still need substantial RAM. Non-record JSON metadata is limited to 2 MB and repeated in every part.

## Privacy and operations

Uploads and results use temporary disk storage and are deleted after the response completes or an error occurs. A forced process kill may leave files until the container is replaced; use ephemeral storage. Files do leave the user's browser and enter the hosting service. No analytics or file-content logging is included. Public deployment should add provider/proxy rate limiting and monitoring before broad promotion; the app accepts one active job per worker and returns 429 to other jobs. Keep one worker and one replica initially. Do not enable Flask debug mode publicly.

## Tests

```sh
python -m unittest discover -s tests -v
```

## Upgrading an existing Railway deployment

Replace app.py, splitter.py, requirements.txt and templates/index.html in GitHub. Railway will rebuild with the new dependencies. Change the existing Railway Custom Start Command to:

```sh
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 300
```

Keep at least 2 GB of free temporary disk headroom and monitor RAM/CPU. No permanent volume or database is required. A single 200 MB record can use much more memory than its byte size. The local 200 MB tests cover many small records, not every possible document shape.

Railway has an edge request-duration limit; raising Gunicorn's timeout does not override it. Slow uploads or processing can still time out. If real workloads approach that limit, use direct object-storage uploads and background jobs rather than further increasing request timeouts. Test an actual 200 MB upload against the generated Railway domain before calling the deployment verified.

The native browser download avoids buffering the full ZIP in browser JavaScript. A clean disconnect closes the response and removes temporary files.
