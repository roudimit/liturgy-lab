"""Summarize controlled saved-prompt replays without claiming alignment accuracy."""

import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT))
from benchmark_llm import summarize


def hashes(result):
    return [hashlib.sha256(json.dumps(batch["messages"], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            for batch in result["batches"]]


def main():
    control = json.loads((DATA / "turbo-qwen4b.json").read_text())
    selected = control["benchmark_sample"]["selected_ids"]
    entries = []
    disagreements = {}
    baseline = {str(row["id"]): row for row in control["segments"]}
    for name in ["17b", "4b", "30b", "35b"]:
        path = DATA / f"turbo-qwen{name}.json"
        if not path.exists():
            continue
        result = json.loads(path.read_text())
        if result["benchmark_sample"]["selected_ids"] != selected or hashes(result) != hashes(control):
            raise ValueError(f"{path.name} does not use identical control rows/messages")
        summary = summarize(result, selected)
        summary.pop("lexical_disagreements", None)
        summary["file"] = path.name
        summary["peak_memory_gb"] = max((batch.get("peak_memory_gb") or 0 for batch in result["batches"]), default=0)
        summary["exact_control_messages"] = True
        summary["revision"] = (result.get("model_inventory") or {}).get("revision")
        entries.append(summary)
        changed = []
        for row in result["segments"]:
            sid = str(row["id"])
            if sid not in selected:
                continue
            new, old = row["llm_match"], baseline[sid]["llm_match"]
            if (new["unit_id"], new["status"]) != (old["unit_id"], old["status"]):
                changed.append({"segment_id": row["id"], "start": row["start"], "text": row["text"],
                                "control_4b": old, "model_result": new})
        disagreements[name] = changed
    output = {
        "sample_size": len(selected), "model_inference_rows": 47,
        "experimental_scope": "Identical saved messages and ASR/candidates; model tokenizer/chat-template differs. Original September 30 reference retained for controlled comparison.",
        "limits": ["No human audio transcript or alignment labels; counts are system decisions, not accuracy.",
                   "Temperature zero, thinking disabled, 1400 generated-token limit per batch.",
                   "Peak memory is MLX reported process memory, not whole-Mac memory; timings include model load but exclude downloads.",
                   "Original Matins coverage is absent from this control reference; new combined-reference tests are separate."],
        "models": entries, "disagreements_vs_4b": disagreements,
    }
    (DATA / "large-llm-comparison.json").write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps([{key: row[key] for key in ["model", "selected_status_counts", "raw_proposal_status_counts", "invalid_decision_count", "peak_memory_gb"]}
                      | {"total_seconds": row["metrics"]["total_seconds"]} for row in entries], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
