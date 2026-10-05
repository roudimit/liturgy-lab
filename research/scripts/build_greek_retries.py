#!/usr/bin/env python3
"""Build a separate forced-Greek retry view with explicit adjacent-fragment evidence.

This supplemental experiment never rewrites raw text, timestamps or the frozen
automatic-language comparison. Associations supported by two ASR fragments carry
the entire evidence span; they are not claims of independent fragment accuracy.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from liturgy_lab.align import ALIGNMENT_VERSION, ReferenceIndex, align_sequence, normalize


def support_adjacent_fragments(rows, reference):
    index = ReferenceIndex(reference)
    for i in range(len(rows) - 1):
        left, right = rows[i:i + 2]
        if left.get("clip_id") != right.get("clip_id") or not 0 <= right["start"] - left["end"] <= 2:
            continue
        if left.get("asr_warnings") or right.get("asr_warnings"):
            continue
        combined = left["text"] + " " + right["text"]
        if min(len(normalize(r["text"]).split()) for r in (left, right)) < 2 or len(normalize(combined).split()) < 5:
            continue
        candidates = index.retrieve(combined, top_k=2)
        if not candidates or candidates[0]["score"] < .90 or (len(candidates) > 1 and candidates[0]["score"] - candidates[1]["score"] < .10):
            continue
        best = candidates[0]
        evidence = {"kind": "adjacent_raw_fragments", "segment_ids": [left["id"], right["id"]],
                    "start": left["start"], "end": right["end"], "joined_text_for_retrieval_only": combined,
                    "span_score": best["score"], "independent_fragment_accuracy_claimed": False}
        for row in (left, right):
            row["automatic_sequence_match"] = dict(row["match"])
            row["match"] = {"unit_id": best["unit_id"], "unit_index": best["index"], "section_id": best["section_id"],
                            "section_title": best["section_title"], "service_id": best["service_id"], "service_title": best["service_title"],
                            "status": "matched", "score": best["score"], "method": "supplemental_adjacent_phrase",
                            "reason": "Association supported by the explicitly recorded two-fragment phrase span; individual words remain unverified"}
            row["sequence_match"] = dict(row["match"])
            row["supplemental_evidence"] = dict(evidence)
        # A short preceding rubric may be located only with strong lexical
        # evidence and the immediately following distinct reference unit.
        if i and rows[i - 1].get("clip_id") == left.get("clip_id"):
            prior = rows[i - 1]
            suggestions = index.retrieve(prior["text"], top_k=2)
            if (suggestions and suggestions[0]["index"] == best["index"] - 1
                    and suggestions[0]["score"] >= .88 and len(suggestions) > 1
                    and suggestions[0]["score"] - suggestions[1]["score"] >= .10
                    and 0 <= left["start"] - prior["end"] <= 10):
                candidate = suggestions[0]
                prior["automatic_sequence_match"] = dict(prior["match"])
                prior["match"] = {"unit_id": candidate["unit_id"], "unit_index": candidate["index"],
                                  "section_id": candidate["section_id"], "section_title": candidate["section_title"],
                                  "service_id": candidate["service_id"], "service_title": candidate["service_title"],
                                  "status": "matched", "score": candidate["score"], "method": "supplemental_adjacent_phrase",
                                  "reason": "Strong short-rubric lexical evidence immediately precedes a distinctive adjacent-fragment passage"}
                prior["sequence_match"] = dict(prior["match"])
                prior["supplemental_evidence"] = {**evidence, "kind": "preceding_rubric_plus_adjacent_phrase"}
    return rows


def main():
    data = ROOT / "data"
    reference = json.loads((data / "reference-MIxJvLfaynY.json").read_text())
    inputs = [(f"data/large-v3-greek-retry-{start}.json", json.loads((data / f"large-v3-greek-retry-{start}.json").read_text())) for start in (1950, 4920)]
    raw = [{**row, "source_segment_id": row["id"], "id": f"{int(payload['start'])}:{row['id']}",
            "clip_id": str(int(payload["start"])), "source_asr_file": path}
           for path, payload in inputs for row in payload["segments"]]
    rows = support_adjacent_fragments(align_sequence(raw, reference), reference)
    intervals = [{"start": payload["start"], "end": payload["end"], "source_file": path} for path, payload in inputs]
    inference_seconds = sum(p["metrics"]["inference_seconds"] for _, p in inputs)
    result = {"model": inputs[0][1]["model"], "language_mode": "el", "chunk_seconds": 30,
              "start": 1950, "end": 4950, "intervals": intervals,
              "unprocessed_intervals": [{"start": 1980, "end": 4920}],
              "segments": rows, "chunks": [chunk for _, payload in inputs for chunk in payload["chunks"]],
              "reference_id": reference["reference_id"], "source_asr_files": [path for path, _ in inputs],
              "metrics": {"audio_seconds": 60, "inference_seconds": inference_seconds,
                          "real_time_factor": inference_seconds / 60, "speedup": 60 / inference_seconds,
                          "includes_model_load": True,
                          "peak_memory_gb": max(p["metrics"]["peak_memory_gb"] for _, p in inputs)},
              "alignment": {"method": "sequence_with_explicit_supplemental_phrase_spans", "version": ALIGNMENT_VERSION,
                            "explicit_clip_boundaries": True, "supplemental_only": True},
              "notes": ["Two selected difficult clips were re-run with Greek forced; this is not the default automatic-language system.",
                        "Raw ASR text and timestamps are unchanged. The large gap between clips was not processed.",
                        "Two adjacent short fragments can share one explicitly recorded phrase-span association; this does not provide independent word accuracy.",
                        "This selected retry does not alter the frozen 24-minute ASR comparison or establish overall Greek accuracy."]}
    target = data / "large-v3-greek-retries-sequence.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps([{"start": r["start"], "text": r["text"], "match": r["match"]} for r in rows], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
