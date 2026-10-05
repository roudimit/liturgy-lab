"""Build one completed recording without rewriting historical sessions or titles."""
import argparse
import json
from pathlib import Path
from build_sessions import DATA, compact_run, read, sequence_run, write

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording_id')
    args=parser.parse_args()
    video_id=args.recording_id
    source=read(f'source-{video_id}.json')
    reference=read(f'reference-{video_id}.json')
    name,original=sequence_run(f'turbo-full-{video_id}',reference,video_id)
    run=compact_run(name,original,'Whisper Turbo · full recording',reference,source['duration'])
    assert run['complete'], 'Full recording is not complete'
    accepted=[s for s in run['segments'] if (s.get('match') or {}).get('status')=='matched']
    source.update(preview_start=accepted[0]['start'] if accepted else 0,reference_url=reference['source_url'],reference_date=reference['date'],reference_status=reference['selection']['status'],caveat=reference['selection']['caveat'],experiment_note='Full recording transcribed. Matins and Liturgy are both in the reference. Locations are sequence-supported predictions, not independently verified timing. Raw ASR is displayed separately from canonical service text.',sample_windows=run['intervals'])
    session_name=f'session-{video_id}.json'
    write(session_name,{'source':source,'reference':reference,'references':{reference['reference_id']:reference},'runs':[run],'default_run':run['id']})
    records=read('recordings.json')
    record={'id':video_id,'title':source['title'],'session_file':session_name,'media_file':f'{video_id}.mp4'}
    records=[r for r in records if r['id']!=video_id]+[record]
    # Keep the two Dormition examples first, with the newer recording selected initially.
    records.sort(key=lambda r:{'ZUMoL5VwJzw':0,'n674zECLjTI':1}.get(r['id'],2))
    write('recordings.json',records)
    print(f'Added {video_id}: {len(run["segments"])} segments, {len(accepted)} associated segments')

if __name__=='__main__': main()
