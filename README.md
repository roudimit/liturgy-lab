# Liturgy Lab

[Open the online viewer](https://roudimit.github.io/liturgy-lab/)

Explore five recordings with saved speech recognition transcripts, suggested sections, and bilingual service text. Predictions are experimental; see [Findings](reports/FINDINGS.md), [Results](reports/RESULTS.md), and [Help](reports/HELP.md).

## View locally

Extract the ZIP, then double-click **Start Viewer.command** on Mac or **Start Viewer.cmd** on Windows. Alternatively run:

    python3 run_viewer.py

Open http://127.0.0.1:8766/ and keep the terminal open. No Python packages or models are needed to view the results. YouTube playback needs internet access. Use --port 8767 if the default port is busy.

## Research code and saved experiments

The research/ directory contains the ASR and alignment pipeline, experiment scripts, tests, source texts, and saved outputs. See [research/README.md](research/README.md) for commands. To prepare a separate Python virtual environment on an Apple Silicon Mac with Python 3.11 or newer:

    cd research
    bash setup.sh

Rerunning inference requires downloading recordings and model weights separately. The saved outputs can be inspected without rerunning inference.

## Sharing and publishing

The collaborator ZIP contains the same committed files as this repository, plus private/ADS Pilot Specification.docx. The original specification is deliberately excluded from GitHub. The ZIP contains no Git history.

Downloaded recordings/audio, model weights, virtual environments, caches, private human reviews, and credentials are excluded from both. Third-party recordings and service texts retain their original rights; source credits and reference-date caveats remain in the viewer and saved data.

GitHub Pages serves main at /(root). No backend is required. Research files and outputs in this repository are public, as are the viewer files.

To rebuild the ZIP from the committed files:

    python3 scripts/package_share.py --output /path/to/liturgy-lab-share.zip --spec "/path/to/ADS Pilot Specification.docx"
