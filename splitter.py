"""Record-based JSON/XML splitting. No input files are written to disk."""
import copy
import io
import json
import math
import re
import zipfile
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

MAX_INPUT = 10 * 1024 * 1024
MAX_OUTPUT = 40 * 1024 * 1024
MAX_PARTS = 500

class SplitError(ValueError):
    pass

def reject_constant(value):
    raise SplitError('JSON must not contain NaN or Infinity.')

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SplitError('JSON contains duplicate object keys; splitting would lose data.')
        result[key] = value
    return result

def split_file(data, filename, amount, mode='records', array_key=''):
    if not data or len(data) > MAX_INPUT:
        raise SplitError('Choose a non-empty file up to 10 MiB.')
    if mode not in ('records', 'parts') or not isinstance(amount, int) or amount < 1:
        raise SplitError('Enter a positive whole number and a valid split mode.')
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext == 'json':
        try:
            doc = json.loads(data.decode('utf-8-sig'), parse_constant=reject_constant, object_pairs_hook=unique_object)
        except (UnicodeError, json.JSONDecodeError, RecursionError):
            raise SplitError('Invalid JSON. Use a UTF-8 JSON file.') from None
        if array_key:
            if not isinstance(doc, dict) or not isinstance(doc.get(array_key), list):
                raise SplitError('The array key must identify a top-level JSON array property.')
            records = doc[array_key]
            def serialize(chunk):
                output = dict(doc)
                output[array_key] = chunk
                return json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
        else:
            if not isinstance(doc, list):
                raise SplitError('Use a JSON array, or enter the top-level property containing your array.')
            records = doc
            def serialize(chunk):
                return json.dumps(chunk, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    elif ext == 'xml':
        try:
            root = SafeET.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        except (ET.ParseError, DefusedXmlException, ValueError):
            raise SplitError('Invalid or unsupported XML. DTDs and entities are not accepted.') from None
        records = list(root)
        if (root.text or '').strip() or any((child.tail or '').strip() for child in records):
            raise SplitError('XML must contain records directly under its root, without mixed text between records.')
        def serialize(chunk):
            output = ET.Element(root.tag, dict(root.attrib))
            output.extend(copy.deepcopy(child) for child in chunk)
            return ET.tostring(output, encoding='utf-8', xml_declaration=True)
    else:
        raise SplitError('Choose an .xml or .json file.')
    count = len(records)
    if not count:
        raise SplitError('No records were found to split.')
    if mode == 'parts':
        if amount > min(count, MAX_PARTS):
            raise SplitError('Number of files cannot exceed the record count or 500.')
        base, extra = divmod(count, amount)
        sizes = [base + (i < extra) for i in range(amount)]
    else:
        parts = math.ceil(count / amount)
        if parts > MAX_PARTS:
            raise SplitError('This would create more than 500 files. Increase records per file.')
        sizes = [min(amount, count - i * amount) for i in range(parts)]
    stem = re.sub(r'[^A-Za-z0-9_-]', '_', filename.replace('\\', '/').split('/')[-1].rsplit('.', 1)[0])[:70] or 'file'
    archive = io.BytesIO()
    total = 0
    offset = 0
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for number, size in enumerate(sizes, 1):
            content = serialize(records[offset:offset + size])
            total += len(content)
            if total > MAX_OUTPUT:
                raise SplitError('Expanded output exceeds 40 MiB. Reduce the number of files or repeated metadata.')
            z.writestr(f'{stem}_part_{number:03d}.{ext}', content)
            offset += size
    archive.seek(0)
    return archive, f'{stem}_split.zip', len(sizes)
