"""Replay the original saved prompts on larger local models, retaining controls.

These tests isolate the LLM change. They deliberately keep the original
date-mismatched reference; the new combined-reference/progression pipeline is a
different experiment and must not be presented as a pure model-size comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT / "work"
DATA = PROJECT / "data"
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))
os.environ.setdefault("HF_HOME", str(WORK / "cache/huggingface"))

from benchmark_llm import summarize
from liturgy_lab.llm import build_messages, run_llm_alignment

MODELS = {
    "30b": "mlx-community/Qwen3-30B-A3B-Instruct-2507-4bit",
    "32b": "mlx-community/Qwen3-32B-4bit",
    "35b": "mlx-community/Qwen3.6-35B-A3B-4bit",
}


def prompt_hash(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--source", type=Path, default=DATA / "turbo-qwen4b.json")
    parser.add_argument("--reference", type=Path, default=DATA / "reference.json")
    parser.add_argument("--clips", default="all", help="all or comma-separated saved clip IDs, for a timed pilot")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    control = json.loads(args.source.read_text())
    by_id = {str(row["id"]): row for row in control["segments"]}
    allowed_clips = {clip["clip_id"] for clip in control["benchmark_sample"]["clips"]}
    chosen_clips = allowed_clips if args.clips == "all" else set(args.clips.split(","))
    if chosen_clips - allowed_clips:
        raise ValueError("Unknown clip ID")
    ids = [str(row["id"]) for row in control["segments"] if row.get("llm_clip_id") in chosen_clips]
    selected_batches = [batch for batch in control["batches"] if set(batch["segment_ids"]).intersection(ids)]
    for batch in selected_batches:
        reconstructed = build_messages([by_id[sid] for sid in batch["segment_ids"]])
        if reconstructed != batch["messages"]:
            raise ValueError("Current prompt builder differs from the saved control; refusing an uncontrolled comparison")
    experiment = {
        "type": "controlled_saved_prompt_replay",
        "control": args.source.name,
        "selected_ids": ids,
        "selected_clips": sorted(chosen_clips),
        "saved_prompt_sha256": [prompt_hash(batch["messages"]) for batch in selected_batches],
        "maximum_control_prompt_tokens": max(batch["prompt_tokens"] for batch in selected_batches),
        "temperature": 0.0, "max_output_tokens": 1400, "max_prompt_tokens": 12000,
        "note": "Same raw ASR, candidate texts, chronological clips, instructions and generation budget as 4B control. Model tokenizer/template can differ. Original reference date mismatch intentionally retained.",
        "accuracy_note": "No human ground truth. Decision counts, structured-output validity and textual disagreements are not accuracy estimates.",
    }
    print(json.dumps(experiment, ensure_ascii=False, indent=2), flush=True)
    if args.prepare_only:
        return
    rows = []
    for original in control["segments"]:
        row = {key: value for key, value in original.items() if key not in {"llm_match", "llm_proposal"}}
        rows.append(row)
    inventory_path = DATA / "large-model-inventory.json"
    inventory = json.loads(inventory_path.read_text()) if inventory_path.exists() else []
    model_inventory = next((row for row in inventory if row["model"] == MODELS[args.model]), None)
    if not model_inventory or not model_inventory.get("download_complete") or not model_inventory.get("validation"):
        raise ValueError("Download and validate the pinned model snapshot before inference")
    result = run_llm_alignment(rows, json.loads(args.reference.read_text()), model=MODELS[args.model],
                               selected_ids=ids, batch_size=6, max_tokens=1400, max_prompt_tokens=12000,
                               runtime_model_path=model_inventory["snapshot"],
                               progress=lambda message: print(message, flush=True))
    actual_hashes = [prompt_hash(batch["messages"]) for batch in result["batches"]]
    if actual_hashes != experiment["saved_prompt_sha256"]:
        raise ValueError("Actual prompts differed from control; do not label this result controlled")
    combined = {
        **result, "benchmark_sample": {**control["benchmark_sample"], "selected_ids": ids, "count": len(ids)},
        "experiment": experiment, "model_inventory": model_inventory,
        "source_asr_model": control.get("source_asr_model"),
        "source_asr_metrics": control.get("source_asr_metrics"),
    }
    combined["metrics"]["peak_memory_gb"] = max(batch.get("peak_memory_gb") or 0 for batch in result["batches"])
    suffix = "" if args.clips == "all" else "-pilot"
    output = DATA / f"turbo-qwen{args.model}{suffix}.json"
    output.write_text(json.dumps(combined, ensure_ascii=False, indent=2))
    summary = summarize(combined, ids)
    (DATA / f"qwen{args.model}{suffix}-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({key: value for key, value in summary.items() if key != "lexical_disagreements"}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
