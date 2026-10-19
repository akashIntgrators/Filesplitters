# Upgrade the existing Railway app to 200 MB

1. In your existing Filesplitters GitHub repository, replace:
   - app.py
   - splitter.py
   - requirements.txt
   - templates/index.html (keep it inside templates/)
2. Commit the changes. Railway should automatically rebuild.
3. In Railway > Filesplitters > Settings > Deploy > Custom Start Command, set:

```
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 300
```

4. Apply/deploy the changes. Keep one replica initially.
5. Check the live page says 200 MB, then test a small file before testing a large file.

Do not put templates/index.html at the repository root. It is a Flask template, not your portfolio homepage.

Verified locally: seven automated checks plus HTTP uploads of exactly 200,000,000 bytes for JSON and XML, each with 100,000 records split into ten valid files. Peak process memory was about 46 MB on the test machine. This is evidence for many small records, not a memory guarantee for giant individual records or a live Railway benchmark.

Temporary input and ZIP files now use disk and are removed when the download finishes or processing fails. Keep at least 2 GB free temporary storage and monitor runtime memory. Output is capped at 1 GB uncompressed and 500 files. JSON metadata outside the selected array is capped at 2 MB.

Hosting/proxy time limits still apply. A 200 MB upload over a slow connection may need direct-to-storage uploads and background processing in a future version. The live Railway upload path has not yet been tested.
