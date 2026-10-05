import json
from pathlib import Path
import re

data = Path(__file__).resolve().parents[1] / 'outputs/liturgy-lab/data'
recordings = ['n674zECLjTI', 'vkkeLmltf_4', 'IuZ8WRk-POI']
for video in recordings:
    completed = data / f'turbo-full-{video}.json'
    if completed.exists():
        payload = json.loads(completed.read_text())
        print(video, 'FULL COMPLETE', round(payload['metrics']['audio_seconds'] / 60, 1), 'min audio;',
              round(payload['metrics']['inference_seconds'] / 60, 1), 'min model time;', len(payload['segments']), 'segments')
        continue
    blocks = [path for path in data.glob(f'turbo-{video}-hour*.json')
              if re.fullmatch(r'turbo-' + re.escape(video) + r'-hour\d+\.json', path.name)]
    active = list(data.glob(f'turbo-{video}-hour*.json.progress.json'))
    print(video, len(blocks), 'completed hour blocks', end='')
    for path in active:
        payload = json.loads(path.read_text())
        if payload.get('chunks'):
            print('; active through', round(payload['chunks'][-1]['end'] / 60, 1), 'min', end='')
    print()
