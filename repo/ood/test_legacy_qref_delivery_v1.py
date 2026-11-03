"""stdlib Linux/Windows metadata closure and lifecycle checks; no ML dependency."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import tarfile
import unittest
import legacy_qref_common_v1 as c
import legacy_qref_delivery_v1 as d


class Delivery(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='qref_delivery_');self.root=Path(self.tmp.name)

    def tearDown(self):self.tmp.cleanup()

    def assets(self):
        pins={}
        for path,value in zip(d.REPORT_INPUTS,[{'excluded':True},[{'context_reasons':{'unsupported':3}}]]):
            p=c.confined(self.root,path);p.parent.mkdir(parents=True,exist_ok=True);c.write(p,value);pins[path]=c.sha(p)
        return pins

    def test_report_dependencies_clean_directory(self):
        report=d.coverage(self.root,self.assets())
        self.assertEqual(report['preparation_context_exclusions']['unsupported'],3)

    def test_missing_old_failure_file_is_preflight_error(self):
        pins=self.assets();c.confined(self.root,d.REPORT_INPUTS[0]).unlink()
        with self.assertRaises(FileNotFoundError):d.coverage(self.root,pins)

    def test_receipts_not_silently_omitted(self):
        pins=self.assets();del pins[d.REPORT_INPUTS[1]]
        with self.assertRaisesRegex(c.Stop,'UNPINNED'):d.coverage(self.root,pins)

    def test_changed_report_metadata_rejected(self):
        pins=self.assets();c.confined(self.root,d.REPORT_INPUTS[1]).write_text('[]')
        with self.assertRaisesRegex(c.Stop,'IDENTITY'):d.coverage(self.root,pins)

    def test_status_pending_ignored(self):
        p=c.Progress(self.root/'run',10);(p.out/'progress'/'99999999.pending').write_text('partial')
        self.assertEqual(c.status(p.out)['status'],'RUNNING')

    def test_failure_visible_and_no_retry(self):
        p=c.Progress(self.root/'run',10);p.done=3;p.finish('STOPPED_NO_RETRY',error='synthetic')
        s=c.status(p.out);self.assertEqual(s['completed_updates'],3);self.assertEqual(s['retries'],0)
        self.assertEqual(s['status'],'STOPPED_NO_RETRY')

    def test_late_seal_failure_latest_status_wins(self):
        p=c.Progress(self.root/'run',0);p.finish('COMPLETE');p.finish('STOPPED_NO_RETRY',error='seal failure')
        self.assertEqual(c.status(p.out)['status'],'STOPPED_NO_RETRY')

    def test_open_reader_does_not_require_replacing_file(self):
        p=c.Progress(self.root/'run',10);f=next((p.out/'progress').glob('*.json'))
        with f.open() as reader:p.emit();self.assertIn('RUNNING',reader.read())

    def test_success_seal_roundtrip(self):
        p=c.Progress(self.root/'run',0);p.finish('COMPLETE');c.seal(p.out);c.verify(p.out)

    def test_resource_accounting_positive(self):self.assertGreater(c.rss_bytes(),0)

    def test_package_roundtrip_and_refuse_overwrite(self):
        impl=self.root/c.IMPLEMENTATION_REL;impl.mkdir(parents=True)
        source=self.root/'code.py';source.write_text('pass\n')
        c.write(impl/'code_pins.json',{'code.py':c.sha(source)})
        c.write(impl/'input_pins.json',{})
        c.write(impl/'acceptance.json',{'status':'SYNTHETIC_FIXTURE_ONLY'})
        c.seal(impl)
        recipe=self.root/c.RECIPE_REL;recipe.parent.mkdir(parents=True);recipe.write_text('{}')
        Path(str(recipe)+'.sha256').write_text(c.sha(recipe)+'  '+recipe.name+'\n')
        archive=self.root/'delivery.tar.gz';receipt=d.package(self.root,archive)
        self.assertEqual(receipt['sha256'],c.sha(archive))
        extracted=self.root/'unpacked';extracted.mkdir()
        with tarfile.open(archive) as tar:
            self.assertTrue(all(not Path(x.name).is_absolute() and '..' not in Path(x.name).parts for x in tar.getmembers()))
            tar.extractall(extracted)
        c.verify(extracted);c.verify(extracted/c.IMPLEMENTATION_REL)
        self.assertFalse(c.read(extracted/'DELIVERY.json')['real_execution_authorized'])
        with self.assertRaisesRegex(c.Stop,'PACKAGE_EXISTS'):d.package(self.root,archive)

    def test_report_file_missing_is_not_synthetic_success(self):
        pins=self.assets();c.confined(self.root,d.REPORT_INPUTS[1]).unlink()
        with self.assertRaises(FileNotFoundError):d.coverage(self.root,pins)


if __name__=='__main__':unittest.main(verbosity=2)
