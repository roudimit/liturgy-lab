"""Download pinned MLX snapshots into the shared project cache; no GPU imports."""

import argparse
import json
import os
from pathlib import Path
import struct
import shutil
import time

PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT / "work"
os.environ.setdefault("HF_HOME", str(WORK / "cache/huggingface"))
# Ordinary HTTPS also provides resumable downloads; avoids stalled Xet workers
# observed on this Mac/network during the initial attempt.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")

from huggingface_hub import HfApi, hf_hub_download, snapshot_download

MODELS = {
    "30b": "mlx-community/Qwen3-30B-A3B-Instruct-2507-4bit",
    "32b": "mlx-community/Qwen3-32B-4bit",
    "35b": "mlx-community/Qwen3.6-35B-A3B-4bit",
    "70b": "cnfusion/Llama-3.3-70B-Instruct-Q2-mlx",
}


def validate_snapshot(snapshot: str, files: list[dict]) -> list[dict]:
    """Follow cache symlinks and inspect safetensors headers, not only exit status."""
    verified = []
    for item in files:
        path = Path(snapshot) / item["name"]
        actual = path.stat().st_size if path.is_file() else None
        if actual != item["bytes"]:
            raise RuntimeError(f"Incomplete model file {item['name']}: expected {item['bytes']} bytes, found {actual}")
        if item["name"].endswith(".safetensors"):
            with path.open("rb") as handle:
                header_size = struct.unpack("<Q", handle.read(8))[0]
                if not 2 <= header_size <= min(actual - 8, 16_000_000):
                    raise RuntimeError(f"Invalid safetensors header length in {item['name']}")
                header = json.loads(handle.read(header_size))
                if not isinstance(header, dict) or not any(key != "__metadata__" for key in header):
                    raise RuntimeError(f"Missing tensor metadata in {item['name']}")
        verified.append({"name": item["name"], "bytes": actual, "resolved_path": str(path.resolve())})
    return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", choices=MODELS, default=["30b", "35b"])
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--metadata-only", action="store_true", help="Inspect sizes/configuration without downloading weights")
    args = parser.parse_args()
    output = PROJECT / "data/large-model-inventory.json"
    inventory = json.loads(output.read_text()) if output.exists() else []
    if args.validate_only:
        for row in inventory:
            if row["model"] not in [MODELS[key] for key in args.models]:
                continue
            row["verified_files"] = validate_snapshot(row["snapshot"], row["files"])
            row["validation"] = "Resolved file sizes match HF metadata; all safetensors headers parse"
            print(f"Verified {row['model']}: {len(row['verified_files'])} files", flush=True)
        output.write_text(json.dumps(inventory, indent=2))
        return
    for key in args.models:
        name = MODELS[key]
        existing = next((row for row in inventory if row["model"] == name), None)
        revision = existing.get("revision") if existing else None
        info = HfApi().model_info(name, revision=revision, files_metadata=True)
        files = [{"name": item.rfilename, "bytes": item.size} for item in info.siblings
                 if item.rfilename.endswith((".safetensors", ".json", ".txt", ".model", ".jinja"))]
        row = {**(existing or {}), "model": name, "revision": info.sha, "files": files,
               "download_bytes": sum(item["bytes"] or 0 for item in files),
               "source_url": f"https://huggingface.co/{name}", "transfer": "HTTPS (Xet disabled)"}
        config = json.loads(Path(hf_hub_download(name, "config.json", revision=info.sha)).read_text())
        row["config"] = config
        # FP16/BF16 K and V cache, prior to padding/implementation overhead.
        text_config = config.get("text_config", config)
        head_dim = text_config.get("head_dim", text_config["hidden_size"] // text_config["num_attention_heads"])
        layer_types = text_config.get("layer_types")
        full_layers = sum(kind == "full_attention" for kind in layer_types) if layer_types else text_config["num_hidden_layers"]
        row["estimated_kv_bytes_per_token"] = 2 * full_layers * text_config["num_key_value_heads"] * head_dim * 2
        row["estimated_kv_8192_gib"] = row["estimated_kv_bytes_per_token"] * 8192 / 2**30
        row["kv_estimate_note"] = "Full-attention FP16/BF16 K/V cache only; excludes recurrent-state, activation, buffer and allocator overhead."
        if key == "70b":
            weight_bytes = sum(item["bytes"] for item in files if item["name"].endswith(".safetensors"))
            disk_free = shutil.disk_usage(WORK).free
            estimated_peak = weight_bytes + row["estimated_kv_bytes_per_token"] * 2304 + 2_000_000_000
            row["hardware_probe_assessment"] = {
                "prompt_token_limit": 2048, "output_token_limit": 256,
                "estimated_peak_bytes": estimated_peak, "ceiling_bytes": 26_000_000_000,
                "buffer_allowance_bytes": 2_000_000_000,
                "disk_free_bytes_before_download": disk_free,
                "feasible_estimate": estimated_peak <= 26_000_000_000 and disk_free >= row["download_bytes"] + 5_000_000_000,
                "estimate_note": "Weights plus 2304-token full-attention KV and 2 GB buffer allowance; a planning estimate, not proof of runtime fit. No system memory limits are raised.",
                "provenance_note": "Third-party 2-bit MLX conversion of unsloth/Llama-3.3-70B-Instruct; not an official Meta quantization. Standard Llama architecture, safetensors and tokenizer data only; trust_remote_code=False.",
                "purpose": "Short hardware-fit and Greek alignment probe, separate from the controlled 48-row comparison.",
            }
        inventory = [old for old in inventory if old["model"] != name] + [row]
        output.write_text(json.dumps(inventory, indent=2))
        if args.metadata_only:
            print(json.dumps(row, indent=2), flush=True)
            continue
        if key == "70b" and not row["hardware_probe_assessment"]["feasible_estimate"]:
            raise RuntimeError("70B estimate exceeds the configured memory ceiling or disk headroom")
        print(f"Downloading {name} revision {info.sha}: {row['download_bytes'] / 1e9:.2f} GB; 8k KV estimate {row['estimated_kv_8192_gib']:.2f} GiB", flush=True)
        started = time.perf_counter()
        row["snapshot"] = snapshot_download(name, revision=info.sha,
            allow_patterns=["*.safetensors", "*.json", "*.txt", "*.model", "*.jinja"], max_workers=2)
        row["download_seconds"] = time.perf_counter() - started
        row["verified_files"] = validate_snapshot(row["snapshot"], files)
        row["validation"] = "Resolved file sizes match HF metadata; all safetensors headers parse"
        row["download_complete"] = True
        output.write_text(json.dumps(inventory, indent=2))
        print(f"Completed {name} in {row['download_seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
