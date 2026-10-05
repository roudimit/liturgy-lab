"""Matched-window, raw-ASR comparison. No canonical prompt or transcript correction.

Run each model in a fresh process after downloading its weights. The selected
24 minutes span Matins, Liturgy, Greek/English, chant and the closing address;
they are exploratory, purposively selected windows, not an accuracy test set.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from liturgy_lab.asr import MODELS, transcribe

STARTS = [1200, 1800, 1950, 2700, 3600, 4410, 4680, 4860,
          5040, 5220, 5430, 6000, 6300, 6690, 7200, 7500]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=sorted(MODELS), required=True)
    parser.add_argument('--starts', default=','.join(map(str, STARTS)))
    parser.add_argument('--duration', type=int, default=90)
    args = parser.parse_args()
    starts = [int(x) for x in args.starts.split(',')]
    data = ROOT / 'data'
    pieces = []
    for start in starts:
        dest = data / f'asr-compare-{args.model}-{start}.json'
        if dest.exists():
            result = json.loads(dest.read_text())
        else:
            result = transcribe(data / 'media/source-audio.m4a', start,
                                args.duration, args.model, 'auto', 30, dest)
        pieces.append(result)
    segments = []
    for piece in pieces:
        for segment in piece['segments']:
            segments.append({**segment, 'id': len(segments)})
    seconds = sum(p['metrics']['inference_seconds'] for p in pieces)
    duration = sum(p['metrics']['audio_seconds'] for p in pieces)
    combined = {
        'model': MODELS[args.model], 'language_mode': 'auto', 'chunk_seconds': 30,
        'start': starts[0], 'end': pieces[-1]['end'],
        'intervals': [{'start': p['start'], 'end': p['end']} for p in pieces],
        'segments': segments, 'chunks': [c for p in pieces for c in p['chunks']],
        'metrics': {'audio_seconds': duration, 'inference_seconds': seconds,
                    'speedup': duration / seconds, 'real_time_factor': seconds / duration,
                    'peak_memory_gb': max(p['metrics']['peak_memory_gb'] for p in pieces),
                    'includes_model_load': True},
        'notes': ['Same audio windows and decoding settings across models.',
                  'No canonical text supplied to ASR.',
                  'Exploratory windows selected across the service, not randomly sampled.',
                  'Text-match scores are retrieval proxies, not word accuracy.',
                  'Language detection per 30-second chunk; within-chunk switches remain difficult.']}
    (data / f'asr-compare-{args.model}.json').write_text(
        json.dumps(combined, ensure_ascii=False, indent=2))
    print(json.dumps(combined['metrics'], indent=2), flush=True)


if __name__ == '__main__':
    main()
