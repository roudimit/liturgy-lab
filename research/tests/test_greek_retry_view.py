import copy

from scripts.build_greek_retries import support_adjacent_fragments
from liturgy_lab.align import align_sequence


def test_supplemental_phrase_span_preserves_fragments_and_timestamps():
    reference = {"units": [{"id": "u0", "index": 0, "kind": "spoken", "greek": "Δεῦτε προσκυνήσωμεν καὶ προσπέσωμεν Χριστῷ", "english": "Come let us worship and bow down before Christ", "section_id": "s0", "section_title": "Entrance Hymn", "service_id": "liturgy", "service_title": "Liturgy"}]}
    raw = [{"id": "a", "clip_id": "one", "start": 10, "end": 13, "text": "Δεύτε προσκυνήσωμεν"},
           {"id": "b", "clip_id": "one", "start": 13.5, "end": 20, "text": "Και προσπέσωμεν Χριστό"}]
    original = copy.deepcopy(raw)
    rows = support_adjacent_fragments(align_sequence(raw, reference), reference)
    assert [r["match"]["unit_id"] for r in rows] == ["u0", "u0"]
    assert raw == original
    assert [(r["start"], r["end"], r["text"]) for r in rows] == [(r["start"], r["end"], r["text"]) for r in raw]
    assert rows[0]["supplemental_evidence"]["segment_ids"] == ["a", "b"]
    assert rows[0]["supplemental_evidence"]["independent_fragment_accuracy_claimed"] is False


def test_supplemental_context_never_crosses_independent_clip_boundary():
    reference = {"units": [{"id": "u0", "index": 0, "kind": "spoken", "greek": "", "english": "Come let us worship and bow down before Christ", "section_id": "s0", "section_title": "Entrance Hymn", "service_id": "liturgy", "service_title": "Liturgy"}]}
    raw = [{"id": "a", "clip_id": "one", "start": 10, "end": 13, "text": "Come let us worship"},
           {"id": "b", "clip_id": "two", "start": 13.5, "end": 20, "text": "and bow down before Christ"}]
    rows = support_adjacent_fragments(align_sequence(raw, reference), reference)
    assert all("supplemental_evidence" not in r for r in rows)
