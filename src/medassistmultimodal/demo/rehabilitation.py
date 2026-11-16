"""Demonstração de medidas com pose artificial; nenhum provider ou arquivo."""
from dataclasses import asdict, replace
import json

from medassistmultimodal.domain.rehabilitation import Landmark, CoordinateSpace, measure_rehabilitation


def synthetic_pose() -> dict[int,Landmark]:
    return {index:Landmark(point,1.) for index,point in {
        11:(-1.,0.),12:(1.,0.),14:(2.,0.),16:(2.,1.),23:(-1.,2.),24:(1.,2.)}.items()}


def build_demo_results() -> dict:
    pose=synthetic_pose()
    low=dict(pose);low[14]=replace(low[14],visibility=0.2)
    missing=dict(pose);del missing[16]
    return {'project':'MedAssistMultimodal','source':'synthetic:rehabilitation:v1',
            'clinical_validation':False,'visibility_threshold_experimental':0.5,
            'cases':[{'name':name,'measurements':[asdict(value) for value in
                     measure_rehabilitation(points,space=CoordinateSpace.IMAGE_2D,min_visibility=0.5)]}
                     for name,points in [('known_pose',pose),('low_elbow_visibility',low),('missing_wrist',missing)]]}


def main() -> int:
    print(json.dumps(build_demo_results(),ensure_ascii=False,indent=2,allow_nan=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
