"""Reproduce the complete synthetic corpus through CLI/SQLite and verify evidence."""
import argparse
from collections import Counter
from contextlib import closing, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import time
from uuid import UUID, uuid5

from medassistmultimodal.application.register_vitals import encode_json, strict_json
from medassistmultimodal.demo import vitals_cli

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = UUID('f20fd16a-0a28-4b33-a988-281f1f7b7580')


def cli(args):
    stream = io.StringIO()
    with redirect_stdout(stream):
        status = vitals_cli.main(args)
    if status:
        raise ValueError(f'CLI failed: {args[0]}')
    return strict_json(stream.getvalue().encode('utf-8'))


def check(condition, message):
    if not condition:
        raise ValueError(message)


def key(item):
    return (item['channel'], item['direction'], item['first_index'],
            item['last_index'], item['confirmed_index'], item['termination'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='data/interim/vitals/day11_closeout_v1')
    args = parser.parse_args()
    output = vitals_cli.safe_path(args.output + '/marker.json','interim/vitals','.json').parent
    check(not output.exists(), 'Output already exists; previous results preserved')
    # Verify approved sources and previously generated artifacts before any new run.
    for receipt in ('DAY_11_TASK_02_2026-11-03.json','DAY_11_TASK_03_2026-11-03.json',
                    'DAY_11_TASK_04_2026-11-03.json'):
        previous = strict_json((ROOT/'reports'/receipt).read_bytes())
        for name, sha in previous['sha256'].items():
            check(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha, f'Prior hash changed: {name}')
    bundle = ROOT/'data/synthetic/vitals_v1'
    manifest = strict_json((bundle/'manifest.json').read_bytes())
    for name in [f'V{i:02d}.json' for i in range(1,19)]+['references.json']:
        data=(bundle/name).read_bytes()
        check(hashlib.sha256(data).hexdigest()==manifest['files'][name]['sha256'], f'Input changed: {name}')
    output.mkdir(parents=True,exist_ok=False)
    database=(output/'vitals.sqlite3').relative_to(ROOT).as_posix()
    elapsed=[]
    receipts=[]
    for i in range(1,19):
        run=uuid5(NAMESPACE,f'day11:{output.relative_to(ROOT).as_posix()}:V{i:02d}')
        command=['persist','--database',database,'--input',f'data/synthetic/vitals_v1/V{i:02d}.json',
                 '--run-id',str(run)]
        if i>1: command.append('--reuse-db')
        start=time.perf_counter()
        first=cli(command)
        elapsed.append(time.perf_counter()-start)
        retry=cli(command if i>1 else command+['--reuse-db'])
        check(first==retry, 'Retry changed registration receipt')
        receipts.append(first)
    listed=cli(['list','--database',database])
    export=output/'events.json'
    exported=cli(['export','--database',database,'--output',export.relative_to(ROOT).as_posix()])
    check(exported==listed==strict_json(export.read_bytes()),'Export differs from query')
    check(len(listed['cases'])==18,'Incorrect session count')
    # Verify evidence hash + referenced JSON-pointer item for every persisted event.
    kinds=Counter()
    by_scenario={}
    for case in listed['cases']:
        for event in case['events']:
            path,fragment=event['evidence_ref'].split('#')
            hash_part,item_part=fragment.split('&item=')
            data=vitals_cli.safe_path(path,'interim/vitals','.json').read_bytes()
            check(hashlib.sha256(data).hexdigest()==hash_part.removeprefix('sha256='),'Evidence hash mismatch')
            document=strict_json(data)
            cursor=document
            for part in item_part.strip('/').split('/'):
                cursor=cursor[int(part)] if isinstance(cursor,list) else cursor[part]
            check(event['review_status']=='pending_review' and not event['is_mock'], 'Incorrect event state')
            check(event['patient_id']=='PAT-001' and event['source_kind']=='synthetic','Incorrect origin')
            if item_part=='/summary':kinds['summary']+=1
            elif '/occurrences/' in item_part:kinds['occurrence']+=1
            else:kinds['quality']+=1
            by_scenario[document['scenario_id']]=document['result']
    references=strict_json((bundle/'references.json').read_bytes())['scenarios']
    metrics={}
    matches=[]
    for i in range(1,19):
        scenario=f'V{i:02d}'
        actual=by_scenario[scenario]
        ref=references[scenario]
        pred=Counter(key(x) for x in actual['occurrences'])
        truth=Counter(key(x) for x in ref['threshold_occurrences'])
        check(pred==truth,f'Occurrence mismatch {scenario}')
        qkey=lambda q:(q['channel'],q['first_index'],q['last_index'],q['quality'],q['reason'])
        check(Counter(map(qkey,actual['quality_intervals']))==Counter(map(qkey,ref['quality_intervals'])),f'Quality mismatch {scenario}')
        matches.append({'scenario_id':scenario,'occurrences':len(actual['occurrences']),
                        'quality_intervals':len(actual['quality_intervals']),'exact_match':True,
                        'coverage':actual['coverage']})
        for channel,direction in [('heart_rate','low'),('heart_rate','high'),('spo2','low'),
                                  ('systolic','low'),('systolic','high'),('diastolic','low'),('diastolic','high')]:
            rule=channel+'_'+direction
            counts=metrics.setdefault(rule,{'tp':0,'fp':0,'fn':0})
            a=Counter({k:v for k,v in pred.items() if k[:2]==(channel,direction)})
            b=Counter({k:v for k,v in truth.items() if k[:2]==(channel,direction)})
            counts['tp']+=sum((a&b).values()); counts['fp']+=sum((a-b).values()); counts['fn']+=sum((b-a).values())
    for counts in metrics.values():
        tp,fp,fn=counts.values()
        counts.update(precision=tp/(tp+fp) if tp+fp else None,
                      recall=tp/(tp+fn) if tp+fn else None,
                      f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
    with closing(sqlite3.connect((ROOT/database).as_uri()+'?mode=ro',uri=True)) as db:
        counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in
                ('multimodal_sessions','multimodal_events','audit_records')}
        check(list(counts.values())==[18,43,18],'Incorrect counts after retries')
        check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','Database integrity failure')
        check(not db.execute('PRAGMA foreign_key_check').fetchall(),'Foreign key failure')
    summary={'date':'2026-11-03','clinical_validation':False,'independent_evaluation':False,
        'counts_after_retries':counts,'event_kinds':dict(kinds),'scenario_checks':matches,'metrics_by_rule':metrics,
        'nominal_confirmation_latency_seconds':2,'processing_wall_seconds':{'scope':'first persist including evidence+SQLite per scenario; excludes retry/export',
        'total':sum(elapsed),'min':min(elapsed),'max':max(elapsed)},'input_samples':216,
        'all_evidence_hashes_and_items_verified':True,'prior_receipts_hashes_preserved':True,
        'export_sha256':hashlib.sha256(export.read_bytes()).hexdigest()}
    (output/'verification.json').write_bytes(encode_json(summary))
    print(json.dumps({'counts':counts,'event_kinds':dict(kinds),'output':output.relative_to(ROOT).as_posix()},indent=2))


if __name__=='__main__':main()
