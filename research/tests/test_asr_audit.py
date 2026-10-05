import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/audit_asr_models.py"
spec = importlib.util.spec_from_file_location("audit_asr_models", path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def row(start, end, text="Κύριε ελέησον", score=0.9):
    return {"start": start, "end": end, "text": text, "match": {"status": "matched"},
            "candidates": [{"score": score}], "asr_warnings": []}


def test_timestamp_union_does_not_double_count_overlapping_segments():
    value = audit.time_metrics([row(0, 20), row(10, 30, score=0.8)], 0, 30)
    assert value["sequence_associated_speech_seconds"] == 30
    assert value["asr_timestamped_speech_seconds"] == 30
    assert value["reference_evidence_score_seconds"] == 26


def test_duration_metrics_are_invariant_to_segment_splitting():
    whole = audit.time_metrics([row(0, 20)], 0, 30)
    split = audit.time_metrics([row(0, 10), row(10, 20)], 0, 30)
    for key in ("sequence_associated_speech_seconds", "asr_timestamped_speech_seconds", "reference_evidence_score_seconds"):
        assert whole[key] == split[key]


def test_warning_detector_is_recomputed_instead_of_trusting_old_fields():
    value = audit.time_metrics([row(5, 12, text="Υπότιτλοι AUTHORWAVE")], 0, 30)
    assert value["warning_affected_speech_seconds"] == 7


def test_script_counts_separate_greek_from_latin_without_claiming_language():
    assert audit.script_counts("Ἅγιος Θεός / Agios Theos") == {"greek_letters": 9, "latin_letters": 10, "other_letters": 0}
