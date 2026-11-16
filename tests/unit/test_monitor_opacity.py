from unittest.mock import patch
import customtkinter as ctk
import pytest
from medassistmultimodal.desktop_custom import OpaqueCTk

@pytest.mark.parametrize('method,args,expected',[
    ('attributes',('-alpha',.15),('-alpha',1.0)),
    ('attributes',('-alpha',0),('-alpha',1.0)),
    ('wm_attributes',('-alpha',.15),('-alpha',1.0)),
    ('attributes',('-alpha',),('-alpha',)),
    ('attributes',(),()),
    ('attributes',('-topmost',True),('-topmost',True)),
    ('attributes',('-topmost',False,'-alpha',.15),('-topmost',False,'-alpha',1.0)),
])
def test_only_opacity_setter_is_protected(method,args,expected):
    root=object.__new__(OpaqueCTk)
    with patch.object(ctk.CTk,'attributes',return_value='query-result') as base:
        assert getattr(root,method)(*args)=='query-result'
    base.assert_called_once_with(*expected)

def test_dpi_callback_exception_cannot_leave_window_translucent():
    root=object.__new__(OpaqueCTk);state={'alpha':1.0}
    def native(*args):
        if len(args)==2:state['alpha']=args[1]
        return state['alpha']
    with patch.object(ctk.CTk,'attributes',side_effect=native):
        with pytest.raises(RuntimeError):
            root.attributes('-alpha',.15)
            raise RuntimeError('Simulated DPI redraw failure before restoration')
        assert root.attributes('-alpha')==1.0
