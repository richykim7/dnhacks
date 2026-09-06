"""Lossless float64 chunks of exported coordinates, separate from display geometry."""
from __future__ import annotations
import struct
from .protocol import canonical,digest


def encode_frame(frame: dict) -> tuple[dict,bytes]:
    """No downsampling; retains every exported point and persistent entity identity."""
    coordinates=[];poles=[];filaments=[]
    for pole in frame['poles']:
        poles.append({'id':pole['id'],'offset':len(coordinates)//3})
        coordinates.extend(pole['position'])
    for fiber in frame['filaments']:
        offset=len(coordinates)//3
        for point in fiber['points']:coordinates.extend(point)
        filaments.append({'id':fiber['id'],'pole':fiber['pole'],'offset':offset,'count':len(fiber['points'])})
    raw=struct.pack('<'+'d'*len(coordinates),*coordinates)
    index={'schema':'spindle_frame_chunk.v1','time_s':frame['time'],'dtype':'<f8','shape':[len(coordinates)//3,3],
           'sha256':digest(raw),'byte_length':len(raw),'poles':poles,'filaments':filaments}
    if 'cortical_motors' in frame:index['cortical_motors']=frame['cortical_motors']
    return index,raw


def decode_frame(index: dict, raw: bytes) -> dict:
    if (index.get('schema')!='spindle_frame_chunk.v1' or index.get('dtype')!='<f8'
        or index.get('sha256')!=digest(raw) or index.get('byte_length')!=len(raw)
        or not isinstance(index.get('shape'),list) or len(index['shape'])!=2
        or type(index['shape'][0]) is not int or index['shape'][0]<0 or index['shape'][1]!=3
        or index['shape'][0]*24!=len(raw)):
        raise ValueError('Corrupt coordinate chunk or invalid dimensions')
    coordinates=struct.unpack('<'+'d'*(len(raw)//8),raw)
    def point(offset):
        if type(offset) is not int or not 0<=offset<index['shape'][0]:raise ValueError('Chunk offset outside bounds')
        return list(coordinates[offset*3:offset*3+3])
    poles=[{'id':p['id'],'position':point(p['offset'])} for p in index['poles']]
    filaments=[]
    for f in index['filaments']:
        if type(f['count']) is not int or f['count']<2 or f['count']>index['shape'][0]:raise ValueError('Invalid filament count')
        filaments.append({'id':f['id'],'pole':f['pole'],'points':[point(f['offset']+i) for i in range(f['count'])]})
    result={'time':index['time_s'],'poles':poles,'filaments':filaments}
    if 'cortical_motors' in index:result['cortical_motors']=index['cortical_motors']
    return result


def export_chunks(directory, runs):
    directory.mkdir();index=[]
    for r,run in enumerate(runs):
        chunks=[]
        for i,frame in enumerate(run['frames']):
            metadata,raw=encode_frame(frame);name=f'{r}-{i}.f64'
            (directory/name).write_bytes(raw);chunks.append({**metadata,'path':name})
        # Lifetimes are sampled presence intervals, not invented exact solver birth times.
        lifetimes={}
        for i,frame in enumerate(run['frames']):
            for fiber in frame['filaments']:
                lifetimes.setdefault(fiber['id'],[]).append(i)
        index.append({'seed':run['seed'],'condition':run['condition'],'frames':chunks,
                      'filament_sampled_presence':lifetimes})
    (directory/'index.json').write_bytes(canonical({'schema':'spindle_chunks.v1','runs':index,
        'precision':'Lossless relative to native exported values; raw solver trajectory is archived separately.'}))
