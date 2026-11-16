import hashlib
import json
from unittest.mock import Mock

import pytest

from medassistmultimodal.infrastructure.audio_playback import WindowsAudioPlayer, PlaybackError, playback_source, prepare_listening_audio
from medassistmultimodal.infrastructure.desktop_workspace import CORPUS


def catalog(tmp_path):
    media = tmp_path/'data/audio permitido.mp3'; media.parent.mkdir(); media.write_bytes(b'unit-fixture-not-real-audio')
    item = dict(case_id='A01',human_verified=True,consent_ref='permission',
                actual_audio_path='data/audio permitido.mp3',audio_sha256=hashlib.sha256(media.read_bytes()).hexdigest())
    path=tmp_path/CORPUS; path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(dict(clips=[item])),encoding='utf-8')
    return media,path,item


@pytest.mark.parametrize('failure',[None,'changed','missing','permission','unreviewed','duplicate','traversal'])
def test_playback_only_permitted_unchanged_catalog_media(tmp_path,failure):
    media,path,item=catalog(tmp_path)
    if failure=='changed':media.write_bytes(b'changed')
    if failure=='missing':media.rename(media.with_suffix('.saved'))
    if failure=='permission':item.pop('consent_ref')
    if failure=='unreviewed':item['human_verified']=False
    if failure=='traversal':item['actual_audio_path']='../outside.mp3'
    path.write_text(json.dumps(dict(clips=[item,item] if failure=='duplicate' else [item])),encoding='utf-8')
    if failure:
        with pytest.raises(PlaybackError):playback_source(tmp_path,'A01')
    else:assert playback_source(tmp_path,'A01')==media


class FakeMCI:
    def __init__(self):self.commands=[];self.mode='stopped';self.position=0
    def __call__(self,text):
        self.commands.append(text)
        if text.endswith(' length'):return '5000'
        if text.endswith(' position'):return str(self.position)
        if text.endswith(' mode'):return self.mode
        if text.startswith('play '):self.mode='playing'
        if text.startswith('pause '):self.mode='paused'
        if text.startswith('stop '):self.mode='stopped'
        if text.startswith('seek '):self.position=0
        return ''


def test_native_commands_lifecycle_and_end_replay(tmp_path):
    media,_,_=catalog(tmp_path); send=FakeMCI();player=WindowsAudioPlayer(send)
    assert not send.commands
    player.open(media);assert player.duration_ms==5000
    assert f'"{media}"' in send.commands[0]
    player.play();assert player.status()[1]=='playing'
    send.position=1200;player.pause();assert player.status()==(1200,'paused')
    player.play();assert player.status()==(1200,'playing')
    send.position=5000;send.mode='stopped';player.play();assert player.status()[0]==0
    player.stop();assert player.status()==(0,'stopped')
    player.close();player.close();assert player.status()==(0,'closed')
    assert len([c for c in send.commands if c.startswith('close ')])==1


def test_failed_open_closes_device_and_reports_sanitized_error(tmp_path):
    media,_,_=catalog(tmp_path);commands=[]
    def send(text):
        commands.append(text)
        if text.endswith(' length'):return 'invalid'
        return ''
    player=WindowsAudioPlayer(send)
    with pytest.raises(PlaybackError,match='Não foi possível abrir'):player.open(media)
    assert not player.opened and commands[-1].startswith('close ')


def test_missing_media_never_opens_device(tmp_path):
    send=Mock();player=WindowsAudioPlayer(send)
    with pytest.raises(PlaybackError):player.open(tmp_path/'missing.mp3')
    send.assert_not_called()


def test_pilot_source_is_pinned_and_media_hash_checked(tmp_path,monkeypatch):
    media,_,_=catalog(tmp_path)
    origin=Mock(return_value=dict(audio_ref=media.relative_to(tmp_path).as_posix(),sha256=hashlib.sha256(media.read_bytes()).hexdigest()))
    monkeypatch.setattr('medassistmultimodal.infrastructure.audio_playback.acoustic_source',origin)
    assert playback_source(tmp_path,'AP01',pilot=True)==media
    origin.assert_called_with(tmp_path,'AP01')
    media.write_bytes(b'changed')
    with pytest.raises(PlaybackError):playback_source(tmp_path,'AP01',pilot=True)


def test_listening_pcm_is_temporary_mono_and_original_preserved(tmp_path):
    import wave
    source=tmp_path/'stereo.wav'
    with wave.open(str(source),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(44100)
        f.writeframes(b'\x01\x00\x02\x00'*4410)
    original=source.read_bytes();prepared=prepare_listening_audio(source)
    with wave.open(str(prepared.path),'rb') as f:
        assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,44100)
        assert f.getnframes()==4410
    path=prepared.path;prepared.close()
    assert not path.exists() and source.read_bytes()==original


def test_undecodable_listening_preserves_original(tmp_path):
    media,_,_=catalog(tmp_path);before=media.read_bytes()
    with pytest.raises(PlaybackError,match='preparar'):prepare_listening_audio(media)
    assert media.read_bytes()==before
