"""Aquisição explicitamente autorizada em 31/10/2026; sem extração em massa."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile
import struct
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SIZE = 8433934055
ARCHIVE_MD5 = 'f21dc596f4ef84e21060a43a65c2f30b'
MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task'
RANGE_URL = 'https://zenodo.org/api/records/23018128/files/videos.zip/content'


class RemoteArchive(io.BufferedIOBase):
    """ZIP seekable via HTTP Range validado; somente diretório e membro selecionado."""
    def __init__(self): self.position=0; self.received=0
    def seekable(self):return True
    def readable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        position=offset if whence==0 else ((self.position if whence==1 else ARCHIVE_SIZE)+offset)
        if not 0<=position<=ARCHIVE_SIZE:raise ValueError('Seek inválido')
        self.position=position;return position
    def read(self,size=-1):
        if size<0:size=ARCHIVE_SIZE-self.position
        size=min(size,ARCHIVE_SIZE-self.position)
        if not size:return b''
        if size>1024**3:raise ValueError('Range excessivo')
        start=self.position;end=start+size-1
        req=urllib.request.Request(f'{RANGE_URL}?range={start}-{end}',headers={'Range':f'bytes={start}-{end}'})
        with urllib.request.urlopen(req,timeout=60) as response:
            if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{ARCHIVE_SIZE}':
                raise ValueError('Servidor não respeitou Range; não baixar integral silenciosamente')
            content=response.read(size+1)
        if len(content)!=size:raise ValueError('Range incompleto')
        self.position+=size;self.received+=size
        return content


def hashes(path):
    md5=hashlib.md5(); sha=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024**2),b''):
            md5.update(chunk);sha.update(chunk)
    return md5.hexdigest(),sha.hexdigest()


def download(url, target, maximum):
    if target.exists(): return
    partial=target.with_suffix(target.suffix+'.partial')
    if partial.exists(): raise ValueError('Download parcial anterior exige inspeção; sem sobrescrever')
    if shutil.disk_usage(ROOT).free < maximum + 3*1024**3: raise ValueError('Espaço insuficiente')
    request=urllib.request.Request(url,headers={'User-Agent':'MedAssistMultimodal academic acquisition'})
    count=0
    with urllib.request.urlopen(request,timeout=60) as response, partial.open('xb') as stream:
        while chunk:=response.read(8*1024**2):
            count+=len(chunk)
            if count>maximum: raise ValueError('Download excedeu limite')
            stream.write(chunk)
            if count//(512*1024**2)!=(count-len(chunk))//(512*1024**2): print('Downloaded MiB',count//1024**2,flush=True)
    partial.rename(target)


def main():
    raw=ROOT/'data/raw/rehab26/videos/v1';raw.mkdir(parents=True,exist_ok=True)
    # HEAD não confirmou Range; GET real confirmou 206 e Content-Range em 31/10.
    # Parcial integral anterior é preservado, sem reutilização nem exclusão.
    remote=RemoteArchive()
    plan=json.loads((ROOT/'data/manifests/rehab26_ex1_evaluation_plan_v1.json').read_text())
    mapping_path=ROOT/plan['local_mapping_path']
    if hashes(mapping_path)[1]!=plan['local_mapping_sha256']: raise ValueError('Mapeamento divergente')
    mapping=json.loads(mapping_path.read_text())
    ref=sorted(p['participant_ref'] for p in plan['participants'] if p['group']=='development')[0]
    source=next(p['source_person'] for p in mapping['participants'] if p['participant_ref']==ref)
    destination=raw/f'{ref}_ex1_cam1.mp4'
    with zipfile.ZipFile(remote) as zipped:
        matches=[m for m in zipped.infolist() if Path(m.filename).name==f'ex1_{source}_cam1.mp4']
        if len(matches)!=1: raise ValueError('Membro selecionado ausente/ambíguo')
        member=matches[0]
        if member.file_size>1024**3: raise ValueError('Vídeo excede limite de 1 GiB')
        if not destination.exists():
            partial=destination.with_suffix('.mp4.partial')
            if member.compress_type==zipfile.ZIP_STORED:
                remote.seek(member.header_offset)
                header=remote.read(30)
                if header[:4]!=b'PK\x03\x04':raise ValueError('Cabeçalho ZIP inválido')
                name_length,extra_length=struct.unpack_from('<HH',header,26)
                offset=member.header_offset+30+name_length+extra_length
                prefix=partial.stat().st_size if partial.exists() else 0
                if prefix>member.file_size:raise ValueError('Parcial maior que membro')
                starts=list(range(prefix,member.file_size,8*1024**2))
                def fetch(start):
                    part=RemoteArchive();part.seek(offset+start)
                    data=part.read(min(8*1024**2,member.file_size-start))
                    return data
                with ThreadPoolExecutor(max_workers=8) as pool,partial.open('ab') as dst:
                    for data in pool.map(fetch,starts):
                        dst.write(data);dst.flush()
                        remote.received+=len(data)
                        print('Selected MP4 MiB',dst.tell()//1024**2,flush=True)
            else:
                with zipped.open(member) as src,partial.open('xb') as dst: shutil.copyfileobj(src,dst,8*1024**2)
            partial.rename(destination)
        if destination.stat().st_size!=member.file_size: raise ValueError('Tamanho MP4 divergente')
        # Leitura até EOF valida CRC ZIP. SHA local é manifesto de aquisição,
        # não equivale a SHA publicado independente para esse membro.
        import zlib
        crc=0
        with destination.open('rb') as stream:
            for chunk in iter(lambda:stream.read(8*1024**2),b''):crc=zlib.crc32(chunk,crc)
        if crc!=member.CRC:raise ValueError('CRC MP4 divergente')
    models=ROOT/'data/raw/models';models.mkdir(parents=True,exist_ok=True)
    model=models/'pose_landmarker_full.task';download(MODEL_URL,model,64*1024**2)
    manifest={'date':'2026-10-31','authorization':'User explicitly approved ZIP, one development recording, OpenCV/MediaPipe and Full model',
        'source':'https://zenodo.org/records/23018128','license':'Academic/non-profit non-commercial research; cite DOI 10.48550/arXiv.2609.35726; do not redistribute media',
        'archive':{'url':RANGE_URL,'published_size':ARCHIVE_SIZE,'published_md5':ARCHIVE_MD5,
                   'full_archive_hash_verified':False,'acquisition':'HTTP Range 206, selected member CRC verified',
                   'range_bytes_received':remote.received,'unused_partial_preserved':True},
        'video':{'path':destination.relative_to(ROOT).as_posix(),'participant_ref':ref,'group':'development','exercise':1,'camera':1,
                 'size':destination.stat().st_size,'sha256':hashes(destination)[1],'zip_crc32':f'{member.CRC:08x}'},
        'model':{'path':model.relative_to(ROOT).as_posix(),'url':MODEL_URL,'size':model.stat().st_size,'sha256':hashes(model)[1],
                 'license_reference':'https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker#models'},
        'other_members_extracted':False}
    (ROOT/'data/manifests/day07_rgb_assets.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Assets verified, selected development participant',ref,flush=True)


if __name__=='__main__':main()
