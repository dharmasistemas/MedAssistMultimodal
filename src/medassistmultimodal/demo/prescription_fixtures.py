"""Fixed fictional documents and authored expectations, independent of the detector."""
from copy import deepcopy


def base_pair():
    item={'item_id':'RX-001','product_code':'DEMO-A','dose_value':'10','dose_unit':'mg',
          'frequency_per_day':1,'route':'oral','duration_days':7,'instructions':'Exemplo fictício A'}
    before={'schema_version':'synthetic-prescriptions-v1','subject_kind':'synthetic_patient',
        'patient_id':'PAT-001','source_kind':'synthetic','source':'synthetic-prescriptions-fixture-v1',
        'dataset_id':None,'participant_ref':None,'synthetic':True,'complete':True,
        'prescription_set_id':'RXSET-DEMO-001','version':1,
        'issued_at':'2026-11-03T12:00:00+00:00','items':[item]}
    after=deepcopy(before)
    after.update(version=2,issued_at='2026-11-04T12:00:00+00:00')
    return {'before':before,'after':after}


def build_prescription_cases():
    """24 primary cases; P19–P24 have additional rejection subcases in tests."""
    cases={f'P{i:02d}':base_pair() for i in range(1,25)}
    c={'item_id':'RX-002','product_code':'DEMO-B','dose_value':'5','dose_unit':'mL',
       'frequency_per_day':2,'route':'oral','duration_days':3,'instructions':'Exemplo fictício B'}
    cases['P02']['after']['items'].append(deepcopy(c))
    cases['P03']['before']['items'].append(deepcopy(c))
    cases['P04']['after']['items'][0]['dose_value']='15'
    cases['P05']['after']['items'][0]['frequency_per_day']=2
    cases['P06']['after']['items'][0].update(dose_value='15',frequency_per_day=2,duration_days=10)
    for side in ('before','after'):cases['P07'][side]['items'].append(deepcopy(c))
    cases['P07']['after']['items'].reverse()
    cases['P08']['before']['items'][0]['dose_value']='10.00'
    cases['P09']['before']['items']=[]
    cases['P10']['after']['items']=[]
    cases['P11']['before']['items']=[];cases['P11']['after']['items']=[]
    cases['P12']['after']['items'][0]['item_id']='RX-009'
    cases['P13']['after']['items'][0]['product_code']='DEMO-B'
    cases['P14']['before']['items'][0]['dose_value']='1000'
    cases['P14']['after']['items'][0].update(dose_value='1',dose_unit='g')
    cases['P15']['after']['items'][0]['instructions']='Exemplo fictício A revisado'
    cases['P16']['after']['items'][0]['route']='topical'
    cases['P17']['after']=deepcopy(cases['P17']['before'])
    cases['P18']['after']=deepcopy(cases['P18']['before'])
    cases['P18']['after']['items'][0]['dose_value']='15'
    cases['P19']['after']['issued_at']=cases['P19']['before']['issued_at']
    cases['P20']['after']['patient_id']='PAT-002'
    cases['P21']['after']=None
    cases['P22']['after']['items']*=2
    cases['P23']['after']['items'][0]['dose_value']='0'
    cases['P24']['after']['version']=True
    # Each expectation is declared from the approved table, never from comparison output.
    expected={k:[] for k in cases}
    for key,kind,identifier,fields in (
        ('P02','included','RX-002',()),('P03','removed','RX-002',()),
        ('P04','modified','RX-001',('dose_value',)),('P05','modified','RX-001',('frequency_per_day',)),
        ('P06','modified','RX-001',('dose_value','frequency_per_day','duration_days')),
        ('P09','included','RX-001',()),('P10','removed','RX-001',()),
        ('P12','removed','RX-001',()),('P12','included','RX-009',()),
        ('P13','modified','RX-001',('product_code',)),
        ('P14','modified','RX-001',('dose_value','dose_unit')),
        ('P15','modified','RX-001',('instructions',)),('P16','modified','RX-001',('route',))):
        expected[key].append({'kind':kind,'item_id':identifier,'fields':list(fields)})
    return cases,{'changes':{k:v for k,v in expected.items() if int(k[1:])<=17},
                  'rejected':[f'P{i:02d}' for i in range(18,25)]}
