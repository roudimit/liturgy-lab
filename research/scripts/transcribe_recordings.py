"""Transcribe complete recordings in reusable hour blocks, one model at a time."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from liturgy_lab.asr import MODELS, transcribe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recordings', nargs='+', default=['vkkeLmltf_4', 'IuZ8WRk-POI', 'n674zECLjTI'])
    parser.add_argument('--model', default='turbo', choices=sorted(MODELS))
    args = parser.parse_args()
    data = ROOT / 'data'
    for video_id in args.recordings:
        source = json.loads((data / f'source-{video_id}.json').read_text())
        duration = int(source['duration'])
        pieces = []
        for number, start in enumerate(range(0, duration, 3600), 1):
            path = data / f'{args.model}-{video_id}-hour{number}.json'
            expected_end = min(start + 3600, duration)
            if path.exists():
                piece = json.loads(path.read_text())
                if (piece['model'] != MODELS[args.model] or piece['start'] != start
                        or piece.get('language_mode') != 'auto' or piece.get('chunk_seconds') != 30
                        or abs(piece.get('end', -1) - expected_end) > 1):
                    raise ValueError(f'Existing block has incompatible settings: {path}')
            else:
                piece = transcribe(data / f'media/{video_id}.m4a', start,
                                   min(3600, duration - start), args.model, 'auto', 30, path)
            pieces.append(piece)
        segments = [{**s, 'id': i} for i, s in enumerate(s for p in pieces for s in p['segments'])]
        seconds = sum(p['metrics']['inference_seconds'] for p in pieces)
        audio = sum(p['metrics']['audio_seconds'] for p in pieces)
        result = {
            'model': MODELS[args.model], 'language_mode': 'auto', 'chunk_seconds': 30,
            'start': 0, 'end': pieces[-1]['end'], 'segments': segments,
            'chunks': [c for p in pieces for c in p['chunks']],
            'metrics': {'audio_seconds': audio, 'inference_seconds': seconds,
                        'real_time_factor': seconds / audio, 'speedup': audio / seconds,
                        'peak_memory_gb': max(p['metrics']['peak_memory_gb'] for p in pieces),
                        'includes_model_load': True},
            'notes': ['Full recording, assembled from contiguous cached hour blocks.',
                      'Raw ASR with no reference prompt; timestamps refer to original video.',
                      'Timing sums block inference times; cached blocks may have been run in different processes.']}
        out = data / f'{args.model}-full-{video_id}.json'
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f'Complete: {out.name}: {audio:.1f}s audio / {seconds:.1f}s inference', flush=True)


if __name__ == '__main__':
    main()
