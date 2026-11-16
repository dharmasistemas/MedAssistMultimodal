"""Verified selected-session report snapshots; no inference or clinical correlation."""
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
from pathlib import Path
import sqlite3
from uuid import UUID,uuid4

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.register_vitals import encode_json,strict_json
from medassistmultimodal.providers.whisper_local import checked_path
from medassistmultimodal.application.prescription_expectation_text import expectation_lines
from medassistmultimodal.application.register_acoustics import acoustic_lines
from .desktop_text import TextHistoryReader

STATUS={'pending_review':'Pendente de revisão','reviewed':'Revisado','dismissed':'Descartado',
    'completed':'Concluído tecnicamente','degraded':'Parcial','failed':'Falhou','succeeded':'Concluída',
    'disabled':'Desativada','timeout':'Prazo excedido','unavailable':'Indisponível','invalid_response':'Resposta inválida',
    'not_run':'Não executada','unsupported_input':'Fora da capacidade','not_configured':'Não configurada'}
KINDS={'audio':'Áudio','vitals':'Vitais','prescriptions':'Prescrições','video':'Vídeo','acoustics':'Áudio acústico'}


@dataclass(frozen=True,slots=True)
class ReportSnapshot:
    payload: bytes
    @property
    def document(self):return strict_json(self.payload)


