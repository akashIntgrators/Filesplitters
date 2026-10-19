# Update to XML-only splitting

Replace these four files in your existing Filesplitters GitHub repository:

- app.py
- splitter.py
- requirements.txt
- templates/index.html

Commit and let Railway redeploy. Keep your existing start command:

```
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 300
```

After deployment the page should show only Number of files, accept .xml and .txt containing XML, and offer no JSON option. Files are still limited to 200 MB; outputs are always XML. Try both examples/sample.xml and examples/sample.txt.
