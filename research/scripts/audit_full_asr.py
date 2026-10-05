#!/usr/bin/env python3
"""Compare complete Turbo/Large-v3 outputs on fixed bins, without accuracy claims."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from liturgy_lab.align import ALIGNMENT_VERSION, detect_liturgy_start
from scripts.audit_asr_models import time_metrics, total_metrics

PROBES = [
    (1900, 2010, "Greek chant / language detection", "Large-v3 emits Latin-letter Greek at 1950s while Turbo emits damaged Greek script. Neither establishes accurate words; the forced-Greek retry remains a separate selected experiment."),
    (4395, 4500, "Liturgy opening", "Both recover the opening. Large-v3 improves σύμπαντος κόσμου but worsens the next petition's wording around μετὰ πίστεως εὐλαβείας; gains are mixed."),
    (4860, 4960, "Little / Small Entrance", "Automatic Large-v3 repeats unrelated-looking Greek phrasing and then emits Alleluia; Turbo also fails to recover the entrance phrase here. No automatic entrance location should be inferred from the later forced-Greek retry."),
    (5040, 5190, "Trisagion", "Both yield enough chronological text for some Trisagion associations, but errors remain. Large-v3 emits English-looking words where Turbo emits Latin-letter Greek, then Άγιος η Σύνος instead of the canonical Ἅγιος Ἰσχυρός."),
    (6000, 6090, "Doxology and Kiss of Peace", "Large-v3 emits additional fragments where Turbo has omissions, including Through the night; added text does not demonstrate correct recognition."),
    (7455, 7548, "Closing address", "The closing address is outside the canonical service text. Both remain unassociated; theological word overlap must not be treated as a service location."),
]


def main():
    data = ROOT / "data"
    reference = json.loads((data / "reference-MIxJvLfaynY.json").read_text())
    payloads = {name: json.loads((data / f"{name}-full-sequence.json").read_text()) for name in ("turbo", "large-v3")}
    if any(p.get("reference_id") != reference["reference_id"] or p["alignment"].get("version") != ALIGNMENT_VERSION for p in payloads.values()):
        raise ValueError("Both runs must use the current matcher and identical reference")
    if len({p["end"] for p in payloads.values()}) != 1 or any(p["start"] != 0 for p in payloads.values()):
        raise ValueError("Full runs must have identical audio boundaries")
    duration = next(iter(payloads.values()))["end"]
    bins = [(float(t), min(duration, t + 30.0)) for t in range(0, int(duration) + 1, 30)]
    models = {}
    for name, payload in payloads.items():
        rows = payload["segments"]
        chunk_language = {(float(c["start"]), float(c["end"])): c.get("language") for c in payload["chunks"]}
        timed = [{"start": a, "end": b, "detected_language": chunk_language.get((a, b), "missing"),
                  "time_metrics": time_metrics(rows, a, b)} for a, b in bins]
        associated = [r for r in rows if r["match"]["status"] == "matched"]
        section_ids = {r["match"]["section_id"] for r in associated}
        models[name] = {"model": payload["model"], "asr_runtime": payload["metrics"],
                        "aligned_file": f"data/{name}-full-sequence.json", "totals": total_metrics(timed), "bins": timed,
                        "opening_detection": detect_liturgy_start(rows),
                        "chunk_languages": dict(Counter(c.get("language") for c in payload["chunks"])),
                        "segment_counts_for_diagnostics_only": dict(Counter(r["match"]["status"] for r in rows)),
                        "sections_with_associations": [{"id": s["id"], "title": s["title"], "service_id": s.get("service_id")} for s in reference["sections"] if s["id"] in section_ids],
                        "language_strata_own_detected_bins": {lang: total_metrics([b for b in timed if b["detected_language"] == lang]) for lang in sorted({b["detected_language"] for b in timed})},
                        "closing_address_associated_seconds": time_metrics(rows, 7455, 7548)["sequence_associated_speech_seconds"],
                        "post_7455_associated_segments": sum(r["start"] >= 7455 for r in associated)}
    for name, result in models.items():
        paired = []
        for i, row in enumerate(result["bins"]):
            labels = {m["bins"][i]["detected_language"] for m in models.values()}
            paired.append({**row, "consensus_language": next(iter(labels)) if len(labels) == 1 else "model_language_disagreement"})
        result["language_strata_paired_consensus_bins"] = {lang: total_metrics([b for b in paired if b["consensus_language"] == lang]) for lang in sorted({b["consensus_language"] for b in paired})}
    probes = []
    for a, b, label, note in PROBES:
        per_model = {}
        for name, payload in payloads.items():
            selected = [r for r in payload["segments"] if r["start"] < b and r["end"] > a]
            per_model[name] = {"time_metrics": time_metrics(selected, a, b),
                               "raw_segments_with_separate_predictions": [{k: r.get(k) for k in ("id", "start", "end", "text", "language", "match", "sequence", "asr_warnings")} for r in selected]}
        probes.append({"start": a, "end": b, "label": label, "transcript_review_note": note, "models": per_model})
    result = {"recording_id": "MIxJvLfaynY", "reference_id": reference["reference_id"], "alignment_version": ALIGNMENT_VERSION,
              "design": "Complete identical 7667.879-second recording; automatic language detection on independent 30-second ASR chunks; identical frozen reference and full-context sequence aligner.",
              "comparison_basis": "Fixed 30-second bins and timestamp unions, not number of ASR segments, because models segment speech differently.",
              "models": models, "qualitative_probes": probes,
              "limitations": ["No human listening transcript or verified service timings: these are association-coverage and reference-similarity proxies, not WER, CER or accuracy.",
                              "ASR output timestamps do not independently measure speech duration, silence, or omissions.",
                              "A higher segment count can result from more fragmentation; associated seconds and sections are more useful than raw counts, but remain heuristic.",
                              "Greek-script output is not evidence of correct Greek; Latin output can be transliterated Greek or English.",
                              "Both models can agree on wrong words or language; paired consensus language strata are not human-labelled audio.",
                              "The reference retains the explicitly labelled 2026 same-feast substitute for the 2025 recording.",
                              "Full-run wall times include model load and compilation and can differ from the 24-minute controlled sample due to execution conditions.",
                              "The forced-Greek supplemental retry is deliberately excluded from this automatic-language comparison."]}
    (data / "full-asr-comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({name: {"asr_runtime": m["asr_runtime"], "totals": m["totals"], "section_count": len(m["sections_with_associations"]), "opening": m["opening_detection"].get("start"), "post_address_matches": m["post_7455_associated_segments"], "chunk_languages": m["chunk_languages"]} for name, m in models.items()}, indent=2))


if __name__ == "__main__":
    main()
