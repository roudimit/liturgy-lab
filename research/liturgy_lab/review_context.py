"""Bind human annotations to an immutable view of a model prediction."""

import hashlib
import json


def displayed_match(segment: dict, alignment: str):
    """Use the same decision as the viewer, including an explicit no-prediction."""
    primary = segment.get("match") or {}
    if alignment == "llm":
        match = segment.get("llm_match")
    elif alignment == "sequence":
        match = segment.get("sequence_match") or (primary if primary.get("method") == "sequence" else None)
    else:
        match = segment.get("lexical_match") or (primary if primary.get("method") != "sequence" else None)
    return None if (match or {}).get("status") == "not_run" else match


def reference_for_run(experiment: dict, run: dict) -> dict:
    return experiment.get("references", {}).get(run.get("reference_id")) or experiment.get("reference") or {}


def prediction_context(recording_id: str, run: dict, segment: dict, alignment: str,
                       reference: dict, units: dict | None = None) -> dict:
    """Fingerprint what was reviewed, independent of mutable file/run names.

    Only the server computes this opaque token. Rebuilding in place invalidates
    it if the reference, algorithm version, audio/text, or displayed decision
    changes. Canonical text participates too, even if a ref ID is reused by hand.
    """
    match = displayed_match(segment, alignment)
    unit = (units or {str(u["id"]): u for u in reference.get("units", [])}).get(str((match or {}).get("unit_id")))
    version = (segment.get("sequence") or {}).get("version", (run.get("alignment") or {}).get("version")) if alignment == "sequence" else None
    payload = {
        "schema_version": 1, "recording_id": recording_id, "run_id": str(run["id"]),
        "segment_id": str(segment["id"]), "alignment": alignment,
        "reference_id": run.get("reference_id") or reference.get("reference_id") or reference.get("source_sha256"),
        "alignment_version": version,
        "asr_model": run.get("model"),
        "audio_and_transcript": {k: segment.get(k) for k in ("start", "end", "text", "language")},
        "prediction": match,
        "reference_unit": {k: unit.get(k) for k in ("id", "section_id", "greek", "english")} if unit else None,
    }
    if alignment == "llm":
        payload["llm_context"] = {"model": run.get("llm_model"),
                                  "candidate_tracker_versions": run.get("candidate_tracker_versions"),
                                  "guard_policy": (run.get("llm_metrics") or {}).get("guard_policy")}
    if alignment == "sequence":
        payload["supplemental_evidence"] = segment.get("supplemental_evidence")
        payload["run_alignment"] = {k: (run.get("alignment") or {}).get(k) for k in ("method", "version")}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return {"prediction_fingerprint": fingerprint, "reference_id": payload["reference_id"],
            "alignment_version": version, "reviewed_prediction": match,
            "reviewed_audio_and_transcript": payload["audio_and_transcript"]}


def session_with_review_context(experiment: dict, recording_id: str) -> dict:
    """Attach ephemeral tokens to the API response; never rewrite session files."""
    for run in experiment.get("runs", []):
        reference = reference_for_run(experiment, run)
        units = {str(u["id"]): u for u in reference.get("units", [])}
        for segment in run.get("segments", []):
            alignments = ["lexical"]
            if displayed_match(segment, "sequence") is not None:
                alignments.append("sequence")
            if displayed_match(segment, "llm") is not None:
                alignments.append("llm")
            segment["review_fingerprints"] = {a: prediction_context(recording_id, run, segment, a, reference, units)["prediction_fingerprint"] for a in alignments}
    experiment["review_context_schema_version"] = 1
    return experiment

