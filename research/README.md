> This directory contains the research pipeline and saved experiments. For the shared website, return to the repository root. Videos, models, environments, caches, and private reviews are intentionally omitted.

# Liturgy Lab

A local, offline pre-MVP experiment on an Apple M5 MacBook Air with 32 GB memory. It transcribes public church recordings with MLX Whisper, retrieves bilingual liturgy passages, and compares local Whisper and Qwen models, including larger models that fit this Mac. The viewer keeps the raw model transcript separate from the canonical text.

## Open the viewer

Open **http://127.0.0.1:8765** while the server is running. To restart later, double-click **Launch Liturgy Lab.command**, or run from this folder:

```sh
.venv/bin/python -m liturgy_lab.cli serve
```

Choose a recording, speech-recognition run, and alignment method. Click a suggested section or a timed reference paragraph to seek the local video. Greek and English text follow accepted predicted matches. Search either column, turn off automatic following to read freely, or open **Review segment** to label results and enter a transcript made by listening. Reviews are saved locally and can be exported.

The viewer shows five recordings and the processed intervals of each run. Full-recording runs and fixed-window model comparisons are kept separate. Unprocessed intervals have no predictions. LLM experiments use selected clips; other segments explicitly show that the LLM was not run. Chronological sequence alignment is the default. Historical LLM comparisons retain their original reference and are labeled separately.

The selected configuration for the additional recordings is **Whisper Large v3 Turbo + sequence-aware text matching**. ASR/LLM model comparisons were confined to the first video; the other videos receive one Turbo pass. The larger LLMs remain diagnostic comparisons rather than the viewer's default matcher.

Read **RESULTS.md** for measured speed, observed failures, sample coverage, and what remains unvalidated. **COLLABORATOR-SUMMARY.txt** is a short forwardable summary; **GREEK-EXAMPLES.md** contains illustrative raw transcription errors.

## Installed environment

- Dedicated `.venv`, created with bundled Python 3.12.14. No global Python packages were installed.
- Exact package versions in `requirements-lock.txt`; project dependencies in `pyproject.toml`.
- FFmpeg comes from `imageio-ffmpeg`, inside the virtual environment.
- Downloaded model weights were deleted on October 1, 2026 to reclaim 68.97 GiB. The viewer needs no models. To rerun inference, download the selected model again into `work/cache/huggingface` (or set `HF_HOME`).
- Media and experiment results live in `data/`. Inference and playback run on this Mac. Downloads require network access; subsequent inference can use `HF_HUB_OFFLINE=1`.
- The server binds to `127.0.0.1`, uses no external scripts/fonts, and loads no ML models. The local viewer does not need network access after downloads.

To recreate the virtual environment on Apple Silicon with Python 3.11 or later:

```sh
LITURGY_PYTHON=/path/to/python3.12 ./setup.sh
```

MLX requires access to the Metal GPU. Ordinary Terminal has this access; restricted execution sandboxes may not. No system GPU settings were changed.

## Reproduce the experiments

Run commands from this folder. These commands document the experiments; opening the completed viewer does not require rerunning them. Existing saved ASR comparison outputs are reused by the benchmark scripts. Use distinct output names when trying new configurations.

