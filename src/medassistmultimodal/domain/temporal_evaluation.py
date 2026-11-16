"""Pareamento temporal um-para-um e métricas; sem acesso à pose ou rótulo clínico."""
from dataclasses import dataclass
from collections.abc import Iterable
import statistics


@dataclass(frozen=True, slots=True)
class FrameInterval:
    interval_id: str
    first_frame: int
    last_frame: int

    def __post_init__(self):
        if not isinstance(self.interval_id,str) or not self.interval_id or self.interval_id!=self.interval_id.strip():raise ValueError('ID inválido')
        if type(self.first_frame) is not int or type(self.last_frame) is not int or not 0<=self.first_frame<=self.last_frame:
            raise ValueError('Intervalo inclusivo inválido')


def temporal_iou(a: FrameInterval,b: FrameInterval) -> float:
    intersection=max(0,min(a.last_frame,b.last_frame)-max(a.first_frame,b.first_frame)+1)
    union=(a.last_frame-a.first_frame+1)+(b.last_frame-b.first_frame+1)-intersection
    return intersection/union


def evaluate_intervals(references: Iterable[FrameInterval],predictions: Iterable[FrameInterval], *,
                       min_iou: float=.5,fps: float=30.,boundary_tolerance_frames: int=15) -> dict:
    refs=tuple(references);preds=tuple(predictions)
    if isinstance(min_iou,bool) or not isinstance(min_iou,(int,float)) or not 0<min_iou<=1:raise ValueError('IoU inválida')
    if isinstance(fps,bool) or not isinstance(fps,(int,float)) or fps!=30:raise ValueError('Perfil exige 30 FPS')
    if type(boundary_tolerance_frames) is not int or boundary_tolerance_frames<0:raise ValueError('Tolerância inválida')
    for group in [refs,preds]:
        if any(not isinstance(x,FrameInterval) for x in group):raise ValueError('Intervalos tipados obrigatórios')
        if len({x.interval_id for x in group})!=len(group):raise ValueError('IDs duplicados')
    edges=[]
    for ri,r in enumerate(refs):
        for pi,p in enumerate(preds):
            iou=temporal_iou(r,p)
            if iou>=min_iou:edges.append((ri,pi,iou))
    edges.sort(key=lambda e:(-e[2],abs(preds[e[1]].first_frame-refs[e[0]].first_frame),refs[e[0]].first_frame,preds[e[1]].first_frame))
    used_r=set();used_p=set();matches=[]
    for ri,pi,iou in edges:
        if ri in used_r or pi in used_p:continue
        used_r.add(ri);used_p.add(pi);r=refs[ri];p=preds[pi]
        start=p.first_frame-r.first_frame;end=p.last_frame-r.last_frame
        matches.append({'reference_id':r.interval_id,'prediction_id':p.interval_id,'iou':iou,
            'start_error_frames':start,'end_error_frames':end,'start_error_seconds':start/fps,'end_error_seconds':end/fps,
            'both_boundaries_within_tolerance':abs(start)<=boundary_tolerance_frames and abs(end)<=boundary_tolerance_frames})
    tp=len(matches);fp=len(preds)-tp;fn=len(refs)-tp
    def ratio(n,d):return n/d if d else None
    def errors(name):
        values=[m[name+'_error_frames'] for m in matches];absolute=[abs(x) for x in values]
        return {'mean_signed_frames':statistics.mean(values) if values else None,
            'median_signed_frames':statistics.median(values) if values else None,
            'mean_absolute_frames':statistics.mean(absolute) if values else None,
            'median_absolute_frames':statistics.median(absolute) if values else None,
            'max_absolute_frames':max(absolute,default=None),
            'mean_absolute_seconds':statistics.mean(absolute)/fps if values else None,
            'median_absolute_seconds':statistics.median(absolute)/fps if values else None,
            'max_absolute_seconds':max(absolute)/fps if values else None}
    return {'references':len(refs),'predictions':len(preds),'tp':tp,'fp':fp,'fn':fn,
        'precision':ratio(tp,tp+fp),'recall':ratio(tp,tp+fn),'f1':ratio(2*tp,2*tp+fp+fn),
        'matching_method':'greedy descending IoU, abs start error, reference start, prediction start; stable ties',
        'min_iou':min_iou,'boundary_tolerance_frames':boundary_tolerance_frames,
        'boundary_errors':{'start':errors('start'),'end':errors('end')},'matches':matches,
        'unmatched_reference_ids':[r.interval_id for i,r in enumerate(refs) if i not in used_r],
        'unmatched_prediction_ids':[p.interval_id for i,p in enumerate(preds) if i not in used_p]}
