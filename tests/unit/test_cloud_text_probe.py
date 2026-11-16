import importlib.util
import json
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[2]/'scripts/compare_cloud_text.py'
spec = importlib.util.spec_from_file_location('cloud_text_probe',path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def response(quote='dor'):
    return {'model':'gpt-oss:120b-cloud','done':True,'done_reason':'stop',
            'message':{'content':json.dumps({'sentiment':'neutral',
                'sentiment_evidence':[{'quote':quote}], 'key_phrases':[{'quote':quote}]})}}


def test_valid_cloud_provenance_and_literal_offsets():
    result=module.validate_response(response(),'Não senti dor.')
    assert result['source']=='ollama_cloud' and result['model']=='gpt-oss:120b-cloud'
    assert result['evidence'][0]['start']==10 and result['input_sha256']


@pytest.mark.parametrize('text,quote',[('dor e dor','dor'),('aaa','aa'),('dor','Dor'),('dor','calor')])
def test_cloud_citations_not_repaired(text,quote):
    with pytest.raises(ValueError):module.validate_response(response(quote),text)


@pytest.mark.parametrize('fault',['model','length','extra','duplicate','schema'])
def test_cloud_strict_validation(fault):
    r=response()
    if fault=='model':r['model']='other'
    elif fault=='length':r['done_reason']='length'
    elif fault=='extra':
        d=json.loads(r['message']['content']);d['diagnosis']='x';r['message']['content']=json.dumps(d)
    elif fault=='duplicate':r['message']['content']='{"sentiment":"neutral","sentiment":"unknown"}'
    elif fault=='schema':r['message']['content']='```json\n{}\n```'
    with pytest.raises(ValueError):module.validate_response(r,'dor')
