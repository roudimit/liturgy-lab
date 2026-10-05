#!/usr/bin/env python3
"""Compare matched-window ASR artifacts on fixed time bins, without accuracy claims."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from liturgy_lab.align import ALIGNMENT_VERSION, ReferenceIndex, align_sequence, detect_liturgy_start
from liturgy_lab.asr import asr_warnings

QUALITATIVE_STARTS = [1200, 1800, 1950, 2700, 3600, 4410, 4680, 4860, 5040, 6000]
QUALITATIVE_NOTES = {
    1200: "All three distort Greek litany wording. Large-v3 emits subtitle-artifact text and less recognizable text in the opening portion. This is a raw-output observation, not measured accuracy.",
    1800: "Small produces a long run of Latin diacritics and repeated syllables. Turbo and Large-v3 retain recognizable prayer fragments but also emit AUTHORWAVE; Large-v3 additionally renders chant in Latin letters.",
    1950: "Small has repeated foreign-script or diacritic fragments. Turbo emits damaged Greek; Large-v3 renders much of the Greek-sounding chant in Latin letters. Script choice alone does not establish which words were heard correctly.",
    2700: "Large-v3 produces more conventionally spaced Greek doxology text than Turbo's unspaced uppercase output, with remaining substitutions. Better-looking typography is not audio-grounded accuracy.",
    3600: "Small loops Latin diacritics and Telugu-script characters during chant. Turbo and Large-v3 preserve more recognizable Greek phrases; Large-v3 also adds AUTHORWAVE and Latin transliteration. All retain defects.",
    4410: "Large-v3 improves one recognizable phrase toward the reference, σύμπαντος κόσμου, but worsens another phrase corresponding to μετὰ πίστεως εὐλαβείας. Gains are mixed within the same window.",
    4680: "The English antiphon portions are similar across models. Greek litany words remain damaged; Large-v3 emits fewer intervening phrases. Missing text and lexical similarity must be examined separately.",
    4860: "Small and Large-v3 show long repeated phrase loops; Large-v3 repeats a phrase about ευκαιρία του Θεού. Turbo avoids that particular long loop but its Greek is also semantically damaged.",
    5040: "Turbo emits Latin-script Greek such as To Kyrieu Dei Thomen. Large-v3 emits English-looking words in that place and later Άγιος η Σύνος where the reference has Ἅγιος Ἰσχυρός. Neither transcript should be silently replaced by canonical text.",
    6000: "All three produce mixed or broken renderings around the doxology and Kiss of Peace. Large-v3 adds an English-looking phrase beginning Through the night; Turbo omits part of the interval. A human listening audit is needed to adjudicate words and omissions.",
}


def script_counts(text: str) -> dict:
    greek = latin = other = 0
    for char in text:
        if not char.isalpha():
            continue
        name = unicodedata.name(char, "")
        if "GREEK" in name:
            greek += 1
        elif "LATIN" in name:
            latin += 1
        else:
            other += 1
    return {"greek_letters": greek, "latin_letters": latin, "other_letters": other}


def time_metrics(rows: list[dict], start: float, end: float) -> dict:
    """Integrate over timestamp unions so overlapping/fragmented segments do not inflate seconds."""
    clipped = [(max(start, float(r["start"])), min(end, float(r["end"])), r)
               for r in rows if float(r["start"]) < end and float(r["end"]) > start]
    boundaries = sorted({start, end, *(t for a, b, _ in clipped for t in (a, b))})
    speech = matched = warned = weighted = high_evidence = 0.0
    for a, b in zip(boundaries, boundaries[1:]):
        active = [r for left, right, r in clipped if left < b and right > a]
        if not active:
            continue
        dt = b - a
        speech += dt
        if any((r.get("match") or {}).get("status") == "matched" for r in active):
            matched += dt
        if any(asr_warnings(r.get("text", "")) for r in active):
            warned += dt
        support = max((max((c.get("score", 0) for c in r.get("candidates", [])), default=0) for r in active), default=0)
        weighted += dt * support
        if support >= 0.85:
            high_evidence += dt
    scripts = Counter()
    for a, b, row in clipped:
        fraction = (b - a) / max(1e-8, float(row["end"]) - float(row["start"]))
        for key, count in script_counts(row.get("text", "")).items():
            scripts[key] += count * fraction
    result = {"audio_seconds": end - start, "asr_timestamped_speech_seconds": speech,
              "sequence_associated_speech_seconds": matched, "warning_affected_speech_seconds": warned,
              "high_reference_evidence_speech_seconds": high_evidence,
              "reference_evidence_score_seconds": weighted, **scripts}
    return {key: round(value, 5) for key, value in result.items()}


def total_metrics(bins: list[dict]) -> dict:
    totals = Counter()
    for row in bins:
        totals.update(row["time_metrics"])
    speech = totals["asr_timestamped_speech_seconds"]
    audio = totals["audio_seconds"]
    letters = totals["greek_letters"] + totals["latin_letters"] + totals["other_letters"]
    return {**{key: round(value, 3) for key, value in totals.items()},
            "sequence_associated_fraction_of_sampled_audio": round(totals["sequence_associated_speech_seconds"] / audio, 4) if audio else None,
            "sequence_associated_fraction_of_asr_speech": round(totals["sequence_associated_speech_seconds"] / speech, 4) if speech else None,
            "mean_reference_evidence_per_asr_speech_second": round(totals["reference_evidence_score_seconds"] / speech, 4) if speech else None,
            "emitted_greek_letter_fraction": round(totals["greek_letters"] / letters, 4) if letters else None,
            "emitted_latin_letter_fraction": round(totals["latin_letters"] / letters, 4) if letters else None,
            "fixed_30s_bins": len(bins)}


def window_signature(payload: dict) -> list[tuple]:
    return [(float(w["start"]), float(w["end"])) for w in payload["intervals"]]


def audit_model(name: str, payload: dict, reference: dict, *, data: Path) -> dict:
    windows = window_signature(payload)
    raw = []
    for original in payload["segments"]:
        row = {**original, "asr_warnings": asr_warnings(original.get("text", ""))}
        row["clip_id"] = next((str(start) for start, end in windows if start <= row["start"] < end), "outside-selected-windows")
        raw.append(row)
    started = time.perf_counter()
    aligned = align_sequence(raw, reference)
    elapsed = time.perf_counter() - started
    output = data / f"asr-compare-{name}-sequence.json"
    output.write_text(json.dumps({**payload, "segments": aligned, "reference_id": reference["reference_id"],
                                 "source_asr_file": f"data/asr-compare-{name}.json",
                                 "alignment": {"method": "sequence", "version": ALIGNMENT_VERSION, "explicit_clip_boundaries": True,
                                               "cpu_seconds": elapsed}}, ensure_ascii=False, indent=2) + "\n")
    index = ReferenceIndex(reference)
    chunk_map = {(float(c["start"]), float(c["end"])): c for c in payload["chunks"]}
    bins = []
    for start, end in windows:
        t = start
        while t < end:
            stop = min(end, t + 30)
            selected = [r for r in aligned if r["start"] < stop and r["end"] > t]
            text = " ".join(r["text"] for r in selected)
            candidates = index.retrieve(text, top_k=2)
            metrics = time_metrics(aligned, t, stop)
            bins.append({"start": t, "end": stop, "window_start": start,
                         "detected_language": chunk_map.get((t, stop), {}).get("language", "missing"),
                         "asr_inference_seconds": chunk_map.get((t, stop), {}).get("seconds"),
                         "raw_asr_text": text, "time_metrics": metrics,
                         "top_reference_for_concatenated_chunk": candidates,
                         "warning_texts": [r["text"] for r in selected if asr_warnings(r["text"])],
                         "status_counts_for_diagnostics_only": dict(Counter(r["match"]["status"] for r in selected))})
            t = stop
    totals = total_metrics(bins)
    totals["warning_affected_bins"] = sum(bool(b["warning_texts"]) for b in bins)
    return {"model": payload["model"], "aligned_artifact": str(output.relative_to(ROOT)),
            "asr_runtime": payload["metrics"], "alignment_cpu_seconds": round(elapsed, 3),
            "detected_chunk_languages": dict(Counter(b["detected_language"] for b in bins)),
            "opening_detection": detect_liturgy_start(raw), "totals": totals, "bins": bins,
            "windows": [{"start": start, "end": end,
                         "totals": total_metrics([b for b in bins if b["window_start"] == start])}
                        for start, end in windows]}


def build_audit(models: dict[str, dict], reference: dict, data: Path, requested: list[str]) -> dict:
    signatures = {name: window_signature(payload) for name, payload in models.items()}
    if not signatures or len({tuple(sig) for sig in signatures.values()}) != 1:
        raise ValueError("Models must contain exactly the same ordered audio windows")
    results = {name: audit_model(name, payload, reference, data=data) for name, payload in models.items()}
    starts = [(b["start"], b["end"]) for b in next(iter(results.values()))["bins"]]
    consensus = {}
    for i, key in enumerate(starts):
        languages = {result["bins"][i]["detected_language"] for result in results.values()}
        consensus[key] = next(iter(languages)) if len(languages) == 1 else "model_language_disagreement"
    for result in results.values():
        result["consensus_language_strata"] = {
            lang: total_metrics([b for b in result["bins"] if consensus[(b["start"], b["end"])] == lang])
            for lang in sorted(set(consensus.values()))}
    missing = [name for name in requested if name not in results]
    qualitative = []
    for start in QUALITATIVE_STARTS:
        blocks = {}
        for name, result in results.items():
            bins = [b for b in result["bins"] if b["window_start"] == start]
            candidates = [c for b in bins for c in b["top_reference_for_concatenated_chunk"]]
            dedup = {c["unit_id"]: c for c in candidates}
            blocks[name] = {"raw_asr_text": " ".join(b["raw_asr_text"] for b in bins),
                            "predicted_reference_excerpts_separate_from_asr": list(dedup.values())[:6],
                            "detected_chunk_languages": [b["detected_language"] for b in bins]}
        qualitative.append({"start": start, "end": start + 90, "label": "Greek-rich or mixed exploratory probe; language not human-labelled",
                            "raw_text_review_note": QUALITATIVE_NOTES[start],
                            "review_basis": "Qualitative inspection of emitted transcripts against reference candidates; no human listening transcript or word error measurement.",
                            "models": blocks})
    return {"schema_version": 1, "alignment_version": ALIGNMENT_VERSION, "complete": not missing, "models_pending": missing,
            "reference_id": reference["reference_id"], "reference_path": "data/reference-MIxJvLfaynY.json",
            "comparison_design": "Same 16 × 90-second purposively selected audio windows, same 30-second ASR chunking, same combined reference and sequence algorithm; explicit independent-window resets.",
            "metric_meanings": {"sequence_associated_speech_seconds": "Union of model segment timestamps accepted by sequence alignment, clipped to each fixed 30-second bin.",
                                "asr_timestamped_speech_seconds": "Union of ASR output timestamps, not independent voice-activity or true speech duration.",
                                "reference_evidence": "Lexical/phonetic similarity to candidate reference passages; not ASR correctness.",
                                "script_fractions": "Share of emitted alphabetic characters in Greek or Latin script; Latin includes English and transliterated Greek.",
                                "consensus_language_strata": "Fixed paired bins where all included models emit the same language label; disagreement is separate. No audio-language ground truth.",
                                "warnings": "Recomputed using current asr_warnings(text); suspected subtitle/promotion artifacts, not manually verified hallucinations."},
            "limitations": ["No human transcript or verified word timestamps: WER, CER, precision, and accuracy cannot be inferred.",
                            "Accepted-duration proxies still depend on ASR timestamp quality and the heuristic aligner.",
                            "The conservative service guard depends on recognizing the Liturgy opening or distinctive service-specific text. A model that misses the opening can lose associations across several short sampled windows; this is an end-to-end pipeline effect, not a word-error estimate.",
                            "Reference includes labelled substitute-date material for the original 2025 recording.",
                            "Language strata use model consensus and can share model errors; compare them together with emitted script rates.",
                            "Consensus-Greek bins can exclude difficult Greek audio when a model labels it Latin or another language; they are not a human-labelled Greek test set.",
                            "Long concatenated chunks can span multiple reference units, reducing single-unit retrieval scores even when words are correct.",
                            "Runtime includes model load/compilation as recorded; all models were run locally with the same settings."],
            "models": results, "qualitative_greek_or_mixed_probes": qualitative}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=["small", "turbo", "large-v3"])
    parser.add_argument("--reference", type=Path, default=ROOT / "data/reference-MIxJvLfaynY.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/asr-model-comparison.json")
    args = parser.parse_args()
    data = ROOT / "data"
    models = {name: json.loads((data / f"asr-compare-{name}.json").read_text()) for name in args.models if (data / f"asr-compare-{name}.json").exists()}
    report = build_audit(models, json.loads(args.reference.read_text()), data, args.models)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"complete": report["complete"], "pending": report["models_pending"], "models": {name: {"runtime": result["asr_runtime"], "totals": result["totals"], "language_strata": result["consensus_language_strata"]} for name, result in report["models"].items()}}, indent=2))


if __name__ == "__main__":
    main()
