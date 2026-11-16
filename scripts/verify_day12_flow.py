"""Verify prescription fixtures through CLI, SQLite, evidence and export."""
from contextlib import closing,redirect_stdout,redirect_stderr
from collections import Counter
import argparse
import io
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import UUID,uuid5

from medassistmultimodal.application.register_vitals import encode_json,strict_json
from medassistmultimodal.demo import prescriptions_cli as cli
from medassistmultimodal.demo.prescription_fixtures import build_prescription_cases

ROOT=Path(__file__).resolve().parents[1]
NAMESPACE=UUID('d012d012-0000-4000-8000-000000000005')


def check(value,message):
    if not value:raise ValueError(message)


def invoke(args,expected=0):
    out=io.StringIO();err=io.StringIO()
    with redirect_stdout(out),redirect_stderr(err):status=cli.main(args)
    check(status==expected,f'Unexpected CLI exit: {args[0]} / {err.getvalue()}')
    return strict_json(out.getvalue().encode('utf-8')) if status==0 else {'error':err.getvalue().strip()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='data/interim/prescriptions/day12_closeout_v1')
    args=parser.parse_args()
    output=cli.safe_path(args.output+'/marker.json','interim/prescriptions','.json').parent
    check(not output.exists(),'Output exists; previous evidence preserved')
    previous=strict_json((ROOT/'reports/DAY_12_TASK_03_2026-11-05.json').read_bytes())
    for name,sha in previous['sha256'].items():
        check(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,f'Prior hash changed: {name}')
    output.mkdir(parents=True,exist_ok=False)
    database=(output/'prescriptions.sqlite3').relative_to(ROOT).as_posix()
    cases,refs=build_prescription_cases();receipts={};rejected={}
    for key,payload in cases.items():
        path=output/f'{key}_input.json';path.write_bytes(encode_json(payload))
        run=uuid5(NAMESPACE,output.relative_to(ROOT).as_posix()+':'+key)
        command=['persist','--database',database,'--input',path.relative_to(ROOT).as_posix(),
                 '--run-id',str(run)]
        if receipts:command.append('--reuse-db')
        if key in refs['rejected']:
            rejected[key]=invoke(command,expected=2);continue
        first=invoke(command)
        retry=invoke(command if '--reuse-db' in command else command+['--reuse-db'])
        check(first==retry,'Retry receipt changed')
        receipts[key]=first
    listed=invoke(['list','--database',database])
    export=output/'events.json'
    check(invoke(['export','--database',database,'--output',export.relative_to(ROOT).as_posix()])==listed,
          'Export mismatch')
    kinds=Counter();matches=[]
    for key,receipt in receipts.items():
        artifact=cli.safe_path(receipt['evidence_ref'],'interim/prescriptions','.json')
        content=strict_json(artifact.read_bytes())
        changes=content['result']['changes']
        actual=[{'kind':c['kind'],'item_id':c['item_id'],'fields':[f['field'] for f in c['field_changes']]} for c in changes]
        check(actual==refs['changes'][key],f'Reference mismatch {key}')
        matches.append({'case_id':key,'changes':len(changes),'exact_match':True})
    for case in listed['cases']:
        for event in case['events']:
            path,fragment=event['evidence_ref'].split('#');hashpart,item=fragment.split('&item=')
            raw=cli.safe_path(path,'interim/prescriptions','.json').read_bytes()
            check(hashlib.sha256(raw).hexdigest()==hashpart.removeprefix('sha256='),'Evidence mismatch')
            node=strict_json(raw)
            for part in item.strip('/').split('/'):
                node=node[int(part)] if isinstance(node,list) else node[part]
            check(event['review_status']=='pending_review' and not event['is_mock'],'Event state mismatch')
            check(event['source_kind']=='synthetic' and event['patient_id']=='PAT-001','Origin mismatch')
            kinds['summary' if item=='/summary' else node['kind']]+=1
    with closing(sqlite3.connect((ROOT/database).as_uri()+'?mode=ro',uri=True)) as db:
        counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in
                ('multimodal_sessions','multimodal_events','audit_records')}
        check(list(counts.values())==[17,30,17],'Incorrect counts after retries/rejections')
        check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','Integrity failure')
        check(not db.execute('PRAGMA foreign_key_check').fetchall(),'Foreign key failure')
    result={'date':'2026-11-05','counts_after_retries_and_rejections':counts,'event_kinds':dict(kinds),
        'valid_cases':matches,'rejected_cases':rejected,'all_references_match':True,
        'all_evidence_hashes_and_items_verified':True,'clinical_validation':False,
        'export_sha256':hashlib.sha256(export.read_bytes()).hexdigest()}
    (output/'verification.json').write_bytes(encode_json(result))
    print(json.dumps({'counts':counts,'event_kinds':dict(kinds),'rejections':len(rejected)},indent=2))


if __name__=='__main__':main()