```sh
export HF_HOME="$PWD/work/cache/huggingface"
export HF_HUB_OFFLINE=1

# Full original recording, independently detecting language every 30 seconds.
.venv/bin/python -m liturgy_lab.cli asr data/media/source-audio.m4a \
  --start 0 --duration 7668 --model turbo --language auto \
  --output data/turbo-full.json

# Compare Small / Turbo and one-time vs per-chunk language detection.
# Also run four short samples in each additional recording.
.venv/bin/python scripts/benchmark_asr.py

# Expand the service-opening windows in both additional recordings.
.venv/bin/python scripts/scan_openings.py

# Raw lexical baseline, then two Qwen models on the same 48 selected rows.
.venv/bin/python -m liturgy_lab.cli align data/turbo-full.json \
  --output data/turbo-full-aligned.json
.venv/bin/python scripts/benchmark_llm.py --prepare-only
.venv/bin/python scripts/benchmark_llm.py

# Same 24 minutes, identical settings, separately timed models.
.venv/bin/python scripts/compare_asr_models.py --model small
.venv/bin/python scripts/compare_asr_models.py --model turbo
.venv/bin/python scripts/compare_asr_models.py --model large-v3
.venv/bin/python scripts/audit_asr_models.py

# Supplemental Greek-language retries, kept outside the controlled comparison.
.venv/bin/python -m liturgy_lab.cli asr data/media/source-audio.m4a \
  --start 1950 --duration 30 --model large-v3 --language el \
  --output data/large-v3-greek-retry-1950.json
.venv/bin/python -m liturgy_lab.cli asr data/media/source-audio.m4a \
  --start 4920 --duration 30 --model large-v3 --language el \
  --output data/large-v3-greek-retry-4920.json
.venv/bin/python scripts/build_greek_retries.py

# Transcribe the three additional recordings completely in reusable hour blocks.
.venv/bin/python scripts/transcribe_recordings.py

# Full non-turbo comparison of the original recording.
.venv/bin/python -m liturgy_lab.cli asr data/media/source-audio.m4a \
  --model large-v3 --output data/large-v3-full.json

# Larger LLMs: download and validate once with networking enabled.
# Enable downloads, then restore local-only inference.
unset HF_HUB_OFFLINE
.venv/bin/python scripts/download_large_models.py --models 30b 35b
export HF_HUB_OFFLINE=1
.venv/bin/python scripts/benchmark_large_llm.py --model 30b
.venv/bin/python scripts/benchmark_large_llm.py --model 35b
.venv/bin/python scripts/benchmark_combined_llm.py

# Optional hardware ceiling probe, separate from the 48-row comparison.
# This tested 70B 2-bit conversion produced unusable output; it is not the default.
unset HF_HUB_OFFLINE
.venv/bin/python scripts/download_large_models.py --models 70b
export HF_HUB_OFFLINE=1
.venv/bin/python scripts/probe_70b.py

# Track progress through combined Matins + Liturgy references and export sessions.
.venv/bin/python scripts/build_sessions.py
.venv/bin/python scripts/summarize_experiments.py
.venv/bin/python scripts/audit_full_asr.py

# Regression tests and metrics on saved human reviews.
.venv/bin/python -m pytest -q
.venv/bin/python -m liturgy_lab.cli evaluate
```

For a separate audio file or a different interval, use `cli asr AUDIO --start SECONDS --duration SECONDS --output NEW.json`. `--language auto` redetects per chunk; `continuous` detects once; `el` and `en` force a language. `--model small` selects multilingual Whisper Small; `turbo` selects Large v3 Turbo; `large-v3` selects the full non-turbo model. A compatible Hugging Face model ID may also be supplied. First use of a new model requires disabling `HF_HUB_OFFLINE` to download it.

`cli llm ALIGNED.json --reference data/reference-MIxJvLfaynY.json --limit 24 --output NEW.json` runs the 4B model on the first 24 rows; select the reference file that produced the aligned input. `--model mlx-community/Qwen3-1.7B-4bit` selects the smaller model. The dedicated benchmark script selects consecutive clips spread across the first recording, keeping separated clips out of the same prompt. The basic `align`/`assemble` commands retain the historical September 30 defaults; use `scripts/build_sessions.py` for the current multi-recording viewer.

## What the pipeline does

1. Decode audio to mono, 16 kHz PCM using the bundled FFmpeg.
2. Run multilingual MLX Whisper in 30-second chunks with independent language detection, no reference prompt, no preceding-text conditioning, and word timestamps. All timestamps stay on the original video clock.
3. Import Matins ordinary, dated Matins proper, and the appropriate Liturgy as a combined bilingual reference, preserving source credits. Reference metadata states whether the edition is exact or a same-feast/Sunday substitute. St. Basil and St. John Chrysostom are kept distinct.
4. Retrieve candidates using accent-normalized Greek/English text, light Greek pronunciation tolerance, and auxiliary Romanized-Greek matching. This is lexical similarity, not an LLM or semantic truth test.
5. Track a chronological path with a beam/Viterbi-style algorithm: forward skips are allowed, short reversals are allowed (three reference units by default), and UNKNOWN retains the prior position without assigning the current speech. Temporal gaps reset the path. Nearby distinctive anchors can disambiguate repeated prayers; weak associations stay unassigned.
6. Optionally ask a local Qwen model to select a retrieved unit or UNKNOWN. Validate IDs and structured output, preserve raw prompts/responses, and withhold weak or ambiguous decisions. Historical controlled model comparisons intentionally retain the old reference; new combined-reference experiments are separately labeled.
7. Use the opening blessing as a heuristic service boundary when recognized. Matins is matched to its own text before that boundary. A missed opening no longer hides every subsequent association.

