"""Referência por código específico, inclusive adicionais, sem rótulo global."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec=importlib.util.spec_from_file_location('evaluate_ex1',Path(__file__).resolve().parents[2]/'scripts/evaluate_ex1.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def rep(primary,additional=()):
    return SimpleNamespace(error_code=primary,additional_errors=additional,person_orientation=45,repetition_number=1)


def test_additional_code_is_positive():
    r=module.attach({'samples':[]},rep('ERR_ARM_FORWARD',('ERR_BENT_ARM',)),'P-synthetic')
    assert r['reference_positive']=={'bent_elbow_proxy':True,'low_elevation_proxy':False}


def test_other_error_is_not_positive_for_every_rule():
    r=module.attach({'samples':[]},rep('ERR_HEAD_TO_SIDE'),'P-synthetic')
    assert not any(r['reference_positive'].values())


def test_correct_reference_and_both_codes():
    assert not any(module.attach({'samples':[]},rep(None),'P-synthetic')['reference_positive'].values())
    assert all(module.attach({'samples':[]},rep('ERR_LOW_ABDUCTION',('ERR_BENT_ARM',)),'P-synthetic')['reference_positive'].values())
