#!/usr/bin/env python3
"""Audit one complete sequence run using fixed-time coverage and review flags."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from liturgy_lab.align import ALIGNMENT_VERSION, detect_liturgy_start
from scripts.audit_asr_models import time_metrics, total_metrics


def audit(payload, reference, *, address_start=None):
    if payload.get("reference_id") != reference.get("reference_id") or payload.get("alignment", {}).get("version") != ALIGNMENT_VERSION:
        raise ValueError("Reference fingerprint or alignment version does not match")
    rows = payload["segments"]
    matched = [r for r in rows if r["match"]["status"] == "matched"]
    end = float(payload["end"])
    chunk_languages = {(float(c["start"]), float(c["end"])): c.get("language", "missing") for c in payload.get("chunks", [])}
    bins = [{"start": float(t), "end": min(end, t + 30.),
             "detected_language": chunk_languages.get((float(t), min(end, t + 30.)), "missing"),
             "time_metrics": time_metrics(rows, float(t), min(end, t + 30.))}
            for t in range(int(payload.get("start", 0)), int(end) + 1, 30)]
    sections = []
    for section in reference["sections"]:
        group = [r for r in matched if r["match"]["section_id"] == section["id"]]
        if group:
            first = min(group, key=lambda r: r["start"])
            sections.append({"section_id": section["id"], "title": section["title"], "service_id": section.get("service_id"),
                             "first_associated_start": first["start"], "first_raw_text": first["text"],
                             "last_associated_end": max(r["end"] for r in group), "segments": len(group),
                             "associated_seconds": time_metrics(group, 0, end)["sequence_associated_speech_seconds"]})
    sections.sort(key=lambda s: s["first_associated_start"])
    transitions = []
    jumps = []
    for previous, current in zip(matched, matched[1:]):
        if current["match"].get("service_id") != previous["match"].get("service_id"):
            transitions.append({"start": current["start"], "from": previous["match"].get("service_id"),
                                "to": current["match"].get("service_id"), "text": current["text"]})
        delta = current["match"]["unit_index"] - previous["match"]["unit_index"]
        if delta < -3 or delta > 40:
            jumps.append({"previous_start": previous["start"], "start": current["start"], "unit_delta": delta,
                          "previous_section": previous["match"]["section_title"], "section": current["match"]["section_title"],
                          "previous_text": previous["text"], "text": current["text"],
                          "previous_block": previous.get("sequence", {}).get("block"), "block": current.get("sequence", {}).get("block"),
                          "interpretation": "Review flag only; skipped, missing or unrecognized material can cause legitimate jumps."})
    return {"alignment_version": ALIGNMENT_VERSION, "reference_id": reference["reference_id"],
            "reference_services": reference.get("services"), "asr_runtime": payload["metrics"],
            "comparison_basis": "Timestamp unions in fixed 30-second bins; coverage and textual association, not human-verified accuracy.",
            "totals": total_metrics(bins), "bins": bins,
            "own_detected_language_strata": {lang: total_metrics([b for b in bins if b["detected_language"] == lang]) for lang in sorted({b["detected_language"] for b in bins})},
            "status_counts_for_diagnostics_only": dict(Counter(r["match"]["status"] for r in rows)),
            "opening_detection": detect_liturgy_start(rows), "service_transitions": transitions,
            "sections_in_first_association_order": sections, "large_jumps_to_review": jumps,
            "manual_address_probe": None if address_start is None else {"start": address_start, "end": end,
                "selection_basis": "Start chosen from an explicit address/sermon cue in emitted ASR, not independent audio annotation.",
                "metrics": time_metrics(rows, address_start, end),
                "accepted_segments": [{k: r.get(k) for k in ("id", "start", "end", "text", "match")} for r in matched if r["start"] >= address_start]},
            "limitations": ["No human transcript, verified word timings or verified service boundary labels; WER, precision and accuracy cannot be inferred.",
                            "Language is the model's label for each audio chunk. Greek spoken in Latin characters can be labelled English or Latin.",
                            "Reference substitutions and calendar differences are recorded in reference metadata; omitted material can remain unmatched.",
                            "Even a plausible chronological path can contain wrong associations; listed jumps and repeated phrases warrant listening review.",
                            "Long silence and missing ASR both reduce timestamped speech; this audit does not distinguish them."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording", required=True)
    parser.add_argument("--address-start", type=float)
    args = parser.parse_args()
    data = ROOT / "data"
    reference = json.loads((data / f"reference-{args.recording}.json").read_text())
    payload = json.loads((data / f"turbo-full-{args.recording}-sequence.json").read_text())
    result = audit(payload, reference, address_start=args.address_start)
    result["recording_id"] = args.recording
    result["aligned_file"] = f"data/turbo-full-{args.recording}-sequence.json"
    (data / f"full-recording-audit-{args.recording}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"recording_id": args.recording, "totals": result["totals"], "sections": len(result["sections_in_first_association_order"]),
                      "opening": result["opening_detection"], "service_transitions": result["service_transitions"],
                      "review_jumps": len(result["large_jumps_to_review"]),
                      "address_associations": None if result["manual_address_probe"] is None else len(result["manual_address_probe"]["accepted_segments"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
