#!/usr/bin/env python3
"""Reproduce CPU-only chronological alignment and report association coverage."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from liturgy_lab.align import ALIGNMENT_VERSION, align_sequence, detect_liturgy_start


def summarize(rows: list[dict], reference: dict, elapsed: float) -> dict:
    languages = defaultdict(list)
    for row in rows:
        languages[row.get("language", "unlabelled")].append(row)

    def counts(group: list[dict], field: str) -> dict:
        accepted = [s for s in group if (s.get(field) or {}).get("status") == "matched"]
        return {"segments": len(group), "status_counts": dict(Counter((s.get(field) or {}).get("status", "missing") for s in group)),
                "accepted_seconds": round(sum(max(0, s.get("end", 0) - s.get("start", 0)) for s in accepted), 2),
                "distinct_units": len({s[field]["unit_id"] for s in accepted}),
                "distinct_sections": len({s[field]["section_id"] for s in accepted})}
    accepted = [s for s in rows if s["match"]["status"] == "matched"]
    sections = []
    for section in reference.get("sections", []):
        matches = [s for s in accepted if s["match"]["section_id"] == section["id"]]
        if matches:
            sections.append({"section_id": section["id"], "title": section["title"], "service_id": section.get("service_id"),
                             "first_match_seconds": min(s["start"] for s in matches), "segments": len(matches)})
    return {"alignment_version": ALIGNMENT_VERSION, "description": "Model association coverage, not human-verified transcription or alignment accuracy.",
            "method": "Beam/Viterbi chronological tracking with UNKNOWN, forward skips, and bounded reversal",
            "elapsed_seconds": round(elapsed, 3), "reference_units": len(reference["units"]),
            "reference_sections": len(reference["sections"]), "reference_services": reference.get("services", []),
            "independent_lexical": counts(rows, "lexical_match"), "sequence": counts(rows, "match"),
            "language_breakdown": {lang: {"independent_lexical": counts(group, "lexical_match"), "sequence": counts(group, "match")}
                                   for lang, group in sorted(languages.items())},
            "service_breakdown": dict(Counter(s["match"].get("service_id", "unknown") for s in accepted)),
            "opening_detection": detect_liturgy_start(rows), "sections_with_predictions": sections,
            "limitations": ["ASR labels determine language grouping; code-switched segments may be mislabelled.",
                            "Dates and reference substitutions are inherited from the reference metadata.",
                            "Sequence support can propagate an incorrect anchor; all predictions remain reviewable.",
                            "Short repeated replies abstain when their exact occurrence is ambiguous."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asr", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--max-reverse-units", default=3, type=int)
    args = parser.parse_args()
    asr = json.loads(args.asr.read_text())
    reference = json.loads(args.reference.read_text())
    started = time.perf_counter()
    rows = align_sequence(asr["segments"], reference, max_reverse_units=args.max_reverse_units,
                          progress_callback=lambda stage, done, total: print(f"{stage}: {done}/{total}", flush=True))
    report = summarize(rows, reference, time.perf_counter() - started)
    result = {**asr, "segments": rows, "source_asr_file": str(args.asr), "reference_id": reference.get("reference_id"), "alignment": {"method": "sequence", "version": ALIGNMENT_VERSION, "report_path": str(args.report),
                                                        "reference_path": str(args.reference), "coverage": report["sequence"]}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("elapsed_seconds", "independent_lexical", "sequence", "service_breakdown", "language_breakdown")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
