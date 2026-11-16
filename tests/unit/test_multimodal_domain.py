from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import unittest
from uuid import UUID

from medassistmultimodal.domain.session import Session, SubjectIdentity, SubjectKind
from medassistmultimodal.domain.events import MultimodalEvent, SourceKind, ReviewStatus


class MultimodalDomainTests(unittest.TestCase):
    def setUp(self):
        self.subject = SubjectIdentity(kind=SubjectKind.SYNTHETIC_PATIENT, patient_id="PAT-001")
        self.session = Session(session_id=UUID(int=1), subject=self.subject,
                               started_at=datetime(2026, 10, 24, tzinfo=timezone.utc))
        self.event = MultimodalEvent(event_id=UUID(int=2), session_id=self.session.session_id,
            subject_kind=self.subject.kind, patient_id="PAT-001", source_kind=SourceKind.SYNTHETIC,
            source="generator:v1", timestamp=self.session.started_at, confidence=None,
            evidence_ref="sample:0")

    def test_synthetic_and_simulated_valid(self):
        self.event.validate_for_session(self.session)
        replace(self.event, source_kind=SourceKind.SIMULATED).validate_for_session(self.session)
        self.assertIs(self.event.review_status, ReviewStatus.PENDING_REVIEW)
        self.assertIsNone(self.event.confidence)

    def test_dataset_valid_without_fictional_patient(self):
        subject = SubjectIdentity(kind=SubjectKind.DATASET_PARTICIPANT,
                                  dataset_id="example:v1", participant_ref="subject-A")
        session = replace(self.session, subject=subject)
        event = replace(self.event, subject_kind=subject.kind, patient_id=None,
                        dataset_id=subject.dataset_id, participant_ref=subject.participant_ref,
                        source_kind=SourceKind.DATASET)
        event.validate_for_session(session)
        self.assertIsNone(event.patient_id)
        with self.assertRaises(ValueError):
            event.validate_for_session(replace(session, subject=replace(subject, dataset_id="other:v1")))

    def test_invalid_identities(self):
        for changes in ({"patient_id": None}, {"patient_id": "PAT-1"},
                        {"patient_id": " PAT-001"}, {"dataset_id": "dataset"},
                        {"participant_ref": "A"}, {"kind": "unknown"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.subject, **changes)
        for values in ({}, {"dataset_id": "v1"},
                       {"dataset_id": "v1", "participant_ref": " "},
                       {"dataset_id": "v1", "participant_ref": "A", "patient_id": "PAT-001"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                SubjectIdentity(kind=SubjectKind.DATASET_PARTICIPANT, **values)

    def test_origin_must_match_subject(self):
        with self.assertRaises(ValueError):
            replace(self.event, source_kind=SourceKind.DATASET)
        for origin in (SourceKind.SYNTHETIC, SourceKind.SIMULATED):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                replace(self.event, subject_kind=SubjectKind.DATASET_PARTICIPANT,
                        patient_id=None, dataset_id="v1", participant_ref="A", source_kind=origin)

    def test_session_binding(self):
        for session in (replace(self.session, session_id=UUID(int=3)),
                        replace(self.session, subject=replace(self.subject, patient_id="PAT-002")), None):
            with self.subTest(session=session), self.assertRaises(ValueError):
                self.event.validate_for_session(session)

    def test_confidence_boundaries(self):
        for value in (None, 0, 1, 0.5):
            self.assertEqual(replace(self.event, confidence=value).confidence, value)
        for value in (-0.01, 1.01, float("nan"), float("inf"), -float("inf"), True, "0.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(self.event, confidence=value)

    def test_uuid_and_timestamps(self):
        for value in (UUID(int=0), "not-a-uuid", str(UUID(int=1)), None):
            for field in ("event_id", "session_id"):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(self.event, **{field: value})
            with self.assertRaises(ValueError):
                replace(self.session, session_id=value)
        for value in (datetime(2026, 10, 24), "2026-10-24", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(self.event, timestamp=value)
            with self.assertRaises(ValueError):
                replace(self.session, started_at=value)
        local = datetime(2026, 10, 24, tzinfo=timezone(timedelta(hours=-3)))
        self.assertEqual(replace(self.event, timestamp=local).timestamp.hour, 3)
        self.assertIs(replace(self.session, started_at=local).started_at.tzinfo, timezone.utc)

    def test_required_references_and_enums(self):
        for field in ("source", "evidence_ref"):
            for value in (None, "", " ", " value "):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(self.event, **{field: value})
        for changes in ({"source_kind": "dataset"}, {"review_status": "approved"},
                        {"is_mock": 1}, {"processor": " "}, {"is_mock": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.event, **changes)
        with self.assertRaises(ValueError):
            replace(self.session, subject=None)

    def test_mock_is_separate_from_input_origin(self):
        event = replace(self.event, is_mock=True, processor="mock_speech:v1")
        self.assertIs(event.source_kind, SourceKind.SYNTHETIC)
        event.validate_for_session(self.session)

    def test_entities_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.event.patient_id = "PAT-002"


class MultimodalBoundaryTests(unittest.TestCase):
    def setUp(self):
        from medassistmultimodal.demo.fixtures import build_demo_cases
        self.case = build_demo_cases()[0]
        self.event = self.case.events[0]

    def test_very_large_confidence_rejected_as_validation_error(self):
        for value in (10 ** 1000, -(10 ** 1000)):
            with self.subTest(sign=value > 0), self.assertRaises(ValueError):
                replace(self.event, confidence=value)

    def test_adjacent_float_boundaries(self):
        import math
        for value in (math.nextafter(0.0, -1.0), math.nextafter(1.0, 2.0)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(self.event, confidence=value)
        for value in (math.nextafter(0.0, 1.0), math.nextafter(1.0, 0.0)):
            self.assertEqual(replace(self.event, confidence=value).confidence, value)

    def test_canonical_patient_id_rejects_unicode_digits_and_newlines(self):
        for value in ("PAT-１２３", "PAT-001\n", "PAT-001x", "PAT-0000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(self.case.session.subject, patient_id=value)
        for value in ("PAT-000", "PAT-999"):
            self.assertEqual(replace(self.case.session.subject, patient_id=value).patient_id, value)

    def test_dataset_identity_includes_participant_and_version(self):
        subject = SubjectIdentity(kind=SubjectKind.DATASET_PARTICIPANT,
                                  dataset_id="illustrative:v1", participant_ref="opaque-A")
        session = replace(self.case.session, subject=subject)
        event = replace(self.event, subject_kind=subject.kind, patient_id=None,
                        dataset_id=subject.dataset_id, participant_ref=subject.participant_ref,
                        source_kind=SourceKind.DATASET)
        event.validate_for_session(session)
        for other in (replace(subject, participant_ref="opaque-B"),
                      replace(subject, dataset_id="illustrative:v2")):
            with self.subTest(other=other), self.assertRaises(ValueError):
                event.validate_for_session(replace(session, subject=other))

    def test_dataset_references_reject_invalid_types_and_whitespace(self):
        subject = SubjectIdentity(kind=SubjectKind.DATASET_PARTICIPANT,
                                  dataset_id="illustrative:v1", participant_ref="opaque-A")
        for field in ("dataset_id", "participant_ref"):
            for value in (None, "", "\t", " padded ", 123, True):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(subject, **{field: value})

    def test_timezone_conversion_preserves_instant_across_midnight(self):
        local = datetime(2026, 10, 24, 23, 30, tzinfo=timezone(timedelta(hours=-3)))
        expected = datetime(2026, 10, 25, 2, 30, tzinfo=timezone.utc)
        self.assertEqual(replace(self.event, timestamp=local).timestamp, expected)
        self.assertEqual(replace(self.case.session, started_at=local).started_at, expected)

    def test_mock_processing_preserves_dataset_identity(self):
        subject = SubjectIdentity(kind=SubjectKind.DATASET_PARTICIPANT,
                                  dataset_id="illustrative:v1", participant_ref="opaque-A")
        event = replace(self.event, subject_kind=subject.kind, patient_id=None,
                        dataset_id=subject.dataset_id, participant_ref=subject.participant_ref,
                        source_kind=SourceKind.DATASET)
        self.assertTrue(event.is_mock)
        self.assertEqual(event.subject, subject)
        event.validate_for_session(replace(self.case.session, subject=subject))
