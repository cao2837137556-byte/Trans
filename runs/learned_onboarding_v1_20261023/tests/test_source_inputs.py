import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import source_inputs as source


def digest(data):
    return hashlib.sha256(data).hexdigest()


class SourceInputTests(unittest.TestCase):
    def fixture(self, root):
        files = {
            'run/prepared/LEARN_q.npy': b'Q' * 1310,
            'run/prepared/receipt.json': b'{}',
            'run/endpoints/QUERY_TAIL_27/head.npz': b'HEAD',
            'run/CIC_DEV/scores.npz': b'TARGET_QUERY_MUST_STAY_SEALED',
            'run/UNSW_DEV/scores.npz': b'TARGET_QUERY_MUST_STAY_SEALED',
        }
        body = io.BytesIO()
        with tarfile.open(fileobj=body, mode='w') as archive:
            for name, payload in files.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(payload)
                archive.addfile(entry, io.BytesIO(payload))
        raw = body.getvalue()
        split = 701
        chunks = [raw[:split], raw[split:]]
        archive_dir = root / 'archive'
        archive_dir.mkdir()
        index = dict(format='tar-stream-concatenate-parts-in-order',
                     complete=True, bytes=len(raw), chunks=[])
        for i, chunk in enumerate(chunks):
            name = 'part-%06d.tar' % i
            (archive_dir / name).write_bytes(chunk)
            index['chunks'].append(dict(name=name, bytes=len(chunk),
                                        sha256=digest(chunk)))
        (archive_dir / 'BACKUP_INDEX.json').write_text(json.dumps(index),
                                                        encoding='utf-8')
        return archive_dir, files

    def test_concatenated_tar_targeted_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, files = self.fixture(root)
            members = source.archive_members(archive)
            self.assertEqual(set(members), set(files))
            destination = root / 'selected'
            selected = source.extract_source_members(archive, destination)
            self.assertEqual((destination / 'run/prepared/LEARN_q.npy').read_bytes(),
                             files['run/prepared/LEARN_q.npy'])
            self.assertNotIn('run/CIC_DEV/scores.npz', selected)
            self.assertNotIn('run/UNSW_DEV/scores.npz', selected)
            self.assertFalse((destination / 'run/CIC_DEV').exists())
            self.assertEqual(selected['run/endpoints/QUERY_TAIL_27/head.npz']
                             ['sha256'], digest(b'HEAD'))
            path = destination / 'run/prepared/receipt.json'
            path.write_bytes(b'{!')
            with self.assertRaisesRegex(ValueError, 'EXTRACTED_MEMBER_DRIFT'):
                source.extract_source_members(archive, destination)

    def test_archive_chunk_hash_and_size_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, _ = self.fixture(root)
            chunk = archive / 'part-000001.tar'
            body = chunk.read_bytes()
            chunk.write_bytes(body[:10] + b'!' + body[11:])
            with self.assertRaisesRegex(ValueError, 'INPUT_SHA256'):
                source.archive_members(archive)
            chunk.write_bytes(body[:-1])
            with self.assertRaisesRegex(ValueError, 'ARCHIVE_CHUNK_SIZE'):
                source.archive_members(archive)

    def test_archive_reader_crosses_chunk_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            archive, _ = self.fixture(Path(temp))
            index = source.read(archive / 'BACKUP_INDEX.json')
            with source.ConcatenatedChunks(archive, index) as stream:
                stream.seek(690)
                self.assertEqual(len(stream.read(30)), 30)
                stream.seek(-5, io.SEEK_END)
                self.assertEqual(len(stream.read()), 5)


if __name__ == '__main__':
    unittest.main()