def factual_text(document):
    lines=['MedAssistMultimodal — síntese de resultados para revisão',
        f"Relatório: {document['report_id']} | Gerado em UTC: {document['generated_at']}",
        f"Base: {document['database']}",
        'Síntese factual; sem diagnóstico, prescrição ou validação clínica.',
        'Sessões têm tempos e origens próprios. Não há relação causal ou sincronização demonstrada.',
        'Revisado significa conferência declarada, não certificação clínica.',
        f"Sessões selecionadas: {len(document['session_ids'])} | Eventos técnicos: {document['counts']['events']}",
        'Eventos não equivalem à quantidade de alertas clínicos.',
        'Revisão atual: '+', '.join(f'{STATUS.get(k,k)}: {v}' for k,v in sorted(document['counts']['review_status'].items()))]
    for group,title in [('patient_sessions','REGISTROS DO PACIENTE FICTÍCIO'),('dataset_sessions','DATASET INDEPENDENTE — NÃO É O PACIENTE FICTÍCIO')]:
        lines+=['','='*60,title]
        if not document[group]:lines.append('Nenhuma sessão selecionada neste grupo.')
        for detail in document[group]:
            session=detail['session'];events=detail['events']
            if detail.get('registered_at'):lines.append('Registro no aplicativo: '+detail['registered_at'])
            lines+=['',f"Sessão: {session['session_id']} | Horário da sessão/cenário: {session['started_at']}",
                f"Identidade: {session['subject_kind']} | Paciente: {session.get('patient_id') or 'Não se aplica'}"]
            if group=='dataset_sessions':lines.append(f"Dataset: {session.get('dataset_id')} | Participante: {session.get('participant_ref')}")
            for record in detail['documents']:
                d=record['evidence'];llm=d['llm'];asr=d['asr']
                lines += ['ÁUDIO — relato simulado',f"Origem: {d['input']['origin_kind']} | Resultado: {STATUS.get(d['summary']['status'],d['summary']['status'])}",
                    f"ASR: {asr['status']} | Fonte/modelo: {asr['provider']['source']} / {asr['provider']['model']} | Mock: {asr['provider']['is_mock']}",
                    'Transcrição: '+(asr['result']['text'] if asr.get('result') else 'Indisponível; não interpretar como ausência de relato.'),
                    'MENÇÕES DAS REGRAS (contexto preservado)']
                if d['rules']['items'] is None:lines.append('Regras indisponíveis; não equivale a zero ocorrências.')
                elif not d['rules']['items']:lines.append('Nenhuma menção configurada encontrada; não comprova normalidade.')
                for item in d['rules']['items'] or []:lines.append(f"• {item['term']} | {item['context']} | {item['classification']} | {item['sentence']}")
                lines.append('LLM opcional: '+STATUS.get(llm['status'],llm['status']))
                if llm.get('provider'):lines.append(f"Fonte/modelo LLM: {llm['provider']['source']} / {llm['provider']['model']} | Mock: {llm['provider']['is_mock']}")
                if llm.get('result'):
                    result=llm['result'];lines.append('Sentimento textual: '+result['sentiment']+' (não é emoção vocal, urgência ou diagnóstico).')
                    lines += ['• Citação: '+e['quote'] for e in result['sentiment_evidence']]
                    lines += [f"• Termo LLM: {e['term']} | {e['evidence']['quote']}" for e in result['terms']]
                if llm.get('error'):lines.append('Falha LLM registrada: '+llm['error'])
                lines.append('LLM não decide alertas; validade formal não garante completude.')
            for record in detail['vitals']:
                d=record['evidence'];r=d['result'];raw=record['raw_series']
                lines+=['VITAIS SINTÉTICOS',f"Cenário: {d['scenario_id']} | Perfil: {r['profile_version']} | Série bruta: {raw['status']}",
                    'Tempos nominais fictícios; cobertura não é confiança clínica.']
                for coverage in r['coverage']:lines.append(f"• {coverage['channel']}: {coverage['valid_samples']}/{coverage['total_samples']} válidas ({coverage['fraction']:.1%})")
                for o in r['occurrences']:lines.append(f"• {o['rule_id']} | {o['first_timestamp']} a {o['last_timestamp']} | confirmação: {o['confirmed_timestamp']} | valores: {o['values']} {o['unit']} | limiar: {o['threshold']} | término: {o['termination']}")
                if not r['occurrences']:lines.append('Nenhuma ocorrência registrada pelo perfil; ausência não significa normalidade.')
                lines.append(f"Intervalos de qualidade: {len(r['quality_intervals'])}; consulte evidência para motivos/índices.")
            for record in detail['prescriptions']:
                r=record['evidence']['result']
                if 'expectation' in record['evidence']:lines+=expectation_lines(record['evidence'])
                lines+=['PRESCRIÇÕES SINTÉTICAS — comparação, sem recomendação',
                    f"Versão {r['before']['version']} ({r['before']['issued_at']}) → {r['after']['version']} ({r['after']['issued_at']})",
                    f"Incluídos: {r['included_count']} | Removidos: {r['removed_count']} | Modificados: {r['modified_count']}"]
                if not r['changes']:lines.append('Comparação válida sem alterações.')
                for change in r['changes']:
                    lines.append(f"• {change['item_id']} | {change['kind']}")
                    for side in ('before','after'):
                        item=change[side]
                        lines.append(f"  {side}: "+('Item ausente' if item is None else f"{item['product_code']}, {item['dose_value']} {item['dose_unit']}, {item['frequency_per_day']}/dia, {item['duration_days']}dias, {item['route']}"))
                    for field in change['field_changes']:lines.append(f"  {field['field']}: {field['before']} → {field['after']}")
                    if change['unit_change_note']:lines.append('  Mudança de representação de unidade; sem inferir equivalência clínica ou aumento de dose.')
            for record in detail.get('videos',[]):
                d=record['evidence'];s=d['source'];r=d['summary']
                lines+=['VÍDEO RGB EXPERIMENTAL — dataset independente',
                    f"Frames: {s['first_frame']}–{s['last_frame']} | FPS: {s['fps']} | tempo relativo: {s['first_frame']/s['fps']:.3f}–{s['last_frame']/s['fps']:.3f}s",
                    f"Processamento: {d['processed_at']} | Horário de captura desconhecido | Mock: {s['is_mock']}",
                    f"Ciclos candidatos detectados: {r['detected_cycles']} | Cobertura: {r['coverage']} | Intervalos técnicos: {r['quality_intervals']}",
                    'Não é contagem real garantida ou avaliação de execução correta/incorreta. Desempenho NPY não valida este RGB.']
                for c in d['cycles']:lines.append(f"• Ciclo: frames {c['first_frame']}–{c['last_frame']} | confirmação: {c['confirmed_at_frame']} | pico: {c['peak_degrees']}°")
                if 'elbow_analysis' in d:
                    e=d['elbow_analysis']
                    label={'deviation':'Sinal experimental de flexão do cotovelo',
                        'no_deviation':'Sem sinal desse desvio; não comprova exercício correto',
                        'not_analyzable':'Evidência insuficiente para avaliar cotovelo'}[e['status']]
                    lines += [label,
                        f"Regra: {e['profile']} | Frames: {e['first_frame']}–{e['last_frame']} | Cobertura: {e['coverage']:.1%}",
                        f"Fração abaixo de {e['elbow_min_degrees']}°: {e['bent_fraction']} | Limiar: {e['fraction_threshold']} | Frame de evidência: {e['evidence_frame']}",
                        'Intervalo fornecido pelo operador; regra aplicada aos ângulos originais, sem filtro temporal adicional. Requer revisão; sem validação clínica.']
            for record in detail.get('acoustics',[]):lines+=acoustic_lines(record['evidence'])
            lines+=['EVIDÊNCIAS VERIFICADAS']
            for area in ('documents','vitals','prescriptions','videos','acoustics'):
                for record in detail.get(area,[]):lines.append(f"• {record['reference']} | SHA-256: {record['sha256']}")
            lines+=['REVISÃO DOS EVENTOS — estado no instante da síntese']
            for row in events:
                e=row['event'];history=detail['review_histories'][e['event_id']]
                lines.append(f"• {KINDS.get(row['modality'],row['modality'])} | {e['event_id']} | {STATUS.get(e['review_status'],e['review_status'])} | registros de revisão: {len(history)} | {e['evidence_ref']}")
    lines+=['','Limites: dados demonstrativos, fontes independentes, revisão profissional necessária.',
        'Este retrato pode ficar desatualizado após novas revisões. Referências locais não tornam o arquivo um pacote portátil.']
    return '\n'.join(lines)+'\n'


