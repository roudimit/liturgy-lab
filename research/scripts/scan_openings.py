"""Extend the additional recordings around their service transitions, locally."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from liturgy_lab.asr import transcribe
from liturgy_lab.align import detect_liturgy_start
DATA=ROOT/'data'
for vid in ['vkkeLmltf_4','IuZ8WRk-POI']:
    scanfile=DATA/f'turbo-opening-{vid}.json'
    scan=json.loads(scanfile.read_text()) if scanfile.exists() else transcribe(DATA/f'media/{vid}.m4a',4800,600,'turbo','auto',30,scanfile)
    sample=json.loads((DATA/f'turbo-samples-{vid}.json').read_text())
    rows=sorted([*sample['segments'],*scan['segments']],key=lambda s:s['start'])
    for i,row in enumerate(rows):row['id']=i
    elapsed=sample['metrics']['inference_seconds']+scan['metrics']['inference_seconds']
    result={**sample,'segments':rows,'intervals':[{'start':1800,'end':1890},{'start':4800,'end':5490},{'start':7200,'end':7290},{'start':9900,'end':9990}],
            'chunks':sorted([*sample['chunks'],*scan['chunks']],key=lambda c:c['start']),
            'metrics':{'audio_seconds':960,'inference_seconds':elapsed,'real_time_factor':elapsed/960,'speedup':960/elapsed,
                       'peak_memory_gb':max(scan['metrics']['peak_memory_gb'],sample['metrics']['peak_memory_gb']),'includes_model_load':True},
            'notes':['16 minutes total across four windows, not a complete transcription.','Boundary scan at1:20–1:30 was added after observing ambiguous earlier service matches. Exploratory, not held-out evaluation.']}
    result['opening_detection']=detect_liturgy_start(rows)
    (DATA/f'turbo-extended-{vid}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(vid,result['opening_detection'],flush=True)
