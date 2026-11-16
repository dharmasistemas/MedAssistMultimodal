"""Fixtures inventadas: nenhum nome/arquivo real é necessário à suíte."""
import csv
from dataclasses import FrozenInstanceError
import io
from pathlib import Path
import tempfile
import unittest

from medassistmultimodal.infrastructure.rehab26_metadata import (
    SEGMENT_COLUMNS, ERROR_COLUMNS, MetadataValidationError,
    load_metadata, parse_errors, parse_segmentation, parse_joints,
)


def csv_text(columns,rows):
    out=io.StringIO(newline='')
    writer=csv.writer(out,delimiter=';',lineterminator='\n')
    writer.writerow(columns);writer.writerows(rows)
    return out.getvalue()


ERROR_TEXT=csv_text(ERROR_COLUMNS,[(1,'Arm abduction','ERR_A','Example A'),
                                  (1,'Arm abduction','ERR_B','Example B'),
                                  (6,'Squat','ERR_C','Example C')])
BASE=['ex1_person_example','1','right','person_example','1','0','10','0','1','','']
JOINT_TEXT=''.join(f'{i}: joint_{i}\n' for i in range(33))


class Rehab26MetadataTests(unittest.TestCase):
    def setUp(self):self.errors=parse_errors(ERROR_TEXT)

    def parse(self,rows):return parse_segmentation(csv_text(SEGMENT_COLUMNS,rows),self.errors)

    def test_valid_correct_incorrect_and_internal_error_list(self):
        incorrect=BASE.copy();incorrect[4]='2';incorrect[5:7]=['11','20'];incorrect[8:]=['5','ERR_A','ERR_B']
        rows=self.parse([BASE,incorrect])
        self.assertIsNone(rows[0].error_code)
        self.assertEqual(rows[1].additional_errors,('ERR_B',))
        self.assertEqual(rows[0].frame_count,11)
        with self.assertRaises(FrozenInstanceError):rows[0].first_frame=5

    def test_single_frame_and_empty_squat_subtype(self):
        row=BASE.copy();row[0]='ex6_person_example';row[1]='6';row[2]='';row[6]='0'
        value=self.parse([row])[0]
        self.assertEqual(value.frame_count,1)
        self.assertIsNone(value.exercise_subtype)

    def test_number_can_restart_for_different_orientation(self):
        other=BASE.copy();other[5:8]=['20','30','45']
        self.assertEqual(len(self.parse([BASE,other])),2)
        with self.assertRaises(MetadataValidationError):self.parse([BASE,BASE])

    def test_headers_width_empty_and_malformed_csv(self):
        cases=['', ';'.join(SEGMENT_COLUMNS)+'\n',
               csv_text(SEGMENT_COLUMNS[::-1],[BASE]),
               csv_text(SEGMENT_COLUMNS,[BASE[:-1]]),csv_text(SEGMENT_COLUMNS,[BASE+['extra']]),
               ';'.join(SEGMENT_COLUMNS)+'\n"unterminated']
        for text in cases:
            with self.subTest(case=cases.index(text)),self.assertRaises(MetadataValidationError):
                parse_segmentation(text,self.errors)

    def test_numeric_domains_and_reference_fields(self):
        for index,value in [(1,'2'),(4,'0'),(4,'1.5'),(5,'-1'),(6,'bad'),(7,'15'),(8,'2'),
                            (2,'left'),(3,''),(0,'ex7_person_example')]:
            row=BASE.copy();row[index]=value
            with self.subTest(index=index,value=value),self.assertRaises(MetadataValidationError):self.parse([row])

    def test_reversed_and_overlapping_intervals(self):
        row=BASE.copy();row[5:7]=['20','10']
        with self.assertRaises(MetadataValidationError):self.parse([row])
        other=BASE.copy();other[4]='2';other[5:7]=['10','20']
        with self.assertRaises(MetadataValidationError):self.parse([BASE,other])

    def test_error_codes_and_label_consistency(self):
        for score,primary,additional in [('1','ERR_A',''),('5','',''),('5','ERR_C',''),
                                          ('5','ERR_A','ERR_UNKNOWN'),('5','ERR_A','ERR_B,ERR_B'),
                                          ('5','ERR_A','ERR_B,')]:
            row=BASE.copy();row[8:]=[score,primary,additional]
            with self.subTest(score=score,primary=primary,additional=additional),self.assertRaises(MetadataValidationError):self.parse([row])

    def test_error_definitions_duplicate_or_incompatible(self):
        for rows in [[(1,'Wrong name','ERR_A','Example')],
                     [(1,'Arm abduction','ERR_A','Example')]*2,
                     [(1,'Arm abduction','bad','Example')],
                     [(1,'Arm abduction','ERR_A','')]]:
            with self.subTest(rows=rows),self.assertRaises(MetadataValidationError):
                parse_errors(csv_text(ERROR_COLUMNS,rows))
        definitions=parse_errors(csv_text(ERROR_COLUMNS,[(1,'Arm abduction','ERR_A','One'),
                                                       (7,'Shoulder extension','ERR_A','Two')]))
        self.assertEqual(len(definitions),2)

    def test_joint_indices_count_and_unique_names(self):
        self.assertEqual(len(parse_joints(JOINT_TEXT)),33)
        for text in (JOINT_TEXT.replace('0:','1:',1),JOINT_TEXT.rsplit('32:',1)[0],
                     JOINT_TEXT.replace('joint_32','joint_31'),JOINT_TEXT+'33: extra\n'):
            with self.subTest(length=len(text)),self.assertRaises(MetadataValidationError):parse_joints(text)

    def test_loader_success_missing_empty_and_invalid_encoding(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            content={'Segmentation.csv':csv_text(SEGMENT_COLUMNS,[BASE]),'Error_types.csv':ERROR_TEXT,
                     'joint_names.txt':JOINT_TEXT,'Segmentation.txt':'Invented semantics for fixture'}
            for name,text in content.items():(root/name).write_text(text,encoding='utf-8')
            value=load_metadata(root)
            self.assertEqual(len(value.repetitions),1)
            (root/'Segmentation.txt').write_text('',encoding='utf-8')
            with self.assertRaises(MetadataValidationError):load_metadata(root)
            (root/'Segmentation.txt').write_bytes(b'\xff')
            with self.assertRaises(MetadataValidationError):load_metadata(root)
            (root/'Segmentation.txt').unlink()
            with self.assertRaises(MetadataValidationError):load_metadata(root)

    def test_private_and_traversal_paths_rejected_before_io(self):
        for path in ('_backup/metadata','.git/metadata','somewhere/../metadata'):
            with self.subTest(path=path),self.assertRaises(MetadataValidationError):load_metadata(Path(path))

    def test_messages_and_repr_do_not_expose_source_names(self):
        row=BASE.copy();row[7]='15'
        with self.assertRaises(MetadataValidationError) as caught:self.parse([row])
        self.assertNotIn('person_example',str(caught.exception))
        self.assertNotIn('person_example',repr(self.parse([BASE])[0]))
