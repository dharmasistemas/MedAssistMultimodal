import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from medassistmultimodal.application.text_analysis_v3_prompt_v2 import SYSTEM_PROMPT_V3

spec=importlib.util.spec_from_file_location('probe_qwen',Path(__file__).resolve().parents[2]/'scripts/probe_qwen_prompt_v2.py')
# dataclass needs module identity registered when annotations are resolved.
import sys
probe=importlib.util.module_from_spec(spec);sys.modules[spec.name]=probe;spec.loader.exec_module(probe)


def test_same_prompt_and_automatic_gpu_selection_without_cloud_or_thinking():
    record={}
    def opener(request,timeout):
        record.update(json.loads(request.data))
        return io.BytesIO(json.dumps(dict(model='qwen2.5:7b-instruct',done=True,done_reason='stop',
            message=dict(content='{}'))).encode())
    provider=probe.ProbeProvider(allow_requests=True,opener=opener)
    assert provider.generate(system_prompt=SYSTEM_PROMPT_V3,text='Não senti dor.')=='{}'
    assert record['messages'][0]['content']==SYSTEM_PROMPT_V3
    assert record['options']==dict(temperature=0,num_predict=1536,num_ctx=4096)
    assert 'think' not in record and 'num_gpu' not in record['options']


def test_preparation_and_invalid_input_never_request():
    opener=Mock();provider=probe.ProbeProvider(opener=opener)
    with pytest.raises(ValueError):provider.generate(system_prompt=SYSTEM_PROMPT_V3,text='dor')
    provider.allow_requests=True
    with pytest.raises(ValueError):provider.generate(system_prompt=SYSTEM_PROMPT_V3,text='x'*4001)
    with pytest.raises(ValueError):provider.generate(system_prompt='changed',text='dor')
    opener.assert_not_called()
