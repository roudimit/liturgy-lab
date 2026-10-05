"""LLM suggestions with combined-service references and explicit sequence priors.

This differs from the historical model-only replay: reference coverage, candidate
retrieval and tracking context changed. It is an improved-pipeline experiment,
not proof that a larger model alone produced any observed difference.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
WORK = PROJECT / "work"
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("HF_HOME", str(WORK / "cache/huggingface"))

from liturgy_lab.llm import run_llm_alignment


def prepare(source: dict, reference: dict, starts: list[float]) -> tuple[list[dict], dict]:
    if source.get("reference_id") != reference["reference_id"]:
        raise ValueError("Sequence output and canonical reference fingerprints differ")
    units = {unit["id"]: unit for unit in reference["units"]}
    rows = [{key: value for key, value in row.items() if key not in {"llm_match", "llm_proposal"}} for row in source["segments"]]
    selected, clips = [], []
    used = set()
    for number, start in enumerate(starts):
        first = next(i for i, row in enumerate(rows) if row["start"] >= start)
        clip = rows[first:first + 6]
        if len(clip) != 6 or used.intersection(str(row["id"]) for row in clip):
            raise ValueError("Clip is incomplete or overlaps another clip")
        ids = [str(row["id"]) for row in clip]
        used.update(ids)
        selected.extend(ids)
        clip_id = f"combined-{number + 1:02d}"
        for position, row in enumerate(clip, first):
            row["llm_clip_id"] = clip_id
            prior = row.get("sequence_match", row.get("match", {}))
            context = {"prior": {key: prior.get(key) for key in ["unit_id", "index", "section_title", "service_id", "status", "score"]},
                       "prior_note": "Unverified sequence-tracker proposal, not human ground truth", "nearby_anchors": []}
            # Only nearby rows in this recording can supply context. Include
            # timestamps so a later or skipped passage is never presented as
            # an immediately adjacent utterance.
            for direction in (-1, 1):
                scan = range(position + direction, len(rows) if direction == 1 else -1, direction)
                for index in scan:
                    neighbor = rows[index]
                    if abs(neighbor["start"] - row["start"]) > 90:
                        break
                    match = neighbor.get("sequence_match", neighbor.get("match", {}))
                    unit = units.get(match.get("unit_id"))
                    if match.get("status") == "matched" and match.get("score", 0) >= 0.90 and unit:
                        context["nearby_anchors"].append({
                            "segment_id": str(neighbor["id"]), "start_seconds": neighbor["start"],
                            "asr_text": neighbor["text"], "unit_id": unit["id"], "section": unit["section_title"],
                            "greek": unit["greek"][:450], "english": unit["english"][:450],
                            "note": "Algorithmic textual anchor; not independently verified",
                        })
                        break
            row["llm_context"] = context
            row["llm_evidence_required"] = True
        clips.append({"clip_id": clip_id, "start": clip[0]["start"], "end": clip[-1]["end"], "segment_ids": ids})
    return rows, {"selected_ids": selected, "count": len(selected), "clips": clips,
                  "selection_note": "Purposive Matins, Greek priest speech, chant/Trisagion and late-address clips; not random or human annotated."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="mlx-community/Qwen3.6-35B-A3B-4bit")
    parser.add_argument("--source", type=Path, default=DATA / "turbo-full-sequence.json")
    parser.add_argument("--reference", type=Path, default=DATA / "reference-MIxJvLfaynY.json")
    parser.add_argument("--clip-starts", default="1800,1950,3600,4410,4860,5040,7500")
    parser.add_argument("--output", type=Path, default=DATA / "qwen35b-combined-MIxJvLfaynY.json")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    source = json.loads(args.source.read_text())
    reference = json.loads(args.reference.read_text())
    rows, sample = prepare(source, reference, [float(value) for value in args.clip_starts.split(",")])
    if args.prepare_only:
        print(json.dumps(sample, ensure_ascii=False, indent=2))
        return
    inventory_path = DATA / "large-model-inventory.json"
    inventory = json.loads(inventory_path.read_text()) if inventory_path.exists() else []
    model_inventory = next((row for row in inventory if row["model"] == args.model), None)
    runtime_path = model_inventory["snapshot"] if model_inventory and model_inventory.get("validation") else None
    result = run_llm_alignment(rows, reference, model=args.model, selected_ids=sample["selected_ids"],
                               batch_size=6, max_tokens=1800, max_prompt_tokens=16000,
                               runtime_model_path=runtime_path,
                               progress=lambda message: print(message, flush=True))
    output = {
        **result, "benchmark_sample": sample,
        "reference_id": reference["reference_id"], "recording_id": reference["recording_id"],
        "source_asr_file": Path(source.get("source_asr_file", "turbo-full.json")).name,
        "source_asr_model": source.get("model"), "source_asr_metrics": source.get("metrics"),
        "start": source.get("start"), "end": source.get("end"), "intervals": source.get("intervals"),
        "experiment": {"type": "combined_reference_with_sequence_context",
                       "changed_from_historical_control": ["Combined Matins and same-feast Liturgy reference", "New candidate retrieval", "Sequence prior and nearby algorithmic anchors", "Verbatim transcript/reference evidence required with substring validation", "Narrow observed subtitle-credit abstention rule", "1800-token output budget"],
                       "accuracy_note": "No human ground truth. Canonical text is not an audio transcript. LLM judgments and tracking priors remain unverified.",
                       "reference_caveats": reference.get("selection")},
    }
    output["metrics"]["peak_memory_gb"] = max((batch.get("peak_memory_gb") or 0 for batch in result["batches"]), default=0)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps(output["metrics"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
