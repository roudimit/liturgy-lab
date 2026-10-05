"""A loopback-only review UI. Importing this module never loads an ML model."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from .review_context import prediction_context, reference_for_run, session_with_review_context

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REVIEW_LOCK = threading.Lock()
app = FastAPI(title="Liturgy Lab", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recording_id: str | None = Field(default=None, min_length=1, max_length=160)
    run_id: str = Field(min_length=1, max_length=160)
    segment_id: str = Field(min_length=1, max_length=160)
    verdict: Literal["matched", "incorrect", "unknown"]
    alignment: Literal["sequence", "lexical", "llm"] = "lexical"
    reference_transcript: str = Field(default="", max_length=12000)
    prediction_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


def recording_manifest() -> list[dict]:
    manifest = DATA / "recordings.json"
    if not manifest.is_file():
        try:
            source = json.loads((DATA / "source.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            source = {}
        return [{"id": str(source.get("id", "default")), "title": source.get("title", "Original recording"), "session_file": "session.json", "media_file": "video.mp4"}]
    try:
        records = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(records, list) or not records:
            raise ValueError("Expected recording list")
        identifiers = set()
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", record["id"]):
                raise ValueError("Invalid recording identifier")
            if record["id"] in identifiers:
                raise ValueError("Duplicate recording identifier")
            identifiers.add(record["id"])
            for key, suffix in [("session_file", ".json"), ("media_file", ".mp4")]:
                filename = record.get(key, "")
                if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,200}", filename) or not filename.endswith(suffix):
                    raise ValueError("Invalid manifest filename")
        return records
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        raise HTTPException(500, "The recording manifest could not be read.") from exc


def get_recording(recording: str | None = None) -> dict:
    records = recording_manifest()
    result = records[0] if recording is None else next((r for r in records if r["id"] == recording), None)
    if result is None:
        raise HTTPException(404, "This recording is not in the experiment.")
    return result


def read_session(recording: str | None = None) -> dict:
    selected = get_recording(recording)
    try:
        return json.loads((DATA / selected["session_file"]).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(503, "The experiment is still being prepared. Generate data/session.json, then refresh.") from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(500, "The session file could not be read.") from exc


def read_reviews() -> list[dict]:
    try:
        result = json.loads((DATA / "reviews.json").read_text(encoding="utf-8"))
        if not isinstance(result, list):
            raise ValueError("Expected review list")
        return result
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise HTTPException(500, "Saved reviews could not be read; no changes were made.") from exc


@app.middleware("http")
async def local_write_guard(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host', '')}":
            return JSONResponse({"detail": "Cross-origin writes are not allowed."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site writes are not allowed."}, status_code=403)
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            return JSONResponse({"detail": "Use application/json."}, status_code=415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 64000:
                return JSONResponse({"detail": "Review is too large."}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    if request.url.path == "/" or request.url.path.startswith(("/api/", "/static/")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/session")
def session(recording: str | None = None):
    recording_id = get_recording(recording)["id"]
    return session_with_review_context(read_session(recording_id), recording_id)


@app.get("/api/recordings")
def recordings():
    return [{"id": r["id"], "title": r.get("title", r["id"])} for r in recording_manifest()]


@app.get("/api/reviews")
def reviews():
    return {"reviews": read_reviews()}


@app.post("/api/reviews")
def save_review(review: Review):
    recording_id = get_recording(review.recording_id)["id"]
    experiment = read_session(recording_id)
    run = next((r for r in experiment.get("runs", []) if str(r.get("id")) == review.run_id), None)
    segment = next((s for s in (run or {}).get("segments", []) if str(s.get("id")) == review.segment_id), None)
    if segment is None:
        raise HTTPException(404, "This run or segment is not in the current experiment.")
    if review.alignment == "llm" and (not segment.get("llm_match") or segment["llm_match"].get("status") == "not_run"):
        raise HTTPException(422, "This segment has no LLM alignment to review.")
    if review.alignment == "sequence" and not (segment.get("sequence_match") or (segment.get("match") or {}).get("method") == "sequence"):
        raise HTTPException(422, "This segment has no sequence alignment to review.")
    context = prediction_context(recording_id, run, segment, review.alignment, reference_for_run(experiment, run))
    if review.prediction_fingerprint is not None and review.prediction_fingerprint != context["prediction_fingerprint"]:
        raise HTTPException(409, "This prediction or reference changed after it was loaded. Refresh the recording before saving; your draft has not been changed.")
    record = review.model_dump()
    record["recording_id"] = recording_id
    if review.prediction_fingerprint is not None:
        record.update(context, context_status="bound_to_prediction")
    else:
        # Older clients are accepted without inventing evidence that they saw
        # the current prediction. Keep these records historical/unbound.
        record["context_status"] = "legacy_unbound"
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    with REVIEW_LOCK:
        saved = read_reviews()
        key = (recording_id, review.run_id, review.segment_id, review.alignment, review.prediction_fingerprint)
        default_recording = recording_manifest()[0]["id"]
        saved = [r for r in saved if (r.get("recording_id", default_recording), r.get("run_id"), r.get("segment_id"), r.get("alignment", "lexical"), r.get("prediction_fingerprint")) != key]
        saved.append(record)
        DATA.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=DATA, prefix=".reviews-", suffix=".json", delete=False) as handle:
                temporary_path = handle.name
                json.dump(saved, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, DATA / "reviews.json")
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
    return {"review": record, "count": len(saved)}


@app.get("/api/reviews/export")
def export_reviews():
    return JSONResponse(
        {"schema_version": 2, "exported_at": datetime.now(timezone.utc).isoformat(),
         "context_note": "Apply a verdict only to its matching prediction_fingerprint. Reviews without a fingerprint are historical and have unverified prediction context.",
         "reviews": read_reviews()},
        headers={"Content-Disposition": 'attachment; filename="liturgy-lab-reviews.json"'},
    )


def video_file(filename: str):
    path = DATA / "media" / filename
    if not path.is_file():
        raise HTTPException(404, "The local video is not downloaded yet.")
    return FileResponse(path, media_type="video/mp4")


@app.get("/media/recording/{recording_id}")
def recording_video(recording_id: str):
    return video_file(get_recording(recording_id)["media_file"])


@app.get("/media/{filename}")
def video(filename: str):
    if filename not in {r["media_file"] for r in recording_manifest()}:
        raise HTTPException(404, "This media file is not in the experiment.")
    return video_file(filename)


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Run Liturgy Lab on this Mac only.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
