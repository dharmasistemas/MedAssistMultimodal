"""Fixtures verificáveis sem provider, mídia ou banco de dados."""
from dataclasses import replace
import contextlib
import io
import json
import unittest

from medassistmultimodal.demo.fixtures import build_demo_cases
from medassistmultimodal.demo.__main__ import main
from medassistmultimodal.domain.events import ReviewStatus, SourceKind


class DemoFixturesTests(unittest.TestCase):
    def test_reproducible_and_independent_instances(self):
        first, second = build_demo_cases(), build_demo_cases()
        self.assertEqual(first, second)
        self.assertIsNot(first[0].session, second[0].session)
        self.assertEqual(len({c.session.session_id for c in first}), len(first))
        events = [e for c in first for e in c.events]
        self.assertEqual(len({e.event_id for e in events}), len(events))

    def test_sources_and_evidence_are_explicitly_artificial(self):
        for case in build_demo_cases():
            for event in case.events:
                event.validate_for_session(case.session)
                self.assertIs(event.source_kind, SourceKind.SYNTHETIC)
                self.assertTrue(event.is_mock)
                self.assertIsNone(event.confidence)
                self.assertIs(event.review_status, ReviewStatus.PENDING_REVIEW)
                self.assertIsNone(event.dataset_id)
                self.assertIsNone(event.participant_ref)
                self.assertIn(case.name, event.evidence_ref)

    def test_patient_sessions_cannot_be_crossed(self):
        first, second = build_demo_cases()
        with self.assertRaises(ValueError):
            first.events[0].validate_for_session(second.session)
        with self.assertRaises(ValueError):
            replace(first.events[0], session_id=second.session.session_id).validate_for_session(second.session)

    def test_cli_outputs_inspectable_json(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(), 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["mode"], "synthetic_fixture_only")
        self.assertFalse(payload["clinical_validation"])
        self.assertEqual(len(payload["cases"]), 2)
        self.assertEqual(payload["cases"][0]["events"][0]["review_status"], "pending_review")
