"""CLI persistida em diretórios temporários e processo separado."""
from contextlib import redirect_stdout, redirect_stderr, closing
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from medassistmultimodal.demo import persistence
from medassistmultimodal.demo.__main__ import main


class PersistedDemoCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.patch=patch.object(persistence,'ROOT',self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def run_cli(self,*args):
        out,err=StringIO(),StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            status=main(args)
        return status,out.getvalue(),err.getvalue()

    def test_persist_reopen_list_and_repeat_without_duplicates(self):
        status,first,error=self.run_cli('persist')
        self.assertEqual((status,error),(0,''))
        payload=json.loads(first)
        self.assertEqual(len(payload['cases']),2)
        status,second,_=self.run_cli('list')
        self.assertEqual(status,0)
        self.assertEqual(json.loads(second),payload)
        self.assertEqual(self.run_cli('persist')[0],2)
        self.assertEqual(self.run_cli('persist','--reuse-db')[0],0)
        with closing(sqlite3.connect(self.root/persistence.DEFAULT_DATABASE)) as db:
            for table in ('synthetic_patient_contexts','multimodal_sessions','multimodal_events','audit_records'):
                self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0],2)
        for case in payload['cases']:
            event=case['events'][0]
            self.assertEqual(event['session_id'],case['session']['session_id'])
            self.assertTrue(event['is_mock'])
            self.assertIsNone(event['confidence'])
            self.assertEqual(event['review_status'],'pending_review')

    def test_export_matches_database_and_never_overwrites(self):
        self.run_cli('persist')
        output='data/interim/demo/export.json'
        status,text,_=self.run_cli('export','--output',output)
        self.assertEqual(status,0)
        path=self.root/output
        original=path.read_bytes()
        self.assertEqual(json.loads(original),json.loads(text))
        self.assertEqual(self.run_cli('export','--output',output)[0],2)
        self.assertEqual(path.read_bytes(),original)

    def test_filter_session_and_missing_session(self):
        _,text,_=self.run_cli('persist')
        identifier=json.loads(text)['cases'][0]['session']['session_id']
        _,text,_=self.run_cli('list','--session-id',identifier)
        self.assertEqual(len(json.loads(text)['cases']),1)
        _,text,_=self.run_cli('list','--session-id','00000000-0000-0000-0000-000000000099')
        self.assertEqual(json.loads(text)['cases'],[])

    def test_missing_database_read_does_not_create_it(self):
        self.assertEqual(self.run_cli('list')[0],2)
        self.assertFalse((self.root/persistence.DEFAULT_DATABASE).exists())

    def test_paths_outside_demo_and_private_rejected_lexically(self):
        for path in ('other.sqlite3','data/interim/demo/../wrong.sqlite3','_backup/no.sqlite3','.git/no.sqlite3'):
            with self.subTest(path=path):
                self.assertEqual(self.run_cli('persist','--database',path)[0],2)
        self.assertFalse((self.root/'data').exists())

    def test_existing_divergent_patient_is_preserved(self):
        self.run_cli('persist')
        database=self.root/persistence.DEFAULT_DATABASE
        with closing(sqlite3.connect(database)) as db:
            original=json.loads(db.execute("SELECT payload FROM synthetic_patient_contexts WHERE patient_id='PAT-001'").fetchone()[0])
            original['patient']['display_name']='Outro nome fictício'
            value=json.dumps(original)
            db.execute("UPDATE synthetic_patient_contexts SET payload=? WHERE patient_id='PAT-001'",(value,))
            db.commit()
        self.assertEqual(self.run_cli('persist','--reuse-db')[0],2)
        with closing(sqlite3.connect(database)) as db:
            self.assertEqual(db.execute("SELECT payload FROM synthetic_patient_contexts WHERE patient_id='PAT-001'").fetchone()[0],value)

    def test_legacy_fixture_command_stays_offline(self):
        status,text,_=self.run_cli()
        self.assertEqual(status,0)
        self.assertEqual(json.loads(text)['mode'],'synthetic_fixture_only')
        self.assertFalse((self.root/'data').exists())

    def test_real_subprocess_end_to_end(self):
        project=Path(__file__).resolve().parents[2]
        parent=project/'data/interim/demo'
        parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            database=str(Path(directory)/'process.sqlite3')
            output=str(Path(directory)/'process.json')
            environment=dict(os.environ,PYTHONPATH=str(project/'src'),PYTHONDONTWRITEBYTECODE='1')
            for arguments in (['persist'],['persist','--reuse-db'],['list'],['export','--output',output]):
                result=subprocess.run([sys.executable,'-B','-S','-m','medassistmultimodal.demo',
                                       *arguments,'--database',database],env=environment,
                                      capture_output=True,text=True,encoding='utf-8')
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(len(json.loads(result.stdout)['cases']),2)
            self.assertTrue(Path(output).is_file())
