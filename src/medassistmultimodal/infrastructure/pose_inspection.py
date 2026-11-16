"""Projeção de landmarks de imagem documentados, somente para inspeção visual."""
import math


def normalized_pixel(x: float, y: float, width: int, height: int) -> tuple[int,int] | None:
    if type(width) is not int or type(height) is not int or min(width,height)<=0:
        raise ValueError('Dimensões positivas obrigatórias')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (x,y)):
        return None
    if not 0<=x<=1 or not 0<=y<=1:return None
    return min(round(x*width),width-1),min(round(y*height),height-1)