class SummaryService:
    def __init__(self,root,reader=None):self.root=Path(root).absolute();self.reader=reader or TextHistoryReader(self.root)

    def catalog(self,database,patient_id):
        rows=[dict(session_id=r.session_id,subject=patient_id,modalities=', '.join(r.modalities),started_at=r.started_at,registered_at=getattr(r,"registered_at",None)) for r in self.reader.sessions(database,patient_id)]
        rows += [dict(session_id=str(r.session_id),subject='Dataset independente',modalities='Vídeo',started_at=r.started_at.isoformat()) for r in self.reader.dataset_sessions(database)]
        return tuple(rows)

    def _collect(self,database,patient_id,session_ids):
        try:selected=tuple(sorted(str(UUID(s)) for s in session_ids))
        except (ValueError,TypeError,AttributeError) as exc:raise HistoryError('report_selection_invalid') from exc
        if not selected or len(selected)>20 or len(set(selected))!=len(selected):raise HistoryError('report_selection_invalid')
        path=checked_path(database,self.root)
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)) as monitor:
            version=monitor.execute('PRAGMA data_version').fetchone()[0]
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            allowed={r['session_id'] for r in self.catalog(database,patient_id)}
            if not set(selected)<=allowed:raise HistoryError('report_selection_invalid')
            documents=[self.reader.detail(database,UUID(s)).document for s in selected]
            if any(d['unsupported_sources'] or d['integrity']!='verified' for d in documents):raise HistoryError('evidence_unsupported')
            if version!=monitor.execute('PRAGMA data_version').fetchone()[0] or before!=hashlib.sha256(path.read_bytes()).hexdigest():raise HistoryError('report_stale')
        groups=dict(patient_sessions=[],dataset_sessions=[])
        for d in documents:
            subject=d['session']
            if subject['subject_kind']=='synthetic_patient' and subject['patient_id']==patient_id:groups['patient_sessions'].append(d)
            elif subject['subject_kind']=='dataset_participant' and subject['patient_id'] is None:groups['dataset_sessions'].append(d)
            else:raise HistoryError('report_selection_invalid')
        return path,selected,groups

    def build(self,database,patient_id,session_ids):
        path,selected,groups=self._collect(database,patient_id,session_ids)
        events=[r for g in groups.values() for d in g for r in d['events']]
        document=dict(schema_version='selected-session-summary-v1',report_id=str(uuid4()),generated_at=datetime.now(timezone.utc).isoformat(),
            database=path.relative_to(self.root).as_posix(),patient_id=patient_id,session_ids=selected,**groups,
            counts=dict(events=len(events),by_modality=dict(Counter(r['modality'] for r in events)),review_status=dict(Counter(r['event']['review_status'] for r in events))),
            clinical_validation=False,causal_correlation_validated=False,temporal_alignment_validated=False)
        document['text']=factual_text(document)
        return ReportSnapshot(encode_json(document))

    def export(self,snapshot):
        if not isinstance(snapshot,ReportSnapshot):raise ValueError('Typed report snapshot required')
        document=snapshot.document
        if document['schema_version']!='selected-session-summary-v1' or document['text']!=factual_text(document):raise HistoryError('evidence_invalid')
        _,_,groups=self._collect(document['database'],document['patient_id'],document['session_ids'])
        if any(groups[k]!=document[k] for k in groups):raise HistoryError('report_stale')
        report_id=str(UUID(document['report_id']))
        directory=checked_path(f'data/interim/multimodal/reports_v1/{report_id}',self.root)
        json_bytes=encode_json(document);text_bytes=document['text'].encode('utf-8')
        files={'summary.json':json_bytes,'summary.txt':text_bytes}
        manifest=encode_json(dict(schema_version='summary-export-manifest-v1',report_id=report_id,
            sha256={n:hashlib.sha256(b).hexdigest() for n,b in files.items()}))
        if directory.exists():
            try:
                if all((directory/n).read_bytes()==b for n,b in {**files,'manifest.json':manifest}.items()):return directory.relative_to(self.root).as_posix()
            except OSError as exc:raise HistoryError('report_export_conflict') from exc
            raise HistoryError('report_export_conflict')
        directory.mkdir(parents=True,exist_ok=False)
        for name,raw in files.items():
            with (directory/name).open('xb') as stream:stream.write(raw)
        # Last file is the completion marker; partial folders remain for explicit recovery.
        with (directory/'manifest.json').open('xb') as stream:stream.write(manifest)
        return directory.relative_to(self.root).as_posix()
