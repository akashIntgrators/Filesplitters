import tempfile
import threading
from pathlib import Path
from flask import Flask, Response, render_template, request
from splitter import MAX_INPUT, SplitError, split_path

app = Flask(__name__)
app.config.update(MAX_CONTENT_LENGTH=MAX_INPUT+1024*1024, MAX_FORM_MEMORY_SIZE=1024*1024, MAX_FORM_PARTS=10)
# One job per worker: avoid concurrent large temporary files. Deploy with one worker.
job_lock = threading.Lock()

@app.after_request
def headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    return response

@app.get('/')
def index(): return render_template('index.html')

@app.post('/split')
def split():
    if not job_lock.acquire(blocking=False):
        return render_template('index.html',error='Another file is processing. Please try again shortly.'),429
    directory = tempfile.TemporaryDirectory(prefix='file-splitter-')
    released = False
    def cleanup():
        nonlocal released
        if not released:
            released = True
            directory.cleanup()
            job_lock.release()
    try:
        upload = request.files.get('file')
        if not upload or not upload.filename: raise SplitError('Choose an XML or JSON file first.')
        try: amount = int(request.form.get('amount',''))
        except ValueError: raise SplitError('Enter a positive whole number.') from None
        source = Path(directory.name)/'input'
        with source.open('wb') as target:
            total = 0
            while chunk := upload.stream.read(1024*1024):
                total += len(chunk)
                if total > MAX_INPUT: raise SplitError('Choose a file up to 200 MB.')
                target.write(chunk)
        archive = Path(directory.name)/'result.zip'
        filename,_ = split_path(source,upload.filename,amount,archive,request.form.get('mode','records'),request.form.get('array_key','').strip())
        def download():
            try:
                with archive.open('rb') as file:
                    while chunk := file.read(256*1024): yield chunk
            finally: cleanup()
        response = Response(download(),mimetype='application/zip')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.content_length = archive.stat().st_size
        response.call_on_close(cleanup)
        return response
    except SplitError as error:
        cleanup()
        return render_template('index.html',error=str(error)),400
    except OSError:
        cleanup()
        return render_template('index.html',error='Temporary storage is unavailable or full. Please try again later.'),503
    except BaseException:
        cleanup()
        raise

@app.errorhandler(413)
def too_large(error):
    return render_template('index.html',error='Upload is too large. Choose a file up to 200 MB.'),413

if __name__ == '__main__': app.run(host='127.0.0.1',port=5000)
