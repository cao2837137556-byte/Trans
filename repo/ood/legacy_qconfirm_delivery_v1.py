"""Future data packaging is separately authorized; safe on import."""
from pathlib import Path
import argparse,tarfile,json
import legacy_qref_common_v1 as c
import legacy_qconfirm_common_v1 as d

def package_inputs(root,scope_path,output,explicit):
    # Packaging reads protected query bytes/PCAP; no implementation-only authority permits it.
    scope=c.read(scope_path)
    c.require(explicit and scope.get('execution_authorized') is True and scope.get('package_inputs') is True,'INPUT_PACKAGING_NOT_AUTHORIZED')
    c.require(scope.get('recipe_sha256')==d.DESIGN_SHA and scope.get('stages')==d.STAGES and scope.get('retries')==0,'PACKAGING_SCOPE')
    c.require(scope.get('training') is False and scope.get('calibration') is False,'PACKAGING_BOUNDARY')
    output=Path(output).resolve();c.require(not output.exists() and output.parent.is_dir(),'PACKAGE_OUTPUT')
    plan=d.recipe(root);assets=c.read(Path(root)/d.DESIGN/'asset_candidates.json')['assets']
    items=[(c.confined(root,plan['data']['query']['path']),plan['data']['query']['path'].replace('\\','/'),plan['data']['query']['sha256'])]
    for a in assets:
        if not a['historical_package_contains']:items.append((Path(a['local']),'inputs/raw/'+a['capture_id']+'.pcap',a['sha256']))
    # Keep candidate superset; never inspect query contents to tune data selection.
    try:
        with tarfile.open(output,'x:gz') as t:
            for p,name,h in items:c.pin(p,h);t.add(p,arcname=name,recursive=False)
        receipt=dict(status='INPUT_PACKAGE_COMPLETE',members=len(items),sha256=c.sha(output),query_rows=341222,PCAP_candidates=65,uploaded=False)
        c.write(output.with_suffix(output.suffix+'.json'),receipt)
        output.with_name(output.name+'.sha256').write_text(receipt['sha256']+'  '+output.name+'\n',encoding='utf-8')
        return receipt
    except BaseException:
        # Preserve partial archive; explicit failed package is never silently overwritten.
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--authorization',required=True);p.add_argument('--out',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(json.dumps(package_inputs(a.root,a.authorization,a.out,a.execute),indent=2))
