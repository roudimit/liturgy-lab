"""Curated local LLM comparison. Sampling is exploratory, not an accuracy benchmark.

Each clip contains six consecutive ASR segments. Distinct clips never share a
prompt; all remaining full-recording segments retain explicit not_run markers.
Run --prepare-only first to inspect the actual text and chosen time ranges.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from collections import Counter

PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT / "work"
DATA = PROJECT / "data"
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("HF_HOME", str(WORK / "cache/huggingface"))

from liturgy_lab.llm import apply_guards_to_result, run_llm_alignment

MODELS = {
    "4b": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
    "17b": "mlx-community/Qwen3-1.7B-4bit",
}
OUTPUTS = {"4b": DATA / "turbo-qwen4b.json", "17b": DATA / "turbo-qwen17b.json"}
PLAN = DATA / "llm-benchmark-sample.json"


def prepare(source: dict | list, clip_starts: list[float]) -> tuple[list[dict], dict]:
    rows = source["segments"] if isinstance(source, dict) else source
    if len(clip_starts) != 8:
        raise ValueError("Specify eight clip start times: two Orthros and six Liturgy clips")
    copied = [dict(row) for row in rows]
    used = set()
    clips = []
    for index, requested in enumerate(clip_starts):
        start_index = next((i for i, row in enumerate(copied) if row["start"] >= requested), None)
        if start_index is None or start_index + 6 > len(copied):
            raise ValueError(f"Not enough ASR segments after {requested}")
        selected = copied[start_index:start_index + 6]
        ids = [str(row["id"]) for row in selected]
        if set(ids) & used:
            raise ValueError("Clip selections overlap; choose more separated clip starts")
        used.update(ids)
        clip_id = f"clip-{index + 1:02d}"
        for row in selected:
            row["llm_clip_id"] = clip_id
        clips.append({
            "clip_id": clip_id, "requested_start": requested,
            "context": "Orthros / outside supplied Divine Liturgy scope" if index < 2 else "Divine Liturgy",
            "start": selected[0]["start"], "end": selected[-1]["end"], "segment_ids": ids,
            "lexical_status_counts": dict(Counter(row.get("match", {}).get("status", "missing") for row in selected)),
            "segments": [{"id": row["id"], "start": row["start"], "end": row["end"],
                          "text": row["text"], "lexical_match": row.get("match"),
                          "top_candidate": (row.get("candidates") or [None])[0]} for row in selected],
        })
    plan = {
        "selection_method": "Eight manually spaced chronological clips, six consecutive ASR segments each; two before and six after the opening blessing.",
        "selection_note": "Exploratory convenience sample covering different sections, languages and text-support levels. Not random or representative enough for an accuracy estimate.",
        "ground_truth": "None. Comparisons measure system decisions and text-only disagreements, not audio transcription or alignment accuracy.",
        "liturgy_opening_observation": "Opening blessing appears around 4410 seconds in the raw transcript; this is a text-derived scope annotation.",
        "count": len(used), "selected_ids": sorted(used, key=lambda sid: next(i for i, row in enumerate(copied) if str(row["id"]) == sid)),
        "clips": clips,
    }
    return copied, plan


def summarize(result: dict, selected_ids: list[str]) -> dict:
    selected = set(selected_ids)
    rows = [row for row in result["segments"] if str(row["id"]) in selected]
    invalid_prefixes = ("invalid_", "missing_reason", "extra_segment_ids", "generation_error")
    invalid = [row for row in rows if any(w.startswith(invalid_prefixes) for w in row["llm_match"].get("warnings", []))]
    invalid_ids = {str(row["id"]) for row in invalid}
    invalid_batches = sum(bool(invalid_ids.intersection(batch["segment_ids"])) for batch in result["batches"])
    malformed_ids = {str(row["id"]) for row in rows if "invalid_json" in row["llm_match"].get("warnings", [])}
    disagreements = []
    for row in rows:
        lexical = row.get("match", {})
        llm = row["llm_match"]
        if lexical.get("unit_id") != llm.get("unit_id") or lexical.get("status") != llm.get("status"):
            disagreements.append({"segment_id": row["id"], "start": row["start"], "text": row["text"],
                                  "lexical": lexical, "llm": llm})
    return {
        "model": result["model"], "selected_segments": len(rows),
        "metrics": result["metrics"],
        "selected_status_counts": dict(Counter(row["llm_match"]["status"] for row in rows)),
        "raw_proposal_status_counts": dict(Counter(row.get("llm_proposal", row["llm_match"])["status"] for row in rows)),
        "invalid_decision_count": len(invalid), "batches_with_invalid_decisions": invalid_batches,
        "invalid_json_batches": sum(bool(malformed_ids.intersection(batch["segment_ids"])) for batch in result["batches"]),
        "output_token_limit_batches": sum(batch.get("finish_reason") == "length" for batch in result["batches"]),
        "lexical_disagreement_count": len(disagreements), "lexical_disagreements": disagreements,
        "raw_lexical_disagreement_count": sum(
            (row.get("match", {}).get("unit_id"), row.get("match", {}).get("status")) !=
            (row.get("llm_proposal", row["llm_match"]).get("unit_id"), row.get("llm_proposal", row["llm_match"]).get("status"))
            for row in rows),
        "note": "Differences in IDs/status are not evidence that either system is correct.",
    }


def compare() -> dict:
    results = {name: json.loads(path.read_text()) for name, path in OUTPUTS.items()}
    sample = results["4b"]["benchmark_sample"]
    if sample["selected_ids"] != results["17b"]["benchmark_sample"]["selected_ids"]:
        raise ValueError("Model outputs used different samples; rerun with identical selections")
    selected = set(sample["selected_ids"])
    by_id = {name: {str(row["id"]): row for row in result["segments"]} for name, result in results.items()}
    diffs = []
    raw_diffs = []
    for sid in sample["selected_ids"]:
        a, b = by_id["4b"][sid], by_id["17b"][sid]
        am, bm = a["llm_match"], b["llm_match"]
        ap, bp = a.get("llm_proposal", am), b.get("llm_proposal", bm)
        if (ap["unit_id"], ap["status"]) != (bp["unit_id"], bp["status"]):
            raw_diffs.append({"segment_id": a["id"], "start": a["start"], "text": a["text"],
                              "qwen4b": ap, "qwen17b": bp})
        if (am["unit_id"], am["status"]) != (bm["unit_id"], bm["status"]):
            diffs.append({"segment_id": a["id"], "start": a["start"], "text": a["text"],
                          "qwen4b": am, "qwen17b": bm})
    output = {
        "sample_size": len(selected), "ground_truth": sample["ground_truth"],
        "model_summaries": {name: summarize(result, sample["selected_ids"]) for name, result in results.items()},
        "between_model_decision_disagreements": len(diffs), "disagreements": diffs,
        "between_model_raw_proposal_disagreements": len(raw_diffs), "raw_proposal_disagreements": raw_diffs,
    }
    (DATA / "llm-comparison.json").write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps({name: {key: value for key, value in summary.items() if key != "lexical_disagreements"}
                      for name, summary in output["model_summaries"].items()}, ensure_ascii=False, indent=2), flush=True)
    print(f"Between-model decision disagreements: {len(diffs)} / {len(selected)} (not errors)", flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DATA / "turbo-full-aligned.json")
    parser.add_argument("--reference", type=Path, default=DATA / "reference.json")
    parser.add_argument("--clip-starts", default="1807,1920,4410,4500,4680,5400,6300,6900")
    parser.add_argument("--model", choices=["both", *MODELS], default="both")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--compare-only", action="store_true")
    parser.add_argument("--apply-guards-only", action="store_true", help="Apply current explicit review guards to saved model decisions, preserving originals; no GPU work")
    args = parser.parse_args()
    if args.apply_guards_only:
        for path in OUTPUTS.values():
            result = apply_guards_to_result(json.loads(path.read_text()))
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        compare()
        return
    if args.compare_only:
        compare()
        return
    source = json.loads(args.source.read_text())
    rows, sample = prepare(source, [float(value) for value in args.clip_starts.split(",")])
    PLAN.write_text(json.dumps(sample, ensure_ascii=False, indent=2))
    if args.prepare_only:
        for clip in sample["clips"]:
            print(f"{clip['clip_id']}: {clip['start']:.1f}–{clip['end']:.1f}s · {clip['context']} · {clip['lexical_status_counts']}")
            for row in clip["segments"]:
                print(f"  {row['id']}: {row['text']}")
        return
    if args.model == "both":
        # Separate processes isolate GPU memory and peak-memory accounting.
        for name in MODELS:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--source", str(args.source),
                            "--reference", str(args.reference), "--clip-starts", args.clip_starts,
                            "--model", name], check=True)
        compare()
        return
    result = run_llm_alignment(rows, json.loads(args.reference.read_text()), model=MODELS[args.model],
                               selected_ids=sample["selected_ids"], batch_size=6, max_tokens=1400,
                               progress=lambda message: print(message, flush=True))
    original = source if isinstance(source, dict) else {}
    combined = {**original, **result, "benchmark_sample": sample,
                "source_asr_model": original.get("model"), "source_asr_metrics": original.get("metrics")}
    OUTPUTS[args.model].write_text(json.dumps(combined, ensure_ascii=False, indent=2))
    print(json.dumps(summarize(result, sample["selected_ids"])["metrics"], indent=2), flush=True)


if __name__ == "__main__":
    main()
