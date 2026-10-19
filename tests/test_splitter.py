import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
from splitter import split_path, SplitError
from app import app, job_lock


def split_file(data, filename, amount):
    with tempfile.TemporaryDirectory() as folder:
        source, target = Path(folder)/'input', Path(folder)/'result.zip'
        source.write_bytes(data)
        split_path(source, filename, amount, target)
        with zipfile.ZipFile(target) as archive:
            return [(name, ET.fromstring(archive.read(name))) for name in archive.namelist()]

class SplitTests(unittest.TestCase):
    def test_balanced_xml_and_txt_preserve_order(self):
        data = b'<root version="1">' + b''.join(f'<record id="{i}"/>'.encode() for i in range(5)) + b'</root>'
        for extension in ('xml', 'txt', 'TXT'):
            parts = split_file(data, 'input.'+extension, 3)
            self.assertEqual([len(root) for _,root in parts],[2,2,1])
            self.assertEqual([int(child.attrib['id']) for _,root in parts for child in root],list(range(5)))
            self.assertTrue(all(name.endswith('.xml') and root.attrib == {'version':'1'} for name,root in parts))

    def test_namespaces_and_nested_records(self):
        parts=split_file(b'<r xmlns="urn:test"><item><n>1</n></item><item><n>2</n></item></r>','x.txt',2)
        self.assertEqual([root[0][0].text for _,root in parts],['1','2'])
        self.assertTrue(all(root.tag=='{urn:test}r' for _,root in parts))

    def test_invalid_content_extensions_and_amounts(self):
        for data,name,amount in [(b'plain text','x.txt',1),(b'[1,2]','x.txt',1),
          (b'<r><i/></r>','x.json',1),(b'<r><i/></r>','x.csv',1),
          (b'<r/>','x.xml',1),(b'<r><i/></r>','x.xml',2),
          (b'<r><i/></r>','x.xml',0),(b'<r>text<i/>tail</r>','x.xml',1),
          (b'<!DOCTYPE r [<!ENTITY x "boom">]><r><i>&x;</i></r>','x.txt',1)]:
            with self.subTest(name=name,amount=amount),self.assertRaises(SplitError):
                split_file(data,name,amount)

    def test_http_txt_upload_and_ui(self):
        client=app.test_client()
        html=client.get('/').data
        self.assertNotIn(b'name="mode"',html)
        self.assertNotIn(b'name="array_key"',html)
        for filename in ('example.xml','example.txt'):
            response=client.post('/split',data={'file':(io.BytesIO(b'<r><i/><i/></r>'),filename),'amount':'2'})
            self.assertEqual(response.status_code,200)
            with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
                self.assertEqual(len(archive.namelist()),2)
                self.assertTrue(all(n.endswith('.xml') for n in archive.namelist()))
            response.close()
        response=client.post('/split',data={'file':(io.BytesIO(b'not xml'),'example.txt'),'amount':'1'})
        self.assertEqual(response.status_code,400)
        self.assertIn(b'valid supported XML',response.data)
        self.assertFalse(job_lock.locked())

    def test_size_limit_busy_and_cleanup(self):
        client=app.test_client()
        job_lock.acquire()
        try:self.assertEqual(client.post('/split').status_code,429)
        finally:job_lock.release()
        with patch('app.MAX_INPUT',2):
            response=client.post('/split',data={'file':(io.BytesIO(b'<r/>'),'x.xml'),'amount':'1'})
            self.assertEqual(response.status_code,400)
        self.assertFalse(job_lock.locked())

    def test_multipart_newline_at_parser_buffer_boundary(self):
        boundary = 'browser-boundary'
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="test.xml"\r\nContent-Type: text/xml\r\n\r\n').encode()
        opening = b'<records><record>'
        payload = opening + b'x' * (65535 - len(head) - len(opening)) + b'\r\n' + b'x' * 100000 + b'</record></records>'
        tail = (f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="amount"\r\n\r\n1\r\n--{boundary}--\r\n').encode()
        response = app.test_client().post('/split', data=head+payload+tail,
            content_type=f'multipart/form-data; boundary={boundary}')
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(len(archive.namelist()), 1)
            self.assertEqual(ET.fromstring(archive.read(archive.namelist()[0])).tag, 'records')
        response.close()

if __name__ == '__main__': unittest.main()
