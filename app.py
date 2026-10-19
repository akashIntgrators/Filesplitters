from flask import Flask, render_template, request, send_file
from splitter import MAX_INPUT, SplitError, split_file

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_INPUT + 1024 * 1024

@app.after_request
def headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    return response

@app.get('/')
def index():
    return render_template('index.html')

@app.post('/split')
def split():
    try:
        upload = request.files.get('file')
        if not upload or not upload.filename:
            raise SplitError('Choose an XML or JSON file first.')
        try:
            amount = int(request.form.get('amount', ''))
        except ValueError:
            raise SplitError('Enter a positive whole number.') from None
        data = upload.read(MAX_INPUT + 1)
        archive, filename, _ = split_file(data, upload.filename, amount,
            request.form.get('mode', 'records'), request.form.get('array_key', '').strip())
        return send_file(archive, mimetype='application/zip', as_attachment=True, download_name=filename)
    except (SplitError, RecursionError) as error:
        message = str(error) if isinstance(error, SplitError) else 'This file is nested too deeply to process.'
        return render_template('index.html', error=message), 400

@app.errorhandler(413)
def too_large(error):
    return render_template('index.html', error='Upload is too large. Choose a file up to 10 MiB.'), 413

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
