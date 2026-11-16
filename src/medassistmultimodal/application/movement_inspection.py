"""Inspeção temporal descritiva; não altera regras nem decide alertas."""
from collections import Counter
import math
from medassistmultimodal.domain.rehabilitation import CoordinateSpace,measure_rehabilitation


def inspect_pose(frame, *, min_visibility: float) -> dict:
    points=dict(frame.landmarks)
    available=frame.coordinate_space is CoordinateSpace.WORLD_3D
    filtered=measure_rehabilitation(points,space=CoordinateSpace.WORLD_3D,min_visibility=min_visibility) if available else ()
    raw=measure_rehabilitation(points,space=CoordinateSpace.WORLD_3D,min_visibility=0.) if available else ()
    by_name={m.name:m for m in filtered}
    return {'frame':frame.frame_index,'pose_reason':frame.reason,
        'visibility':{str(i):points[i].visibility if i in points else None for i in (12,14,16,24)},
        'measurements':{name:{'degrees':by_name[name].value_degrees if name in by_name else None,
            'reason':by_name[name].reason if name in by_name else (frame.reason or 'world_3d_required'),
            'diagnostic_unfiltered_degrees':next((m.value_degrees for m in raw if m.name==name),None)}
            for name in ['right_elbow','right_arm_trunk']}}


def summarize_timeline(samples: list[dict], *, first: int,last: int,fps: float,elbow_limit: float) -> dict:
    if type(first) is not int or type(last) is not int or first<0 or last<first:
        raise ValueError('Intervalo inválido')
    if isinstance(fps,bool) or not isinstance(fps,(int,float)) or not math.isfinite(fps) or fps<=0:
        raise ValueError('FPS inválido')
    if isinstance(elbow_limit,bool) or not isinstance(elbow_limit,(int,float)) or not 0<=elbow_limit<=180:
        raise ValueError('Limite angular inválido')
    if [s['frame'] for s in samples]!=list(range(first,last+1)):
        raise ValueError('Timeline deve preservar todos os índices inclusivos')
    expected=last-first+1;output={}
    for name in ['right_elbow','right_arm_trunk']:
        valid=[s for s in samples if s['measurements'][name]['degrees'] is not None]
        reasons=Counter(s['measurements'][name]['reason'] for s in samples if s['measurements'][name]['degrees'] is None)
        peak=max(valid,key=lambda s:s['measurements'][name]['degrees']) if valid else None
        jumps=[abs(b['measurements'][name]['degrees']-a['measurements'][name]['degrees'])
               for a,b in zip(samples,samples[1:]) if a['measurements'][name]['degrees'] is not None and b['measurements'][name]['degrees'] is not None]
        output[name]={'valid_frames':len(valid),'coverage':len(valid)/expected,'invalid_reasons':dict(reasons),
            'min_degrees':min((s['measurements'][name]['degrees'] for s in valid),default=None),
            'max_degrees':peak['measurements'][name]['degrees'] if peak else None,'peak_frame':peak['frame'] if peak else None,
            'max_consecutive_change_degrees':max(jumps,default=None)}
    hits=[s['frame'] for s in samples if s['measurements']['right_elbow']['degrees'] is not None and s['measurements']['right_elbow']['degrees']<elbow_limit]
    runs=[]
    for index in hits:
        if runs and index==runs[-1][1]+1:runs[-1][1]=index
        else:runs.append([index,index])
    output['elbow_below_limit']={'limit_degrees':elbow_limit,'frames':len(hits),
        'fraction_valid':len(hits)/output['right_elbow']['valid_frames'] if output['right_elbow']['valid_frames'] else None,
        'frame_exposure_seconds':len(hits)/fps,'runs':runs,
        'longest_run_frame_exposure_seconds':max((b-a+1 for a,b in runs),default=0)/fps}
    return output