These are offline heuristics, some using subsequent context. They do not establish real-time latency or causal streaming behavior. The viewer shows no current association during silence, unprocessed gaps, or unmatched material. Internally, the tracker retains its last position through UNKNOWN rows and resets at long gaps or independent clip boundaries. Scores are text-support heuristics or LLM self-ratings, not probabilities.

## Evaluation and review

There is **no independent human ground truth yet**. Match counts, apparent text agreement, and model disagreements are not accuracy. The code deliberately does not manufacture a word-error rate from the printed liturgy: actual services include variants, repetitions, omitted material, sermons, and different readings.

After listening and entering corrected transcripts through the review UI, `cli evaluate` computes accent-normalized WER on those annotated segments and summarizes review labels. Results remain limited to that reviewed sample. Reviews are bound to the exact prediction/reference; changed or older unbound reviews remain historical and exportable, and are excluded from current-run metrics. To measure key-moment timing, supply an independently authored JSON array such as `[{"section_id":"liturgy:s000","time":4410.0}]` to `cli evaluate --moments LABELS.json`. The example is a schema illustration, not a ground-truth label. Exhaustive labels are required to interpret unmatched predictions as false triggers.

The follow-on study should label spoken Greek, spoken English, chant, language switches, silence, and out-of-reference speech separately; then add other parishes and actual phone recordings. This prototype does not establish the specification's acceptance criteria, far-field performance, battery use, or iPhone feasibility.

## Sources and retained outputs

- Original public recording: https://www.youtube.com/watch?v=MIxJvLfaynY
- Additional recordings: https://www.youtube.com/watch?v=vkkeLmltf_4, https://www.youtube.com/watch?v=IuZ8WRk-POI, and https://www.youtube.com/watch?v=n674zECLjTI
- Supplied reference: https://dcs.goarch.org/goa/dcs/h/s/2026/09/30/li/gr-en/index.html
- Calendar / Matins discovery: https://dcs.goarch.org/goa/dcs/dcs.html
- March 29, 2026 reference identifies St. Basil: https://dcs.goarch.org/goa/dcs/h/s/2026/03/29/li/gr-en/index.html
- MLX Whisper: https://github.com/ml-explore/mlx-examples/tree/main/whisper
- MLX LM: https://github.com/ml-explore/mlx-lm
- Models: https://huggingface.co/mlx-community/whisper-large-v3-turbo, https://huggingface.co/mlx-community/whisper-small-mlx, https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit, https://huggingface.co/mlx-community/Qwen3-1.7B-4bit

`data/reference-source.html` and `reference.json` preserve the original September 30 baseline. The current per-recording corpora are `data/reference-<video-id>.json`, with source URLs, hashes, attribution, service labels, and date-substitution caveats. To regenerate them, run `scripts/build_references.py` and then `scripts/refine_december_references.py`; the second step reconstructs the December calendar components from cached, attributed GOA donors. The resulting 2025 references are labeled reconstructions, not recovered exact editions. Raw ASR JSON, raw and guarded LLM decisions, model prompts/responses, timing metrics, and sample definitions remain in `data/`. Compact `session*.json` files drive the UI; `.vtt` files export raw ASR subtitles. `data/reviews.json` is created only when a review is saved.


## Shareable static viewer

Downloaded model weights were removed after benchmarking; saved results remain.
The static export contains only the chosen runs, their reference texts, reports,
and a YouTube/local-file player. No Python or ML backend runs on the website.
Local preview uses Python's standard library with no packages or virtual environment.

To create a new export from this research folder:

```sh
.venv/bin/python scripts/build_static_export.py . /tmp/liturgy-lab-share
python3 /tmp/liturgy-lab-share/run_viewer.py
```

The export's START-HERE.txt covers local use. PUBLISH-GITHUB-PAGES.txt explains
uploading only the contents of site/ to GitHub Pages. The shared viewer is read-only;
original local review files are never exported. Third-party reference credits remain.
