import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location('build_sessions', Path(__file__).resolve().parents[1] / 'scripts' / 'build_sessions.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def corpus():
    return {'reference_id': 'ref-current', 'units': [{'id': 'matins:u0001'}], 'sections': [{'id': 'matins:s001'}]}


def test_incompatible_unit_and_section_ids_are_rejected():
    with pytest.raises(ValueError, match='incompatible unit'):
        builder.validate_matches([{'llm_match': {'unit_id': 'u0001'}}], corpus())
    with pytest.raises(ValueError, match='incompatible section'):
        builder.validate_matches([{'match': {'section_id': 's001'}}], corpus())
    builder.validate_matches([{'match': {'unit_id': 'matins:u0001', 'section_id': 'matins:s001'}}], corpus())


def test_sequence_cache_requires_correct_reference_and_same_asr(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, 'DATA', tmp_path)
    raw = {'segments': [{'id': 1, 'start': 0, 'end': 5, 'text': 'raw words', 'language': 'en'}]}
    cached = {**raw, 'reference_id': 'ref-current', 'alignment': {'method': 'sequence', 'version': builder.ALIGNMENT_VERSION}}
    (tmp_path / 'sample.json').write_text(json.dumps(raw))
    (tmp_path / 'sample-sequence.json').write_text(json.dumps(cached))
    def should_not_run(*args, **kwargs):
        raise AssertionError('Matching cache should be reused')
    monkeypatch.setattr(builder, 'align_sequence', should_not_run)
    name, result = builder.sequence_run('sample', corpus(), 'video')
    assert name == 'sample-sequence'
    assert result['segments'][0]['text'] == 'raw words'
    cached['reference_id'] = 'wrong-reference'
    (tmp_path / 'sample-sequence.json').write_text(json.dumps(cached))
    calls = []
    monkeypatch.setattr(builder, 'align_sequence', lambda segments, ref: calls.append(segments) or segments)
    builder.sequence_run('sample', corpus(), 'video')
    assert len(calls) == 1
    cached['reference_id'] = 'ref-current'
    cached['alignment']['version'] = builder.ALIGNMENT_VERSION - 1
    (tmp_path / 'sample-sequence.json').write_text(json.dumps(cached))
    builder.sequence_run('sample', corpus(), 'video')
    assert len(calls) == 2


def test_historical_llm_is_never_reinterpreted_with_new_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, 'DATA', tmp_path)
    old = {'segments': [{'id': 1, 'text': 'raw', 'llm_match': {'unit_id': 'u1'}}]}
    (tmp_path / 'old-llm.json').write_text(json.dumps(old))
    with pytest.raises(ValueError, match='historical LLM'):
        builder.sequence_run('old-llm', corpus(), 'video')


def test_full_recording_replaces_samples_when_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, 'DATA', tmp_path)
    video = 'vkkeLmltf_4'
    (tmp_path / f'turbo-samples-{video}.json').write_text('{}')
    assert builder.candidate_runs(video)[0][0] == f'turbo-samples-{video}'
    (tmp_path / f'turbo-full-{video}.json').write_text('{}')
    assert builder.candidate_runs(video) == [(f'turbo-full-{video}', 'Whisper Turbo · full recording')]


def test_explicit_sample_windows_reset_sequence_even_with_short_gaps(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, 'DATA', tmp_path)
    raw = {'intervals': [{'start': 0, 'end': 30}, {'start': 60, 'end': 90}],
           'segments': [{'id': 1, 'start': 20, 'end': 30, 'text': 'first clip'},
                        {'id': 2, 'start': 60, 'end': 70, 'text': 'second clip'}]}
    (tmp_path / 'samples.json').write_text(json.dumps(raw))
    calls = []
    monkeypatch.setattr(builder, 'align_sequence', lambda segments, ref: calls.append(segments) or segments)
    _, result = builder.sequence_run('samples', corpus(), 'video')
    assert calls[0][0]['clip_id'] == 'window-0'
    assert calls[0][1]['clip_id'] == 'window-1'
    assert result['alignment']['explicit_clip_boundaries'] is True
    assert [s['text'] for s in result['segments']] == ['first clip', 'second clip']
