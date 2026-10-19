import io
import json
import unittest
import zipfile
import xml.etree.ElementTree as ET
from splitter import split_file, SplitError
from app import app


def contents(result):
    with zipfile.ZipFile(result[0]) as z:
        return [z.read(name) for name in z.namelist()]

class SplitTests(unittest.TestCase):
    def test_json_order_and_balanced_parts(self):
        parts = [json.loads(p) for p in contents(split_file(b'[0,1,2,3,4]', 'a.json', 3, 'parts'))]
        self.assertEqual([len(p) for p in parts], [2, 2, 1])
        self.assertEqual(sum(parts, []), list(range(5)))

    def test_json_metadata_and_literal_key(self):
        data = b'{"a.b":[1,2,3],"meta":{"version":1}}'
        parts = [json.loads(p) for p in contents(split_file(data, 'x.json', 2, array_key='a.b'))]
        self.assertEqual(parts[1], {'a.b':[3], 'meta':{'version':1}})

    def test_xml_wrapper_namespaces_and_nested_records(self):
        data = b'<r xmlns="urn:test" version="1"><item><n>1</n></item><item><n>2</n></item></r>'
        parts = [ET.fromstring(p) for p in contents(split_file(data, 'x.xml', 1))]
        self.assertEqual(len(parts), 2)
        self.assertTrue(all(p.tag == '{urn:test}r' and p.attrib == {'version':'1'} for p in parts))
        self.assertEqual([p[0][0].text for p in parts], ['1','2'])

    def test_unsafe_or_invalid_inputs(self):
        for data, filename in [(b'{"a":1,"a":2}', 'x.json'), (b'[NaN]', 'x.json'),
          (b'[]','x.json'), (b'<r>mixed<a/>text</r>','x.xml'),
          (b'<!DOCTYPE r [<!ENTITY x "boom">]><r><a>&x;</a></r>','x.xml'),
          (b'{','x.json'), (b'abc','x.txt')]:
            with self.subTest(data=data), self.assertRaises(SplitError):
                split_file(data, filename, 1)
        with self.assertRaises(SplitError): split_file(b'[1]', 'x.json', 2, 'parts')
        with self.assertRaises(SplitError): split_file(b'[1]', 'x.json', 0)
        with self.assertRaises(SplitError): split_file(b'['+b'0,'*500+b'0]', 'x.json', 1)

    def test_upload_and_errors(self):
        client = app.test_client()
        self.assertEqual(client.get('/').status_code, 200)
        response = client.post('/split', data={'file':(io.BytesIO(b'[1,2,3]'),'test.json'), 'amount':'2','mode':'records'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/zip')
        with zipfile.ZipFile(io.BytesIO(response.data)) as z: self.assertEqual(len(z.namelist()), 2)
        self.assertEqual(client.post('/split',data={'amount':'bad'}).status_code, 400)
        response = client.post('/split',data={'file':(io.BytesIO(b'{'),'x.json'),'amount':'1'})
        self.assertEqual(response.status_code,400)
        self.assertIn(b'Invalid JSON',response.data)

if __name__ == '__main__': unittest.main()
