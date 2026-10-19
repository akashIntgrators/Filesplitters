# XML Splitter · Techi with Helmet

A Flask app for splitting XML into an exact number of balanced files, downloaded as a ZIP. Python 3.10+ required.

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Stop with Control+C.

## Existing Railway deployment

Replace app.py, splitter.py, requirements.txt and templates/index.html in your GitHub repository. Keep the template inside templates/. Railway should rebuild automatically.

Keep the Custom Start Command:

```sh
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 300
```

Use one replica initially. New deployments can connect this repository in Railway and generate a public domain. This Python app does not run on GitHub Pages.

## Input and splitting

- Accepts .xml and .txt (case-insensitive). Both are parsed as XML; extensions do not bypass content validation.
- JSON support and its dependencies have been removed. Ordinary text and JSON renamed to .txt are rejected.
- Enter only Number of files (1–500). Each output must contain at least one record.
- Each direct child element of the document root is a record. Parts are balanced by record count and preserve order.
- All output parts end in .xml, including when the source ends in .txt.
- Root name, root attributes and namespace URIs are retained. Formatting and namespace prefixes may change. Comments and processing instructions are not preserved. DTDs/entities and mixed text between root-level records are rejected. Do not use for signed XML or byte-exact preservation.
- Limits: 200 MB input (200,000,000 bytes), 500 parts, 1 GB total uncompressed output.

## Storage and hosting

Processing uses two passes and temporary disk files. Files are deleted on normal download completion or processing failure. Forced process termination can leave files until the container is replaced. Keep at least 2 GB free temporary disk headroom and monitor memory. Memory scales with the largest individual XML record, so one giant record may still need substantial RAM.

One active job per worker; other jobs receive 429 and can retry. Slow uploads/processing can hit hosting or proxy time limits; a future background-job design is appropriate if that occurs. No database or permanent volume is required. Live Railway large-file behaviour must be tested after deploying.

## Test

```sh
python -m unittest discover -s tests -v
```

Tests cover XML/TXT content validation, balanced parts, order, namespaces, endpoint behaviour, upload limits and the multipart boundary bug fixed in the previous release.
