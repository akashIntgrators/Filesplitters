"""Disk-backed record splitting. Memory scales with the largest record, not file size."""
import re
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

MAX_INPUT = 200_000_000  # 200 MB, decimal units
MAX_OUTPUT = 1_000_000_000
MAX_PARTS = 500

class SplitError(ValueError):
    pass

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

def split_path(path, filename, amount, output_path):
    size = Path(path).stat().st_size
    if not size or size > MAX_INPUT: raise SplitError('Choose a non-empty file up to 200 MB.')
    if not isinstance(amount,int) or isinstance(amount,bool) or amount < 1:
        raise SplitError('Enter a positive whole number of files.')
    ext = filename.rsplit('.',1)[-1].lower()
    if ext not in ('xml','txt'): raise SplitError('Choose an .xml or .txt file containing XML.')
    context = {}
    def records():
        return xml_records(path,context)
    try:
        # Validate XML contents and count records before writing any output.
        count = sum(1 for _ in records())
        if not count: raise SplitError('No records were found to split.')
        if amount > min(count,MAX_PARTS):
            raise SplitError('Number of files cannot exceed the XML record count or 500.')
        base, extra = divmod(count,amount)
        sizes = [base + (i < extra) for i in range(amount)]
        stem = re.sub(r'[^A-Za-z0-9_-]', '_', filename.replace('\\','/').split('/')[-1].rsplit('.',1)[0])[:70] or 'file'
        empty = ET.tostring(context['root'],encoding='unicode',short_empty_elements=True)
        prefix = '<?xml version="1.0" encoding="UTF-8"?>\n' + empty[:-3] + '>'
        tag = empty[1:].split()[0].rstrip('/>')
        suffix = '</' + tag + '>'
        total = 0
        items = iter(records())
        with zipfile.ZipFile(output_path,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
            for number, length in enumerate(sizes,1):
                with archive.open(f'{stem}_part_{number:03d}.xml','w') as part:
                    def write(value):
                        nonlocal total
                        content = value.encode('utf-8') if isinstance(value,str) else value
                        total += len(content)
                        if total > MAX_OUTPUT: raise SplitError('Output exceeds 1 GB. Reduce repeated metadata or the number of parts.')
                        part.write(content)
                    write(prefix)
                    for index in range(length):
                        item = next(items)
                        write(ET.tostring(item,encoding='utf-8'))
                    write(suffix)
            # Exhaust iterator to finish validation and release handles.
            if next(items,None) is not None: raise SplitError('Record count changed unexpectedly.')
        return f'{stem}_split.zip',len(sizes)
    except SplitError:
        raise
    except (StopIteration, UnicodeError, ET.ParseError, DefusedXmlException, ValueError, RecursionError):
        raise SplitError('This file does not contain valid supported XML. Plain text and JSON are not supported; XML DTDs and entities are not allowed.') from None
