"""Audit a combined-reference LLM experiment without treating suggestions as labels."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, default=DATA / "qwen35b-combined-MIxJvLfaynY.json")
    parser.add_argument("--reference", type=Path, default=DATA / "reference-MIxJvLfaynY.json")
    parser.add_argument("--output", type=Path, default=DATA / "qwen35b-combined-summary.json")
    parser.add_argument("--sequence-hint-version", default="v1", help="Version used by the saved experiment, not the current tracker")
    args = parser.parse_args()
    result = json.loads(args.result.read_text())
    reference = json.loads(args.reference.read_text())
    source_path = DATA / Path(result["source_asr_file"]).name
    source = json.loads(source_path.read_text())
    if result["reference_id"] != reference["reference_id"]:
        raise ValueError("Reference fingerprints differ")
    units = {unit["id"]: unit for unit in reference["units"]}
    original = {str(row["id"]): row for row in source["segments"]}
    ids = set(result["benchmark_sample"]["selected_ids"])
    rows = result["segments"]
    if set(original) != {str(row["id"]) for row in rows}:
        raise ValueError("The experiment dropped or added source segments")
    for row in rows:
        raw = original[str(row["id"])]
        if any(row[key] != raw[key] for key in ("start", "end", "text")):
            raise ValueError("An original ASR value changed")
        if str(row["id"]) not in ids and row["llm_match"]["status"] != "not_run":
            raise ValueError("An untested row has an LLM outcome")
        if row["llm_match"].get("unit_id") not in {None, *units}:
            raise ValueError("An LLM outcome has a foreign reference ID")
    selected = [row for row in rows if str(row["id"]) in ids]
    warnings = Counter(warning for row in selected for warning in row["llm_match"].get("warnings", []))
    clips = []
    for clip in result["benchmark_sample"]["clips"]:
        clip_rows = [row for row in selected if str(row["id"]) in clip["segment_ids"]]
        clips.append({**clip,
                      "raw_status_counts": dict(Counter(row["llm_proposal"]["status"] for row in clip_rows)),
                      "guarded_status_counts": dict(Counter(row["llm_match"]["status"] for row in clip_rows)),
                      "rows": [{"segment_id": str(row["id"]), "start": row["start"], "text": row["text"],
                                "sequence_match": row.get("sequence_match", row.get("match")),
                                "llm_proposal": row["llm_proposal"], "llm_match": row["llm_match"],
                                "selected_canonical": {key: units[row["llm_match"]["unit_id"]].get(key)
                                                       for key in ("id", "section_title", "greek", "english")}
                                if row["llm_match"].get("unit_id") else None} for row in clip_rows]})
    summary = {
        "model": result["model"], "reference_id": result["reference_id"],
        "recording_id": result["recording_id"], "source_asr_file": source_path.name,
        "source_asr_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "selected_segments": len(selected), "untested_segments": len(rows) - len(selected),
        "sequence_hint_version": args.sequence_hint_version,
        "sequence_comparison_note": "Compared only with the sequence proposals retained inside this experiment, not a later rerun of the tracker.",
        "saved_sequence_input_sha256": hashlib.sha256(json.dumps(
            [{"id": str(row["id"]), "sequence_match": row.get("sequence_match"), "llm_context": row.get("llm_context")}
             for row in selected], ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "integrity_checks": {"original_asr_preserved": True, "reference_ids_valid": True,
                             "untested_rows_marked_not_run": True},
        "metrics": result["metrics"],
        "raw_status_counts": dict(Counter(row["llm_proposal"]["status"] for row in selected)),
        "guarded_status_counts": dict(Counter(row["llm_match"]["status"] for row in selected)),
        "warning_counts": dict(warnings),
        "invalid_decision_count": sum(any(warning.startswith("invalid_") or warning == "missing_reason"
                                          for warning in row["llm_proposal"].get("warnings", [])) for row in selected),
        "sequence_id_disagreements": sum(row["llm_match"].get("unit_id") != row.get("sequence_match", row.get("match", {})).get("unit_id") for row in selected),
        "limits": ["Text-only exploratory audit; no listening, human transcripts or location labels.",
                   "Agreement and disagreements with the sequence tracker are not accuracy.",
                   "Reference coverage, prompting, candidates and evidence rules differ from the historical model-size control.",
                   "Substring evidence checks establish that quoted text exists, not that the semantic association is correct."],
        "clips": clips,
    }
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({key: value for key, value in summary.items() if key != "clips"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
