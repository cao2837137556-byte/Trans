"""Qualify one already-downloaded archive member; no feature/model execution."""
import audit as a
import importlib.util
import shutil
import subprocess
import time
import zipfile

DEST=a.ROOT.parent.parent/'data_external/unsw_iotraffic_2025/raw_selected'
MEMBER='pcaps/NetatmoWelcome_70ee50183443.pcap'

def main():
    start=time.monotonic()
    archive=DEST.parent/'pcaps.zip'
    receipt=a.read(a.ROOT/'runs/targeted_normal_raw_qualification_v1_20261031/ARCHIVE_INTEGRITY.json')
    stat=archive.stat()
    assert stat.st_size==receipt['bytes'] and stat.st_mtime_ns==receipt['mtime_ns']
    assert a.sha(archive)==receipt['expected_sha256']
    target=DEST/'NetatmoWelcome_70ee50183443.pcap'
    assert not target.exists() and not target.with_suffix('.pcap.part').exists()
    with zipfile.ZipFile(archive) as z:
        info=z.getinfo(MEMBER)
        assert shutil.disk_usage(DEST).free-info.file_size>8*1024**3
        count=0;digest=a.hashlib.sha256();temp=target.with_suffix('.pcap.part')
        with z.open(MEMBER) as source,temp.open('xb') as out:
            for block in iter(lambda:source.read(4*1024**2),b''):
                out.write(block);digest.update(block);count+=len(block)
        assert count==info.file_size
        temp.rename(target)
        spec=dict(device='Netatmo Welcome Camera',owner_MAC='70:ee:50:18:34:43',member=MEMBER,path=str(target),
            bytes=count,sha256=digest.hexdigest(),crc32=f'{info.CRC:08x}',zip_crc_verified=True)
    assert a.sha(target)==spec['sha256']
    a.write('NETATMO_EXTRACTION.json',dict(status='PASS',archive_sha256=receipt['expected_sha256'],member=spec,
        elapsed_seconds=time.monotonic()-start,downloads=0))
    print('EXTRACTED_AND_HASH_VERIFIED',count,flush=True)
    command=['C:/Program Files/Wireshark/capinfos.exe','-M','-S',str(target)]
    run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',check=True,timeout=120)
    (a.HERE/(target.stem+'.capinfos.txt')).write_text(run.stdout,encoding='utf-8')
    src=a.pin(a.ROOT/'runs/targeted_normal_raw_qualification_v1_20261031/qualify_raw.py')
    module_spec=importlib.util.spec_from_file_location('raw_qualification_reuse',src)
    module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
    module.RUN=a.HERE
    stats=module.scan(spec)
    assert stats['counts']['owner_present_packets']==stats['counts']['packets']
    assert stats['counts'].get('packets_at_or_after_2018_01_01',0)==0
    assert a.sha(target)==spec['sha256']
    end=archive.stat();assert (stat.st_size,stat.st_mtime_ns)==(end.st_size,end.st_mtime_ns)
    a.write('NETATMO_RAW_ACCEPTANCE.json',dict(status='STRUCTURAL_METADATA_PASS_REFERENCE_ADMISSION_PENDING',
        member=spec,independent_checks=stats['independent_checks'],all_packets_owner_present=True,
        all_packets_before_2018=True,normality='Publisher normal-source assumption, no packet-level benign certification',
        statistics_sha256=a.sha(a.HERE/(target.stem+'.raw_stats.json')),qualification_code_sha256=a.sha(src),
        new_features=0,new_references=0,new_experiments=0,script_sha256=a.sha(__file__)))
    print('NETATMO_RAW_ACCEPTED_FOR_DESIGN',flush=True)

if __name__=='__main__':main()
