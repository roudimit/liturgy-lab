"""Build viewer datasets using checked per-recording combined references.

Run again as full ASR files arrive. Only CPU alignment runs here. Old LLM
decisions against the September 30 corpus are never attached to new unit IDs.
"""
from __future__ import annotations
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from liturgy_lab.align import ALIGNMENT_VERSION, align_sequence, detect_liturgy_start
from liturgy_lab.asr import asr_warnings
from liturgy_lab.subtitles import to_vtt

DATA = ROOT / 'data'
RECORDINGS = ['MIxJvLfaynY', 'vkkeLmltf_4', 'IuZ8WRk-POI', 'n674zECLjTI', 'ZUMoL5VwJzw']


def read(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))


def write(name, value):
    path = DATA / name
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=DATA, prefix=f'.{path.stem}-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def asr_digest(original):
    raw = [{k: s.get(k) for k in ['id', 'start', 'end', 'text', 'language']} for s in original['segments']]
    return hashlib.sha256(json.dumps({'segments': raw, 'intervals': original.get('intervals', [])}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate_matches(segments, reference):
    units = {u['id'] for u in reference['units']}
    sections = {s['id'] for s in reference['sections']}
    for segment in segments:
        for field in ['match', 'sequence_match', 'lexical_match', 'llm_match', 'automatic_sequence_match']:
            match = segment.get(field) or {}
            if match.get('unit_id') is not None and match['unit_id'] not in units:
                raise ValueError(f"{field} references an incompatible unit: {match['unit_id']!r}")
            if match.get('section_id') is not None and match['section_id'] not in sections:
                raise ValueError(f"{field} references an incompatible section: {match['section_id']!r}")


def sequence_run(name, reference, recording_id):
    original = read(name + '.json')
    if original.get('reference_id') == reference['reference_id'] and original.get('alignment', {}).get('method') in {'sequence', 'sequence_with_explicit_supplemental_phrase_spans'} and original.get('alignment', {}).get('version') == ALIGNMENT_VERSION:
        validate_matches(original['segments'], reference)
        return name, original
    if original.get('source_asr_model') or any('llm_match' in s for s in original.get('segments', [])):
        raise ValueError(f'Refusing to reinterpret historical LLM output {name} with another reference')
    digest = asr_digest(original)
    target = name if name.endswith('-sequence') else name + '-sequence'
    if (DATA / (target + '.json')).exists():
        cached = read(target + '.json')
        boundaries_ok = len(original.get('intervals', [])) <= 1 or cached.get('alignment', {}).get('explicit_clip_boundaries')
        version_ok = cached.get('alignment', {}).get('version') == ALIGNMENT_VERSION
        if version_ok and boundaries_ok and cached.get('reference_id') == reference['reference_id'] and (cached.get('source_asr_sha256') == digest or asr_digest(cached) == digest):
            validate_matches(cached['segments'], reference)
            return target, cached
    fields = {'id', 'start', 'end', 'text', 'language', 'words', 'avg_logprob', 'no_speech_prob', 'compression_ratio', 'asr_warnings', 'clip_id'}
    clean = [{k: v for k, v in s.items() if k in fields} for s in original['segments']]
    intervals = original.get('intervals', [])
    if len(intervals) > 1:
        for segment in clean:
            if segment.get('clip_id') is None:
                interval_index = next((i for i, window in enumerate(intervals) if window['start'] <= segment.get('start', -1) < window['end']), None)
                if interval_index is not None:
                    segment['clip_id'] = f'window-{interval_index}'
    print(f"Aligning {name}: {len(clean)} segments against {reference['reference_id']}", flush=True)
    segments = align_sequence(clean, reference)
    result = {**{k: v for k, v in original.items() if k not in {'segments', 'alignment', 'reference_id'}},
              'segments': segments, 'recording_id': recording_id,
              'reference_id': reference['reference_id'], 'source_asr_file': name + '.json',
              'source_asr_sha256': digest, 'alignment': {'method': 'sequence', 'version': ALIGNMENT_VERSION, 'explicit_clip_boundaries': True, 'reference_path': f'data/reference-{recording_id}.json'}}
    validate_matches(segments, reference)
    write(target + '.json', result)
    return target, result


def compact_run(name, original, label, reference, duration):
    validate_matches(original['segments'], reference)
    keep = {'id', 'start', 'end', 'text', 'language', 'match', 'sequence_match', 'lexical_match', 'llm_match', 'sequence', 'sequence_section_hint', 'service_context', 'asr_warnings', 'supplemental_evidence', 'automatic_sequence_match'}
    segments = [{**{k: v for k, v in s.items() if k in keep}, 'asr_warnings': asr_warnings(s.get('text', ''))} for s in original['segments']]
    fields = {'start', 'end', 'intervals', 'model', 'language_mode', 'chunk_seconds', 'metrics', 'notes', 'llm_metrics', 'llm_model', 'alignment', 'reference_id', 'source_asr_file', 'source_asr_files', 'historical_reference'}
    metadata = {k: v for k, v in original.items() if k in fields}
    if 'source_asr_metrics' in original:
        metadata.update(llm_metrics=original['metrics'], metrics=original['source_asr_metrics'], llm_model=original['model'], model=original['source_asr_model'])
        tracker_versions = sorted({s['sequence']['version'] for s in original['segments'] if isinstance(s.get('sequence', {}).get('version'), int)})
        if tracker_versions:
            metadata['candidate_tracker_versions'] = tracker_versions
            if tracker_versions != [ALIGNMENT_VERSION]:
                note = f"This saved LLM experiment used tracker version {', '.join(map(str, tracker_versions))} for its sequence baseline and candidate context. The default tracker is now version {ALIGNMENT_VERSION}; the LLM decisions were not rerun with that tracker."
                existing_notes = metadata.get('notes', [])
                metadata['notes'] = (existing_notes if isinstance(existing_notes, list) else [existing_notes]) + [note]
    if not metadata.get('intervals') and isinstance(metadata.get('start'), (int, float)) and isinstance(metadata.get('end'), (int, float)):
        metadata['intervals'] = [{'start': metadata['start'], 'end': metadata['end']}]
    complete = bool(metadata.get('start', 1) <= 0.1 and metadata.get('end', 0) >= duration - 3)
    metadata.update(id=name, label=label, segments=segments, complete=complete, opening_detection=detect_liturgy_start(segments))
    (DATA / (name + '.vtt')).write_text(to_vtt(segments), encoding='utf-8')
    return metadata


def candidate_runs(video_id):
    if video_id == RECORDINGS[0]:
        return [('turbo-full', 'Whisper Turbo · full recording'),
                ('large-v3-full', 'Whisper Large v3 · full recording'),
                ('asr-compare-large-v3', 'Whisper Large v3 · 24-minute comparison'),
                ('asr-compare-turbo', 'Whisper Turbo · 24-minute comparison'),
                ('asr-compare-small', 'Whisper Small · 24-minute comparison'),
                ('large-v3-greek-retries-sequence', 'Whisper Large v3 · forced-Greek 2 × 30s retry'),
                ('large-v3-auto-pilot', 'Whisper Large v3 · 3-minute pilot'),
                ('turbo-auto-pilot', 'Whisper Turbo · 30s language detection'),
                ('small-auto-pilot', 'Whisper Small · 30s language detection'),
                ('turbo-continuous-pilot', 'Whisper Turbo · one language detection')]
    full = f'turbo-full-{video_id}'
    if (DATA / (full + '.json')).exists():
        return [(full, 'Whisper Turbo · full recording')]
    candidates = []
    for prefix, label in [('turbo-extended-', 'Whisper Turbo · expanded samples'), ('turbo-samples-', 'Whisper Turbo · sampled windows')]:
        if (DATA / (prefix + video_id + '.json')).exists():
            candidates.append((prefix + video_id, label))
            break
    first_hour = f'turbo-{video_id}-hour1'
    if (DATA / (first_hour + '.json')).exists():
        candidates.insert(0, (first_hour, 'Whisper Turbo · first hour'))
    return candidates


def main():
    recordings = []
    for video_id in RECORDINGS:
        reference_name = f'reference-{video_id}.json'
        source_name = 'source.json' if video_id == RECORDINGS[0] else f'source-{video_id}.json'
        if not (DATA / reference_name).exists() or not (DATA / source_name).exists():
            continue
        reference, source = read(reference_name), read(source_name)
        runs = []
        references = {reference['reference_id']: reference}
        for name, label in candidate_runs(video_id):
            if not (DATA / (name + '.json')).exists():
                continue
            run_name, original = sequence_run(name, reference, video_id)
            runs.append(compact_run(run_name, original, label, reference, source['duration']))
        # New LLM runs must explicitly identify their recording and exact corpus.
        existing = {run['id'] for run in runs}
        for path in sorted(DATA.glob('*.json')):
            if path.stem in existing or path.name.startswith(('session', 'reference', 'source', 'sequence-audit')) or '.progress.' in path.name:
                continue
            try:
                candidate = read(path.name)
            except json.JSONDecodeError:
                continue  # Another process may still be finishing a result.
            if not isinstance(candidate, dict) or candidate.get('recording_id') != video_id or candidate.get('reference_id') != reference['reference_id'] or not isinstance(candidate.get('segments'), list):
                continue
            if not candidate['segments'] or not any(s.get('llm_match') for s in candidate['segments']):
                continue
            model_name = str(candidate.get('model', 'Local LLM')).rsplit('/', 1)[-1]
            label = candidate.get('label', f"{model_name} · combined reference")
            versions = sorted({s['sequence']['version'] for s in candidate['segments'] if isinstance(s.get('sequence', {}).get('version'), int)})
            if versions and versions != [ALIGNMENT_VERSION]:
                label += f" · tracker v{'/'.join(map(str, versions))} context"
            runs.append(compact_run(path.stem, candidate, label, reference, source['duration']))
        if video_id == RECORDINGS[0] and (DATA / 'reference.json').exists():
            legacy = read('reference.json')
            legacy['reference_id'] = 'legacy-' + legacy['source_sha256'][:20]
            legacy['selection'] = {'status': 'historical_mismatched_date', 'edition_date': legacy['date'],
                                   'caveat': 'Historical model comparison only. These saved LLM decisions use the originally supplied 2026-09-30 Liturgy-only reference, which omits Matins and differs from the recording date. They have not been rerun against the new combined reference.'}
            references[legacy['reference_id']] = legacy
            for name, model_label in [('turbo-qwen4b', 'Qwen 4B'), ('turbo-qwen17b', 'Qwen 1.7B'), ('turbo-qwen30b', 'Qwen 30B'), ('turbo-qwen35b', 'Qwen 35B')]:
                if not (DATA / (name + '.json')).exists():
                    continue
                historical = read(name + '.json')
                historical.update(reference_id=legacy['reference_id'], historical_reference=True)
                label = f'{model_label} · historical 48-segment comparison'
                runs.append(compact_run(name, historical, label, legacy, source['duration']))
        if not runs:
            print(f'No completed ASR for {video_id}; reference is ready.', flush=True)
            continue
        primary = runs[0]
        suggested = next((s['start'] for s in primary['segments'] if (s.get('match') or {}).get('status') == 'matched'), primary['segments'][0]['start'] if primary['segments'] else 0)
        source.update(preview_start=suggested, reference_url=reference['source_url'], reference_date=reference['date'], reference_status=reference['selection']['status'], caveat=reference['selection']['caveat'])
        coverage = 'Full recording transcribed. ' if primary['complete'] else 'Only the listed audio windows have been transcribed; gaps have no prediction. '
        source['experiment_note'] = coverage + 'Matins and Liturgy are both in the reference. Locations are sequence-supported predictions, not independently verified timing. Raw ASR is displayed separately from canonical service text.'
        source['sample_windows'] = primary.get('intervals', [])
        session_name = 'session.json' if video_id == RECORDINGS[0] else f'session-{video_id}.json'
        write(session_name, {'source': source, 'reference': reference, 'references': references, 'runs': runs, 'default_run': primary['id']})
        recordings.append({'id': video_id, 'title': source['title'], 'session_file': session_name, 'media_file': 'video.mp4' if video_id == RECORDINGS[0] else f'{video_id}.mp4'})
        print(f"Built {session_name}: {len(runs)} runs, {len(primary['segments'])} segments, {len(reference['units'])} reference units", flush=True)
    write('recordings.json', recordings)
    print(f'Built {len(recordings)} recording sessions', flush=True)


if __name__ == '__main__':
    main()
