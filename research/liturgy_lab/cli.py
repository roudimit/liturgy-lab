import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(path):
    return json.loads(Path(path).read_text())

def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2))

def assemble(paths, output):
    runs = []
    for path in paths:
        r = load(path)
        r.setdefault('id', Path(path).stem)
        r.setdefault('label', Path(path).stem.replace('-', ' ').title())
        runs.append(r)
    session = {'source': load(ROOT/'data/source.json'), 'reference': load(ROOT/'data/reference.json'),
               'runs': runs, 'default_run': runs[0]['id'] if runs else None}
    save(output, session)
    return session

def main():
    parser=argparse.ArgumentParser(description='Local ASR / LLM liturgy experiment')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('reference',help='Parse downloaded bilingual GOARCH HTML')
    p.add_argument('html');p.add_argument('--output',default=str(ROOT/'data/reference.json'))
    p=sub.add_parser('asr',help='Run MLX Whisper locally')
    p.add_argument('audio');p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float)
    p.add_argument('--model',default='turbo');p.add_argument('--language',default='auto',choices=['auto','continuous','el','en'])
    p.add_argument('--chunk-seconds',type=float,default=30);p.add_argument('--output',required=True)
    p=sub.add_parser('align',help='Conservative lexical baseline')
    p.add_argument('transcript');p.add_argument('--reference',default=str(ROOT/'data/reference.json'));p.add_argument('--output',required=True)
    p=sub.add_parser('llm',help='Run local Qwen candidate matching')
    p.add_argument('aligned');p.add_argument('--reference',default=str(ROOT/'data/reference.json'));p.add_argument('--output',required=True)
    p.add_argument('--limit',type=int);p.add_argument('--model',default='mlx-community/Qwen3-4B-Instruct-2507-4bit')
    p=sub.add_parser('assemble',help='Build UI dataset from real experiment outputs')
    p.add_argument('runs',nargs='+');p.add_argument('--output',default=str(ROOT/'data/session.json'))
    p=sub.add_parser('evaluate',help='Metrics on human reviews or independent key-moment labels')
    p.add_argument('--session',default=str(ROOT/'data/session.json'));p.add_argument('--reviews',default=str(ROOT/'data/reviews.json'))
    p.add_argument('--moments');p.add_argument('--run');p.add_argument('--output')
    p=sub.add_parser('serve',help='Start local follow-along UI');p.add_argument('--port',type=int,default=8765)
    a=parser.parse_args()
    if a.command=='reference':
        from .reference import save_reference
        save_reference(a.html,a.output)
    elif a.command=='asr':
        from .asr import transcribe
        transcribe(a.audio,a.start,a.duration,a.model,a.language,a.chunk_seconds,a.output)
    elif a.command=='align':
        from .align import align_segments
        r=load(a.transcript);r['segments']=align_segments(r['segments'],load(a.reference));save(a.output,r)
    elif a.command=='llm':
        from .asr import WORK  # configure workspace model cache, no ML import
        from .llm import run_llm_alignment
        r=load(a.aligned);llm=run_llm_alignment(r['segments'],load(a.reference),model=a.model,limit=a.limit)
        r['segments']=llm['segments'];r['llm_metrics']=llm['metrics'];r['llm_batches']=llm['batches'];r['llm_model']=llm['model'];save(a.output,r)
    elif a.command=='assemble':
        assemble(a.runs,a.output)
    elif a.command=='evaluate':
        from .evaluate import evaluate_reviews,evaluate_moments
        session=load(a.session)
        if a.moments:
            run=next(r for r in session['runs'] if r['id']==(a.run or session['default_run']))
            result=evaluate_moments(run['segments'],load(a.moments))
        else:
            result=evaluate_reviews(session,load(a.reviews) if Path(a.reviews).exists() else [])
        if a.output:save(a.output,result)
        print(json.dumps(result,indent=2))
    elif a.command=='serve':
        import uvicorn
        uvicorn.run('liturgy_lab.server:app',host='127.0.0.1',port=a.port)

if __name__=='__main__':main()
