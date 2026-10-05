"""MLX Whisper transcription, with auditable timing and chunk language decisions."""
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(os.environ.get('LITURGY_WORK_DIR', str(ROOT / 'work')))
os.environ.setdefault('HF_HOME', str(WORK / 'cache/huggingface'))
os.environ.setdefault('NUMBA_CACHE_DIR', str(WORK / 'cache/numba'))
MODELS = {'turbo': 'mlx-community/whisper-large-v3-turbo', 'small': 'mlx-community/whisper-small-mlx',
          'large-v3': 'mlx-community/whisper-large-v3-mlx'}

def asr_warnings(text):
    suspects = ('authorwave', 'υπότιτλοι', 'thank you for watching', 'thanks for watching', 'subscribe to')
    return ['Possible subtitle/promotion artifact in ASR; listen to verify.'] if any(x in text.casefold() for x in suspects) else []

def read_audio(path, start=0, duration=None):
    import imageio_ffmpeg
    import numpy as np
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-ss', str(start), '-i', str(path)]
    if duration is not None:
        cmd += ['-t', str(duration)]
    cmd += ['-f', 'f32le', '-ac', '1', '-ar', '16000', '-']
    return np.frombuffer(subprocess.check_output(cmd), dtype=np.float32).copy()

def transcribe(path, start=0, duration=None, model='turbo', language='auto', chunk_seconds=30, output=None):
    """Independent chunks redetect language; language='continuous' detects only once.

    No reference-text prompt is supplied: recognition is evaluated independently.
    Segment and word timestamps refer to the original, untrimmed recording.
    """
    import mlx_whisper
    import mlx.core as mx
    if start < 0 or (duration is not None and duration <= 0) or chunk_seconds <= 0:
        raise ValueError('start must be nonnegative, duration/chunk_seconds positive')
    t0 = time.perf_counter()
    audio = read_audio(path, start, duration)
    decode_seconds = time.perf_counter() - t0
    if not len(audio):
        raise ValueError('No audio in requested interval')
    audio_seconds = len(audio) / 16000
    step = len(audio) if language == 'continuous' else round(chunk_seconds * 16000)
    segments, chunks = [], []
    inference_start = time.perf_counter()
    for i in range(0, len(audio), step):
        offset = start + i / 16000
        wall = time.perf_counter()
        result = mlx_whisper.transcribe(
            audio[i:i+step], path_or_hf_repo=MODELS.get(model, model),
            language=None if language in ('auto', 'continuous') else language,
            task='transcribe', temperature=0.0, condition_on_previous_text=False,
            word_timestamps=True, verbose=None,
        )
        elapsed = time.perf_counter() - wall
        chunk_end = min(offset + step / 16000, start + audio_seconds)
        chunks.append({'start': offset, 'end': chunk_end, 'language': result.get('language'), 'seconds': elapsed})
        for seg in result['segments']:
            s = dict(seg)
            s['id'] = len(segments)
            s['start'] = round(offset + s['start'], 3)
            s['end'] = round(min(offset + s['end'], chunk_end), 3)
            s['text'] = s['text'].strip()
            s['asr_warnings'] = asr_warnings(s['text'])
            s['language'] = result.get('language')
            s.pop('tokens', None)
            for word in s.get('words', []):
                word['start'] = round(offset + word['start'], 3)
                word['end'] = round(min(offset + word['end'], chunk_end), 3)
            if s['text'] and s['end'] > s['start']:
                segments.append(s)
        print(f"{offset:.0f}-{chunk_end:.0f}s: {result.get('language')} · {elapsed:.1f}s · {result['text'][:130]}", flush=True)
        if output:
            Path(str(output) + '.progress.json').write_text(json.dumps({'segments': segments, 'chunks': chunks}, ensure_ascii=False, indent=2))
    elapsed = time.perf_counter() - inference_start
    payload = {'model': MODELS.get(model, model), 'language_mode': language,
               'chunk_seconds': chunk_seconds if language != 'continuous' else None,
               'start': start, 'end': start + audio_seconds, 'segments': segments, 'chunks': chunks,
               'metrics': {'audio_seconds': audio_seconds, 'inference_seconds': elapsed,
                           'decode_seconds': decode_seconds, 'real_time_factor': elapsed / audio_seconds,
                           'speedup': audio_seconds / elapsed, 'peak_memory_gb': mx.get_peak_memory() / 1e9,
                           'includes_model_load': True},
               'notes': ['Raw uncorrected ASR; no reference prompt.', 'Independent chunk boundaries can split words.',
                         'Language is detected once per chunk, so within-chunk switches can still fail.',
                         'Speed includes model load and first-use compilation; downloads should be completed first.']}
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        Path(str(output) + '.progress.json').unlink(missing_ok=True)
    return payload

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio')
    p.add_argument('--start', type=float, default=1807)
    p.add_argument('--duration', type=float, default=180)
    p.add_argument('--model', default='turbo')
    p.add_argument('--language', choices=['auto', 'continuous', 'el', 'en'], default='auto')
    p.add_argument('--chunk-seconds', type=float, default=30)
    p.add_argument('--output', required=True)
    a=p.parse_args()
    result=transcribe(a.audio,a.start,a.duration,a.model,a.language,a.chunk_seconds,a.output)
    print(json.dumps(result['metrics'],indent=2))
