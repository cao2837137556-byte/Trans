"""Synthetic retrieval, partial-download recovery and local disk boundaries."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch

import client


def digest(value):return hashlib.sha256(value).hexdigest()


class ClientChecks(unittest.TestCase):
    def fixture(self,root):
        package=root/'science';here=root/'deployment';package.mkdir();here.mkdir()
        card=b'synthetic card';(package/'EXECUTION_CARD.json').write_bytes(card)
        payloads={'RESULT.json':json.dumps(dict(execution_card_sha256=digest(card))).encode(),
            'history/NETATMO/encoded/references.npz':b'synthetic saved reference arrays',
            'history/NETATMO/encoded/batches/000001.npz':b'synthetic saved batch'}
        payloads['STAGE_RECEIPT.json']=json.dumps(dict(technical_status='COMPLETED',outputs={n:digest(b) for n,b in payloads.items()})).encode()
        buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode='w') as ar:
            for name,payload in payloads.items():
                info=tarfile.TarInfo(name);info.size=len(payload);ar.addfile(info,io.BytesIO(payload))
        return package,here,payloads,buffer.getvalue()

    def response(self,archive,offset=0,*,truncate=None):
        data=archive[offset:] if truncate is None else archive[offset:offset+truncate]
        stream=io.BytesIO(data)
        headers={'Content-Length':str(len(archive)-offset),'X-Content-Total-Bytes':str(len(archive)),
            'X-Content-SHA256':digest(archive),'Content-Range':f'bytes {offset}-{len(archive)-1}/{len(archive)}'}
        response=SimpleNamespace(status=206 if offset else 200,getheader=lambda k:headers[k],read=stream.read)
        connection=MagicMock();return connection,response

    def test_complete_archive_keeps_all_receipt_pins_including_batch_files(self):
        with tempfile.TemporaryDirectory() as td:
            package,here,payloads,archive=self.fixture(Path(td))
            with patch.object(client,'PACKAGE',package),patch.object(client,'HERE',here),\
                    patch.object(client,'request',return_value=self.response(archive)),\
                    patch.object(client.shutil,'disk_usage',return_value=SimpleNamespace(free=4*2**30)):
                target=client.retrieve(budget=lambda:100.)
            self.assertEqual((target/'history/NETATMO/encoded/batches/000001.npz').read_bytes(),payloads['history/NETATMO/encoded/batches/000001.npz'])
            self.assertTrue(client.read(here/'RETRIEVAL_RECEIPT.json')['all_stage_outputs_verified'])

    def test_retained_partial_transfer_resumes_at_its_existing_offset(self):
        with tempfile.TemporaryDirectory() as td:
            package,here,payloads,archive=self.fixture(Path(td));offset=101
            (here/'result.part').write_bytes(archive[:offset]);client.write(here/'RESULT_TRANSFER_META.json',dict(bytes=len(archive),sha256=digest(archive)))
            with patch.object(client,'PACKAGE',package),patch.object(client,'HERE',here),\
                    patch.object(client,'request',return_value=self.response(archive,offset)) as request,\
                    patch.object(client.shutil,'disk_usage',return_value=SimpleNamespace(free=4*2**30)):
                client.retrieve(budget=lambda:100.)
            self.assertEqual(request.call_args.kwargs['headers'],{'Range':'bytes=101-'})
            self.assertEqual((here/'result.tar').read_bytes(),archive)

    def test_broken_stream_reconnects_without_restarting_download_or_science(self):
        with tempfile.TemporaryDirectory() as td:
            package,here,payloads,archive=self.fixture(Path(td));offsets=[]
            def request(route,**kw):
                value=kw.get('headers') or {};offset=int(value.get('Range','bytes=0-')[6:-1]);offsets.append(offset)
                return self.response(archive,offset,truncate=101 if len(offsets)==1 else None)
            with patch.object(client,'PACKAGE',package),patch.object(client,'HERE',here),\
                    patch.object(client,'request',side_effect=request),\
                    patch.object(client.shutil,'disk_usage',return_value=SimpleNamespace(free=4*2**30)):
                client.retrieve(budget=lambda:100.)
            self.assertEqual(offsets,[0,101]);self.assertEqual((here/'result.tar').read_bytes(),archive)

    def test_insufficient_disk_stops_before_downloading_or_extracting(self):
        with tempfile.TemporaryDirectory() as td:
            package,here,payloads,archive=self.fixture(Path(td))
            with patch.object(client,'PACKAGE',package),patch.object(client,'HERE',here),\
                    patch.object(client,'request',return_value=self.response(archive)),\
                    patch.object(client.shutil,'disk_usage',return_value=SimpleNamespace(free=2**30-1)):
                with self.assertRaisesRegex(ValueError,'DISK_HEADROOM'):client.retrieve(budget=lambda:100.)
            self.assertFalse((here/'result.part').exists());self.assertFalse((package/'retrieved').exists())


if __name__=='__main__':unittest.main(verbosity=2)
