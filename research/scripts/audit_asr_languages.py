"""Build Greek/English raw-ASR comparison packets against canonical liturgical text.

This is a text-only qualitative audit, not a reference transcript or WER test.
The printed service text can differ from what was actually sung or spoken.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
sys.path.insert(0, str(PROJECT))
from liturgy_lab.align import normalize
from liturgy_lab.asr import asr_warnings


def script_language(text: str) -> str:
    greek = len(re.findall(r"[\u0370-\u03ff\u1f00-\u1fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if greek and latin and min(greek, latin) / (greek + latin) >= 0.15:
        return "Greek + Latin script"
    if greek > latin:
        return "Greek script"
    if latin:
        return "Latin script (not necessarily English)"
    return "Other script / no letters"


CASES = [
    {"id": "orthros_english_hymn", "start": 1850, "end": 1890, "stratum": "English chant",
     "service": "matins", "needles": ["εκ νεοτητος μου πολλα"],
     "note": "The earlier Divine-Liturgy-only reference omitted this Matins hymn. Missing reference coverage must not be counted as an ASR error."},
    {"id": "orthros_greek_hymn", "start": 1950, "end": 1980, "stratum": "Greek chant",
     "service": "matins", "needles": ["οι μισουντες σιων"],
     "note": "Original Turbo has forms resembling 'Σκούντες Ιόνες κύνθητε'; canonical text reads 'Οἱ μισοῦντες Σιών, αἰσχύνθητε'. These differences extend beyond accent conventions; audio review is required to establish the spoken words."},
    {"id": "opening_blessing", "start": 4410, "end": 4440, "stratum": "Greek priest speech",
     "service": "liturgy", "needles": ["ευλογημενη η βασιλεια", "εν ειρηνη του κυριου δεηθωμεν", "υπερ της ανωθεν ειρηνης"],
     "note": "The prayer remains recognizable despite spelling and word-boundary differences. Compare canonical 'νῦν καὶ ἀεὶ καὶ εἰς' with the original Turbo's compressed 'νυν και αϊκέης'."},
    {"id": "great_litany", "start": 4440, "end": 4470, "stratum": "Greek priest speech",
     "service": "liturgy", "needles": ["ειρηνης του συμπαντος", "αγιου οικου τουτου"],
     "note": "Original Turbo's 'σήμαντος κόσμα εφταθίας' differs from 'σύμπαντος κόσμου, εὐσταθείας'. A successful section match can coexist with visibly degraded Greek words."},
    {"id": "small_litany_doxology", "start": 4680, "end": 4710, "stratum": "Greek priest speech / transition",
     "service": "liturgy", "needles": ["οτι σον το κρατος"],
     "note": "Recurring doxologies occur in several services. Recognition of their words does not establish which occurrence is being performed."},
    {"id": "english_feast_hymn", "start": 4710, "end": 4740, "stratum": "English chant",
     "service": "liturgy", "needles": ["εκ καρπου της κοιλιας σου", "σωσον ημας υιε θεου"],
     "note": "Feast-specific antiphon material was absent from the original September 30 reference. The updated same-feast reference reduces that coverage mismatch; it is still from a different year."},
    {"id": "english_anaphora", "start": 6300, "end": 6360, "stratum": "English priest speech",
     "service": "liturgy", "needles": ["πιετε εξ αυτου παντες"],
     "note": "Compare recognizable English sacramental wording with the bilingual canonical text. Translation variants such as 'forgiveness' versus 'remission' are not automatically ASR errors."},
    {"id": "late_artifacts", "start": 7200, "end": 7290, "stratum": "Chant / possible low-information audio",
     "service": None, "needles": [],
     "note": "Inspect repeated tokens, subtitle-credit boilerplate, language changes, or omissions. These are warning signals; their presence or absence does not by itself measure accuracy."},
]


def main() -> None:
    reference = json.loads((DATA / "reference-MIxJvLfaynY.json").read_text())
    files = {"turbo_original_full": DATA / "turbo-full.json"}
    files.update({name: DATA / f"asr-compare-{name}.json" for name in ["small", "turbo", "large-v3"]})
    models = {name: json.loads(path.read_text()) for name, path in files.items() if path.exists()}
    cases = []
    for case in CASES:
        units = []
        for needle in case["needles"]:
            matching = [unit for unit in reference["units"] if unit.get("service_id") == case["service"]
                        and normalize(needle) in normalize(unit.get("greek", ""))]
            if matching:
                units.append(matching[0])
        transcripts = {}
        for name, model in models.items():
            rows = [{key: row[key] for key in ["id", "start", "end", "text", "language"] if key in row}
                    for row in model["segments"] if row["end"] > case["start"] and row["start"] < case["end"]]
            intervals = model.get("intervals") or [{"start": model.get("start", 0), "end": model.get("end", 0)}]
            fully_sampled = any(item["start"] <= case["start"] and item["end"] >= case["end"] for item in intervals)
            transcripts[name] = {"rows": rows, "text": " ".join(row["text"] for row in rows),
                                 "fully_sampled": fully_sampled,
                                 "note": "Rows overlap the interval and can include boundary words. Empty/partial coverage must not be interpreted as a recognition failure."}
        cases.append({**case, "canonical_units": units, "transcripts": transcripts})
    diagnostics = {}
    for name, model in models.items():
        rows = model["segments"]
        diagnostics[name] = {
            "file": files[name].name, "model": model.get("model"), "metrics": model.get("metrics"),
            "segment_count": len(rows), "script_counts": dict(Counter(script_language(row["text"]) for row in rows)),
            "segments_with_warning_signals": sum(bool(asr_warnings(row["text"])) for row in rows),
            "warning_signal_counts": dict(Counter(warning for row in rows for warning in asr_warnings(row["text"]))),
            "note": "Counts depend on segmentation and audio coverage. They are diagnostics, not accuracy or error rates; the full recording and 24-minute samples have different denominators.",
        }
    output = {
        "audit_type": "qualitative_text_only_no_audio_ground_truth",
        "recording_id": "MIxJvLfaynY", "reference_id": reference["reference_id"],
        "reference_file": "reference-MIxJvLfaynY.json", "reference_selection": reference.get("selection"),
        "method": "Purposive language-stratified cases: Greek/English chant and priest speech, recurring replies and artifact-prone audio. Raw model text is preserved.",
        "limits": ["No audio was listened to or independently transcribed for this audit.",
                   "Canonical liturgical text is not an audio ground-truth transcript; local variants, omissions, language changes and translations are possible.",
                   "The same-feast reference is a later-year substitute. Date-specific readings and hymns need manual verification.",
                   "No WER, CER, accuracy ranking or calibrated confidence is claimed.",
                   "Polytonic versus monotonic accents and punctuation should be separated from missing, merged or substituted words.",
                   "An LLM or progression tracker can locate a passage without fixing the raw Greek transcription."],
        "diagnostics": diagnostics, "cases": cases,
    }
    path = DATA / "asr-language-audit.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Wrote {path.name}: {len(cases)} cases; models: {', '.join(models)}")


if __name__ == "__main__":
    main()
