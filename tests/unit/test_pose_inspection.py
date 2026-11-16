import pytest
from medassistmultimodal.infrastructure.pose_inspection import normalized_pixel


def test_projection_uses_separate_width_and_height():
    assert normalized_pixel(.5,.25,1080,1920)==(540,480)
    assert normalized_pixel(0,0,1080,1920)==(0,0)
    assert normalized_pixel(1,1,1080,1920)==(1079,1919)


@pytest.mark.parametrize('x,y',[(float('nan'),.5),(.5,float('inf')),(-.01,.5),(1.01,.5),(True,.5)])
def test_unusable_point_not_drawn_at_invented_location(x,y):
    assert normalized_pixel(x,y,1080,1920) is None


def test_invalid_dimensions():
    with pytest.raises(ValueError):normalized_pixel(.5,.5,0,1920)
