"""Image-bearing review helper shared by the runtime and standalone operator CLI."""
import json
from dnhacksbio import llm


async def inspect(wb,capture_id,question,model=None):
    receipt=next((e['payload'] for e in wb.history() if e['kind']=='scene.capture' and e['payload']['image_hash']==capture_id),None)
    if receipt is None: raise FileNotFoundError('Capture outside experiment')
    raw=wb.j.read_blob(capture_id)
    usage={}
    kwargs={'model':model} if model else {}
    observation=await llm.acomplete('Inspect these actual scene pixels. '+str(question)[:4000]
        +'\nScene metadata: '+json.dumps(receipt),images=[raw],tools_disabled=True,max_turns=1,capture=usage,**kwargs)
    wb.event('scene.vision',{'capture_id':capture_id,'observation':observation,
                          'model':model or 'configured default'},'agent')
    return observation,usage
