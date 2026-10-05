import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from liturgy_lab.asr import transcribe
root=Path(__file__).resolve().parents[2]/'data'
for name,model,language in [('small-auto-pilot','small','auto'),('turbo-continuous-pilot','turbo','continuous')]:
    path=root/f'{name}.json'
    if not path.exists():
        transcribe(root/'media/source-audio.m4a',1807,180,model,language,30,path)
for vid in ['vkkeLmltf_4','IuZ8WRk-POI']:
    path=root/f'turbo-samples-{vid}.json'
    if path.exists():continue
    pieces=[]
    for start in [1800,5400,7200,9900]:
        clip=root/f'turbo-{vid}-{start}.json'
        r=json.loads(clip.read_text()) if clip.exists() else transcribe(root/f'media/{vid}.m4a',start,90,'turbo','auto',30,clip)
        pieces.append(r)
    segments=[]
    for piece in pieces:
        for segment in piece['segments']:
            segment['id']=len(segments)
            segments.append(segment)
    elapsed=sum(r['metrics']['inference_seconds'] for r in pieces)
    result={'model':pieces[0]['model'],'language_mode':'auto','chunk_seconds':30,
            'start':1800,'end':9990,'intervals':[{'start':r['start'],'end':r['end']} for r in pieces],
            'segments':segments,'chunks':sum([r['chunks'] for r in pieces],[]),
            'metrics':{'audio_seconds':360,'inference_seconds':elapsed,'real_time_factor':elapsed/360,'speedup':360/elapsed,
                       'peak_memory_gb':max(r['metrics']['peak_memory_gb'] for r in pieces),'includes_model_load':True},
            'notes':['Four 90-second samples, not a full transcription. Unsampled intervals have no predictions.','Samples are exploratory and not randomly selected or human annotated.']}
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('ASR matrix complete',flush=True)
