"""Relatório Ex1 somente desenvolvimento, sem nomes ou chamadas de providers."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from medassistmultimodal.application.ex1_repetitions import Ex1Config, analyze_repetition
from medassistmultimodal.infrastructure.rehab26_landmarks import LandmarkSequence, Representation
from medassistmultimodal.infrastructure.rehab26_metadata import load_metadata

ROOT = Path(__file__).resolve().parents[1]


def main():
    def read(name): return json.loads((ROOT / name).read_text(encoding='utf-8'))
    def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    plan = read('data/manifests/rehab26_ex1_evaluation_plan_v1.json')
    manifest = read('data/manifests/rehab26_landmarks_manifest.json')
    for name, expected in [(plan['local_mapping_path'], plan['local_mapping_sha256']),
                           (manifest['local_index_path'], manifest['local_index_sha256'])]:
        if digest(ROOT / name) != expected: raise ValueError('Índice/mapeamento divergente')
    for name, expected in plan['input_sha256'].items():
        if digest(ROOT / 'data/raw/rehab26/metadata/v1' / name) != expected:
            raise ValueError('Metadado divergente')
    mapping = read(plan['local_mapping_path'])
    people = {p['source_person']: p['participant_ref'] for p in mapping['participants']}
    development = {p['participant_ref'] for p in plan['participants'] if p['group'] == 'development'}
    members = read(manifest['local_index_path'])['files']
    config_path = ROOT / 'configs/ex1_rules_v1.json'
    config = Ex1Config(**json.loads(config_path.read_text(encoding='utf-8')))
    metadata = load_metadata(ROOT / 'data/raw/rehab26/metadata/v1')
    results = []; inputs = []
    for member in members:
        ref = member['participant_ref']
        if ref not in development or member['representation'] != '3d': continue
        expected = next(f['sha256'] for f in manifest['files'] if f['participant_ref'] == ref and f['representation'] == '3d')
        if member['sha256'] != expected: raise ValueError('Hash de membro divergente')
        with LandmarkSequence(ROOT / member['path'], representation=Representation.THREE_D, expected_sha256=expected) as sequence:
            inputs.append({'participant_ref': ref, 'sha256': expected})
            for rep in metadata.repetitions:
                if rep.exercise_id != 1 or people[rep.person] != ref: continue
                result = analyze_repetition(sequence, rep.first_frame, rep.last_frame,
                    evidence_ref=f'rehab26-v1/{ref}/ex1/cam1/3d#{rep.first_frame}-{rep.last_frame}', config=config)
                result.update(participant_ref=ref, orientation=rep.person_orientation,
                              repetition_number=rep.repetition_number)
                # Não exportar todas as coordenadas/amostras no relatório público.
                samples = result.pop('samples')
                local = ROOT / 'data/interim/rehab26/day06'
                local.mkdir(exist_ok=True)
                target = local / f'{ref}_{rep.person_orientation}_{rep.repetition_number}.json'
                target.write_text(json.dumps(samples, allow_nan=False), encoding='utf-8')
                results.append(result)
    counts = {}
    for result in results:
        for rule in result['rules']:
            counts.setdefault(rule['name'], {})
            counts[rule['name']][rule['status']] = counts[rule['name']].get(rule['status'], 0) + 1
    payload = {'date': '2026-10-31', 'group': 'development', 'evaluation_processed': False,
               'config': asdict(config), 'config_sha256': digest(config_path), 'inputs': inputs,
               'repetitions': len(results), 'counts': counts, 'results': results,
               'limitations': ['3D estimado, sem calibração física', 'Sem referência vertical; tronco indisponível',
                               'Elevação não comprova abdução no plano frontal', 'Sem classificação global correto/incorreto',
                               'Sem avaliação de ERR_ARM_FORWARD, ERR_ELEVATED_SHOULDER ou ERR_HEAD_TO_SIDE',
                               'Timecode nominal 30 FPS; sincronização RGB não verificada',
                               'Parâmetros experimentais fixados antes desta execução, sem ajuste por rótulos']}
    target = ROOT / 'reports/REHAB26_EX1_DEVELOPMENT_2026-10-31.json'
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'repetitions': len(results), 'counts': counts, 'evaluation_processed': False}))


if __name__ == '__main__': main()
