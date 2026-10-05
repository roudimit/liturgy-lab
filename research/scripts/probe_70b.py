"""A bounded 70B hardware-fit probe, separate from the full alignment benchmarks.

The two cases use deliberately small, hand-selected candidate pools. They test
whether this quantization loads and produces usable structured Greek matching
output; they do not estimate alignment accuracy or candidate-retrieval quality.
Run only when the shared Mac GPU has been released by the ASR process.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import resource
import subprocess
import time

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
WORK = PROJECT / "work"
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("HF_HOME", str(WORK / "cache/huggingface"))

from liturgy_lab.llm import build_messages, validate_response

MODEL = "cnfusion/Llama-3.3-70B-Instruct-Q2-mlx"
MAX_MEMORY = 26_000_000_000


def system_swap_usage() -> str | None:
    """Read Mac-wide swap evidence without changing any system setting."""
    if sys.platform != "darwin":
        return None
    return subprocess.check_output(["/usr/sbin/sysctl", "-n", "vm.swapusage"], text=True).strip()


def prepare() -> tuple[dict, dict, list[dict]]:
    inventory = json.loads((DATA / "large-model-inventory.json").read_text())
    info = next(row for row in inventory if row["model"] == MODEL)
    if not info.get("download_complete") or not info.get("validation"):
        raise ValueError("The pinned 70B snapshot must finish downloading and pass file validation first")
    if not info["hardware_probe_assessment"]["feasible_estimate"]:
        raise ValueError("The 70B model did not pass the memory/disk planning check")
    reference = json.loads((DATA / "reference-MIxJvLfaynY.json").read_text())
    source = json.loads((DATA / "qwen35b-combined-MIxJvLfaynY.json").read_text())
    if source["reference_id"] != reference["reference_id"]:
        raise ValueError("Reference fingerprint mismatch")
    units = {unit["id"]: unit for unit in reference["units"]}
    by_id = {str(row["id"]): row for row in source["segments"]}
    cases = []
    for sid, candidate_ids in [
        ("274", ["matins:u0166", "liturgy:u0007", "matins:u0165"]),
        ("515", ["liturgy:u0001", "matins:u0095", "liturgy:u0009"]),
    ]:
        raw = by_id[sid]
        scores = {candidate["unit_id"]: candidate.get("score", 0.0) for candidate in raw["candidates"]}
        row = {key: raw[key] for key in ("id", "start", "end", "text")}
        row["candidates"] = [{**units[uid], "unit_id": uid, "score": scores.get(uid, 0.0)} for uid in candidate_ids]
        messages = build_messages([row], max_text_chars=240)
        cases.append({"raw_asr": row, "messages": messages,
                      "selection_note": "Hand-selected three-candidate pool; no retrieval quality or accuracy inference."})
    return info, reference, cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true", help="CPU tokenizer preflight; no MLX import or model load")
    parser.add_argument("--output", type=Path, default=DATA / "llama70b-hardware-probe.json")
    parser.add_argument("--max-tokens", type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.max_tokens <= 256:
        raise ValueError("The short probe permits at most 256 output tokens per case")
    info, reference, cases = prepare()
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(info["snapshot"], trust_remote_code=False, local_files_only=True)
    for case in cases:
        tokens = tokenizer.apply_chat_template(case["messages"], tokenize=True, return_dict=False, add_generation_prompt=True)
        case["prompt_tokens"] = len(tokens)
        if len(tokens) > 2048:
            raise ValueError("The short probe prompt exceeds 2048 tokens")
    if args.prepare_only:
        print(json.dumps({"model": MODEL, "revision": info["revision"], "cases": cases}, ensure_ascii=False, indent=2))
        return
    del tokenizer

    # All GPU imports and operations are below the prepare-only return.
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    result = {"model": MODEL, "revision": info["revision"], "reference_id": reference["reference_id"],
              "source_urls": {"quantization": info["source_url"], "base_model": "https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct"},
              "experiment": "Short two-case hardware-fit probe with hand-selected candidates",
              "limits": ["Not the controlled 48-row comparison; no accuracy estimate.",
                         "Third-party 2-bit conversion, not an official Meta quantization.",
                         "Greek is not one of the eight explicitly supported languages in Meta's Llama 3.3 model card; this probe does not establish Greek suitability.",
                         "Two-bit quantization can damage quality; parameter count alone does not establish usefulness.",
                         "MLX memory setting is a guideline, not a hard allocation cap; observed peaks are checked after loading and token steps."],
              "configuration": {"max_prompt_tokens": 2048, "max_output_tokens": args.max_tokens,
                                "temperature": 0.0, "prefill_step_size": 128,
                                "memory_review_ceiling_bytes": MAX_MEMORY, "trust_remote_code": False},
              "device": mx.device_info(), "cases": cases, "status": "started"}
    result["system_swap_before"] = system_swap_usage()
    previous_limit = mx.get_memory_limit()
    mx.set_memory_limit(min(previous_limit, MAX_MEMORY))
    mx.set_cache_limit(256_000_000)
    result["configuration"]["process_memory_guideline_bytes"] = mx.get_memory_limit()
    started = time.perf_counter()
    try:
        print(f"Loading {MODEL}", flush=True)
        model, tokenizer = load(info["snapshot"], tokenizer_config={"trust_remote_code": False})
        result["load_seconds"] = time.perf_counter() - started
        result["load_peak_memory_gb"] = mx.get_peak_memory() / 1e9
        if mx.get_peak_memory() > MAX_MEMORY:
            raise RuntimeError("Observed model-load peak exceeded the 26 GB review ceiling")
        sampler = make_sampler(temp=0.0)
        for case in cases:
            print(f"Greek probe segment {case['raw_asr']['id']} ({case['prompt_tokens']} prompt tokens)", flush=True)
            tokens = tokenizer.apply_chat_template(case["messages"], tokenize=True, add_generation_prompt=True)
            case_started = time.perf_counter()
            parts, last = [], None
            for response in stream_generate(model, tokenizer, prompt=tokens, max_tokens=args.max_tokens,
                                            sampler=sampler, prefill_step_size=128):
                parts.append(response.text)
                case["raw_response"] = "".join(parts)
                last = response
                if mx.get_peak_memory() > MAX_MEMORY:
                    raise RuntimeError("Observed generation peak exceeded the 26 GB review ceiling")
                if time.perf_counter() - started > 480:
                    raise RuntimeError("The short hardware probe exceeded its eight-minute runtime review limit")
            case["elapsed_seconds"] = time.perf_counter() - case_started
            case["generation_tokens"] = getattr(last, "generation_tokens", 0)
            case["generation_tokens_per_second"] = getattr(last, "generation_tps", None)
            case["prompt_tokens_per_second"] = getattr(last, "prompt_tps", None)
            case["finish_reason"] = getattr(last, "finish_reason", None)
            case["peak_memory_gb"] = getattr(last, "peak_memory", None)
            case["validated_decision"] = validate_response(case.get("raw_response", ""), [case["raw_asr"]], reference)
            if case["finish_reason"] == "length":
                for decision in case["validated_decision"].values():
                    decision["warnings"].append("output_token_limit_reached")
                    if decision["status"] == "matched":
                        decision["status"] = "uncertain"
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        result["status"] = "completed"
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["total_seconds"] = time.perf_counter() - started
        result["peak_memory_gb"] = mx.get_peak_memory() / 1e9
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result["process_peak_rss_gb"] = rss * (1 if sys.platform == "darwin" else 1024) / 1e9
        result["system_swap_after"] = system_swap_usage()
        result["swap_note"] = "Swap is a Mac-wide snapshot and can include other applications; MLX peak and process RSS are separate measurements."
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({key: value for key, value in result.items() if key != "cases"}, ensure_ascii=False, indent=2), flush=True)
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
