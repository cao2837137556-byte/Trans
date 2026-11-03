"""Persist the public directory entries observed through the registered IAB.

The directory browser does not publish sizes. This records names, not raw
qualification, and contains no registration fields, cookies or session tokens.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent
BASE = 'https://cicresearch.ca/IOTDataset/CICIoMT2024/'

def build():
    records = []
    def add(directory, subdirectories=(), files=()):
        records.append({'directory': directory,
                        'browse_url': BASE+'browse.php?'+urlencode({'p': directory}),
                        'subdirectories': list(subdirectories),
                        'files': [{'relative_path': '/'.join(x for x in [directory,n] if x),
                                   'download_url': BASE+'download.php?'+urlencode({'file':'/'.join(x for x in [directory,n] if x)}),
                                   'bytes': None, 'raw_acquired': False}
                                  for n in files]})
    add('', ['Bluetooth','WiFI_and_MQTT'], ['README.pdf'])
    add('WiFI_and_MQTT', ['attacks','profiling'], ['README_Wifi_and_MQTT_attacks.pdf'])
    add('WiFI_and_MQTT/profiling', ['CSV','PCAP'], ['README_profiling.pdf'])
    p = 'WiFI_and_MQTT/profiling/PCAP'
    add(p, ['Active','Broker','Idle','Interactions','Power'])
    add(p+'/Idle', files=['Idle.pcap'])
    add(p+'/Active', files=['Active.pcap'])
    devices = ['Blink_Camera','Ecobee_Camera','M1T_Camera','Multifunctional_Pager','Owltron_Camera','SenseU','Singcall']
    add(p+'/Interactions', devices)
    add(p+'/Power', files=[d+'_Power.pcap' for d in ['Blink_Mini_Camera','Ecobee_Camera','M1T_Camera','Multifunctional_Pager','Owltron_Camera','SenseUBaby','Singcall']])
    actions = {
        'Blink_Camera': ['LAN_MIC','LAN_WATCH','WAN_MIC','WAN_WATCH'],
        'Ecobee_Camera': ['LAN_MIC','LAN_WATCH','WAN_MIC','WAN_WATCH'],
        'M1T_Camera': ['LAN_MIC','LAN_PHOTO','LAN_PRECORDING','LAN_WATCH','WAN_MIC','WAN_PHOTO','WAN_RECORDING','WAN_WATCH'],
        'Multifunctional_Pager': ['LAN_APP','LAN_PHYSICAL','WAN_APP','WAN_PHYSICAL'],
        'Owltron_Camera': ['LAN_MIC','LAN_PHOTO','LAN_RECORDING','LAN_WATCH','WAN_MIC','WAN_PHOTO','WAN_RECORDING','WAN_WATCH'],
        'SenseU': ['LAN_EMERGENCY','WAN_EMERGENCY'],
        'Singcall': ['LAN_PHYSICAL','WAN_PHYSICAL'],
    }
    for d in devices:
        add(p+'/Interactions/'+d, files=[d+'_'+a+'.pcap' for a in actions[d]])
    a = 'WiFI_and_MQTT/attacks'
    add(a, ['CSV','PCAP'])
    add(a+'/PCAP', ['test','train'])
    common = ['ARP_Spoofing','Benign','MQTT-DDoS-Connect_Flood','MQTT-DDoS-Publish_Flood','MQTT-DoS-Connect_Flood','MQTT-DoS-Publish_Flood','MQTT-Malformed_Data','Recon-OS_Scan','Recon-Ping_Sweep','Recon-Port_Scan','Recon-VulScan']
    test = common + ['TCP_IP-DDoS-ICMP1','TCP_IP-DDoS-ICMP2','TCP_IP-DDoS-SYN','TCP_IP-DDoS-TCP','TCP_IP-DDoS-UDP1','TCP_IP-DDoS-UDP2','TCP_IP-DoS-ICMP','TCP_IP-DoS-SYN','TCP_IP-DoS-TCP','TCP_IP-DoS-UDP']
    train = common[:]
    for category, amount in [('DDoS-ICMP',8),('DDoS-SYN',4),('DDoS-TCP',4),('DDoS-UDP',8),('DoS-ICMP',4),('DoS-SYN',4),('DoS-TCP',4),('DoS-UDP',4)]:
        train += ['TCP_IP-'+category+str(i) for i in range(1,amount+1)]
    add(a+'/PCAP/test', files=[n+'_test.pcap' for n in test])
    add(a+'/PCAP/train', files=[n+'_train.pcap' for n in train])
    all_files = [f for r in records for f in r['files']]
    readmes = json.loads((ROOT/'README_DOWNLOAD_RECEIPT.json').read_text(encoding='utf-8'))
    manifest = {
        'schema':'CICIOMT2024_REGISTERED_DIRECTORY_V1',
        'status':'DIRECTORY_AND_THREE_READMES_ACQUIRED_RAW_QUALIFICATION_PENDING',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'user_facing_date':'2026-11-02',
        'source':'Registered official IAB directory, observed live and transcribed into normalized entries',
        'registration_information_saved':False,
        'credentials_or_session_tokens_exported':False,
        'directory_page_count':len(records),
        'pcap_count_in_observed_scope':sum(f['relative_path'].endswith('.pcap') for f in all_files),
        'scope_exclusions':['Bluetooth','CSV','profiling/PCAP/Broker'],
        'sizes_exposed_by_directory':False,
        'independent_HEAD_status':403,
        'readmes':readmes,
        'directories':records,
        'raw_download_bytes':0,
        'external_model_evaluation_started':False,
    }
    (ROOT/'REGISTERED_DIRECTORY_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raw_base='WiFI_and_MQTT/'
    candidates=[
        ('NORMAL_CHRONOLOGY',raw_base+'profiling/PCAP/Idle/Idle.pcap'),
        ('NORMAL_ACTIVE_AND_CHRONOLOGY',raw_base+'profiling/PCAP/Active/Active.pcap'),
        ('TCP_FLAGS_AND_DIRECTION_CANDIDATE',raw_base+'attacks/PCAP/test/TCP_IP-DoS-TCP_test.pcap'),
        ('TCP_FLAGS_AND_DIRECTION_CANDIDATE',raw_base+'attacks/PCAP/test/TCP_IP-DDoS-TCP_test.pcap'),
        ('UDP_DIRECTION_CANDIDATE',raw_base+'attacks/PCAP/test/TCP_IP-DoS-UDP_test.pcap'),
        ('UDP_DIRECTION_CANDIDATE',raw_base+'attacks/PCAP/test/TCP_IP-DDoS-UDP1_test.pcap'),
        ('UDP_DIRECTION_CANDIDATE',raw_base+'attacks/PCAP/test/TCP_IP-DDoS-UDP2_test.pcap'),
    ]
    indexed={f['relative_path']:f for f in all_files}
    shortlist={
        'schema':'CICIOMT2024_RAW_QUALIFICATION_CANDIDATES_V1',
        'status':'CANDIDATES_IDENTIFIED_SIZES_AND_ROLE_QUALIFICATION_PENDING',
        'not_a_final_minimum_byte_selection':True,
        'candidates':[{'role':role,**indexed[path]} for role,path in candidates],
        'selection_uses_model_scores':False,
        'additional_normal_interaction_policy':'All seven observed real-device directories are inventoried; supplement only where Active does not establish the required normal behavior, before scoring.',
        'train_test_directory_not_assumed_chronological':True,
        'direct_ACK_verified':False,
        'direct_UDP_direction_verified':False,
        'same_device_7200s_and_later_normal_verified':False,
        'unknowns':['Actual PCAP bytes and range/resume support','Device MAC/IP/attacker/target mapping','Physical capture chronology and duplicates between train/test','Direct ACK=1,SYN=0 attack evidence rather than reverse responses','Per-device normal coverage and independent event counts'],
    }
    (ROOT/'RAW_QUALIFICATION_CANDIDATES.json').write_text(json.dumps(shortlist,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name in ['README_DOWNLOAD_RECEIPT.json','REGISTERED_DIRECTORY_MANIFEST.json','RAW_QUALIFICATION_CANDIDATES.json']:
        path=ROOT/name
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_name(name+'.sha256').write_text(digest+'  '+name+'\n',encoding='ascii')
    print(json.dumps({'pages':len(records),'pcaps':manifest['pcap_count_in_observed_scope'],'readmes':len(readmes),'readme_bytes':sum(r['bytes'] for r in readmes),'qualification_candidates':len(candidates)},indent=2))

if __name__=='__main__':
    build()
