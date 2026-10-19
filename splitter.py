"""Disk-backed record splitting. Memory scales with the largest record, not file size."""
import math
import re
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import ijson
import simplejson as json
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

MAX_INPUT = 200_000_000  # 200 MB, decimal units
MAX_OUTPUT = 1_000_000_000
MAX_PARTS = 500
MAX_METADATA = 2_000_000

class SplitError(ValueError):
    pass

class UniqueDict(dict):
    def __setitem__(self, key, value):
        if key in self:
            raise SplitError('JSON contains duplicate keys; splitting would lose data.')
        super().__setitem__(key, value)

def json_value(events, first):
    builder = ijson.common.ObjectBuilder(map_type=UniqueDict)
    event, value = first
    builder.event(event, value)
    depth = int(event in ('start_map', 'start_array'))
    while depth:
        event, value = next(events)
        builder.event(event, value)
        depth += int(event in ('start_map', 'start_array')) - int(event in ('end_map', 'end_array'))
    return builder.value

def json_records(path, key, metadata):
    with open(path, 'rb') as stream:
        # UTF-8 BOM is optional.
        if stream.read(3) != b'\xef\xbb\xbf': stream.seek(0)
        events = iter(ijson.basic_parse(stream))
        first = next(events)
        if not key:
            if first[0] != 'start_array':
                raise SplitError('Use a JSON array, or enter its top-level array key.')
            for event in events:
                if event[0] == 'end_array': break
                yield json_value(events, event)
        else:
            if first[0] != 'start_map': raise SplitError('Array key requires a top-level object.')
            seen = set()
            found = False
            for event, value in events:
                if event == 'end_map': break
                if event != 'map_key' or value in seen: raise SplitError('Invalid or duplicate top-level JSON key.')
                seen.add(value)
                entry = next(events)
                if value == key:
                    if entry[0] != 'start_array': raise SplitError('Selected JSON key must contain an array.')
                    found = True
                    for item in events:
                        if item[0] == 'end_array': break
                        yield json_value(events, item)
                else:
                    metadata[value] = json_value(events, entry)
                    if len(json.dumps(metadata, use_decimal=True).encode('utf-8')) > MAX_METADATA:
                        raise SplitError('Non-record JSON metadata exceeds 2 MB. Use a top-level array instead.')
            if not found: raise SplitError('JSON array key was not found.')
        if next(events, None) is not None: raise SplitError('Unexpected content after JSON document.')

def xml_records(path, context):
    depth = 0
    root = None
    pending = None
    with open(path, 'rb') as stream:
        for event, element in SafeET.iterparse(stream, events=('start','end'), forbid_dtd=True, forbid_entities=True, forbid_external=True):
            if event == 'start':
                depth += 1
                if depth == 1:
                    root = element
                    context['root'] = ET.Element(root.tag, dict(root.attrib))
                elif depth == 2:
                    if (root.text or '').strip(): raise SplitError('XML with mixed text between records is unsupported.')
                    if pending is not None:
                        if (pending.tail or '').strip(): raise SplitError('XML with mixed text between records is unsupported.')
                        pending.tail = None
                        yield pending
                        root.remove(pending)
                        pending.clear()
                        pending = None
            else:
                if depth == 2: pending = element
                elif depth == 1:
                    if (root.text or '').strip(): raise SplitError('XML with mixed text between records is unsupported.')
                    if pending is not None:
                        if (pending.tail or '').strip(): raise SplitError('XML with mixed text between records is unsupported.')
                        pending.tail = None
                        yield pending
                        root.remove(pending)
                        pending.clear()
                depth -= 1

def split_path(path, filename, amount, output_path, mode='records', array_key=''):
    size = Path(path).stat().st_size
    if not size or size > MAX_INPUT: raise SplitError('Choose a non-empty file up to 200 MB.')
    if mode not in ('records','parts') or not isinstance(amount,int) or amount < 1:
        raise SplitError('Enter a positive whole number and a valid split mode.')
    ext = filename.rsplit('.',1)[-1].lower()
    if ext not in ('json','xml'): raise SplitError('Choose an .xml or .json file.')
    metadata = {}
    context = {}
    def records():
        return json_records(path,array_key,metadata) if ext == 'json' else xml_records(path,context)
    try:
        # Validate/count first. This also collects metadata after a JSON record array.
        count = sum(1 for _ in records())
        if not count: raise SplitError('No records were found to split.')
        if mode == 'parts':
            if amount > min(count,MAX_PARTS): raise SplitError('Number of files cannot exceed the record count or 500.')
            base, extra = divmod(count,amount)
            sizes = [base + (i < extra) for i in range(amount)]
        else:
            parts = math.ceil(count / amount)
            if parts > MAX_PARTS: raise SplitError('More than 500 output files. Increase records per file.')
            sizes = [min(amount,count-i*amount) for i in range(parts)]
        stem = re.sub(r'[^A-Za-z0-9_-]', '_', filename.replace('\\','/').split('/')[-1].rsplit('.',1)[0])[:70] or 'file'
        if ext == 'json':
            if array_key:
                prefix = '{' + ''.join(json.dumps(k)+':'+json.dumps(v,use_decimal=True,ensure_ascii=False)+',' for k,v in metadata.items()) + json.dumps(array_key)+':['
                suffix = ']}'
            else: prefix, suffix = '[', ']'
        else:
            empty = ET.tostring(context['root'],encoding='unicode',short_empty_elements=True)
            prefix = '<?xml version="1.0" encoding="UTF-8"?>\n' + empty[:-3] + '>'
            tag = empty[1:].split()[0].rstrip('/>')
            suffix = '</' + tag + '>'
        total = 0
        items = iter(records())
        with zipfile.ZipFile(output_path,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
            for number, length in enumerate(sizes,1):
                with archive.open(f'{stem}_part_{number:03d}.{ext}','w') as part:
                    def write(value):
                        nonlocal total
                        content = value.encode('utf-8') if isinstance(value,str) else value
                        total += len(content)
                        if total > MAX_OUTPUT: raise SplitError('Output exceeds 1 GB. Reduce repeated metadata or the number of parts.')
                        part.write(content)
                    write(prefix)
                    for index in range(length):
                        item = next(items)
                        if ext == 'json':
                            if index: write(',')
                            write(json.dumps(item,use_decimal=True,ensure_ascii=False,allow_nan=False))
                        else: write(ET.tostring(item,encoding='utf-8'))
                    write(suffix)
            # Exhaust iterator to finish validation and release handles.
            if next(items,None) is not None: raise SplitError('Record count changed unexpectedly.')
        return f'{stem}_split.zip',len(sizes)
    except SplitError:
        raise
    except (ijson.JSONError, StopIteration, UnicodeError, ET.ParseError, DefusedXmlException, ValueError, RecursionError):
        raise SplitError('Invalid or unsupported file. Check its structure; XML DTDs and entities are not allowed.') from None
