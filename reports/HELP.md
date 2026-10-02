# Help

Explore five recordings alongside saved speech-recognition transcripts and bilingual service text.

> **Experimental predictions:** a section suggestion may be wrong or later than its actual start. The printed text and raw model transcript are kept separate.

## Watch and follow along

1. Choose a video with **Select recording**. The August 9 Dormition recording is the default; Sunday After Nativity is second.
2. Press **Play** inside the video. A direct click may be required by your browser.
3. Read **Model transcript** below the video for what ASR heard, including errors and gaps.
4. Read **Matins & Liturgy** beside it for the printed service text. English appears first.

The page uses saved predictions. No model runs while you watch.

## Jump to a section

Under **Find your place**, click **Matins (Orthros)** or **Divine Liturgy** to seek to its first suggested location. All suggested sections are visible in the switchboard; Matins and Liturgy have different colors.

Click a section or a timed service-text paragraph to seek. The first supported fragment may be later than the section's actual beginning. Sermons, omitted text, silence, and unsupported chant can remain unmatched.

## Read at your own pace

- Turn off **Follow audio** to browse without automatic following.
- Search the service text for a prayer, hymn, or response.
- Search the transcript for words in the model's output.
- Use the floating video's hide/show control to reclaim space while browsing.

## Check the reference

The links under **Matins & Liturgy** identify the texts used for the selected recording. The reference notice explains exact-date texts, substitutes, and reconstructions. Dates can be inferred from title and release/upload metadata; local wording and order may differ.

## Text-only preview

Directly opening `site/index.html` may offer text-only browsing in browsers that permit local scripts. The local HTTP launcher below is the tested workflow for synchronized YouTube playback.

## Run the shared package locally

1. Extract the entire ZIP to a folder.
2. Install Python 3 from [python.org](https://www.python.org/downloads/) if needed. Viewing needs no additional Python packages, virtual environment, models, or Apple GPU.
3. Start the launcher for your system:

| System | Launcher | Terminal alternative |
|---|---|---|
| Mac | Double-click `Start Viewer.command` | `python3 run_viewer.py` |
| Windows | Double-click `Start Viewer.cmd` | `py -3 run_viewer.py` |
| Linux | Use a terminal | `python3 run_viewer.py` |

Run the terminal command from the extracted package folder. On Mac, use that alternative if opening the launcher is blocked.

4. Open `http://127.0.0.1:8766/` if the browser does not open automatically.
5. Keep the terminal open. Press **Control–C** to stop the viewer.

If port 8766 is busy, run `python3 run_viewer.py --port 8767` and open `http://127.0.0.1:8767/`.

## Playback and internet

The small ZIP does not contain the recordings. YouTube playback requires an internet connection and permission from the video owner to embed the recording. Press Play inside the video. Section buttons seek; subtitles/reference follow the player's actual time. Browser autoplay restrictions may require another Play. 

If YouTube is blocked, unavailable, or disallows embedding, Source recording opens its original page; playback in that separate tab will not synchronize here. 

## What is included and shared?

The package includes only the chosen Turbo + sequence runs, their source provenance, and the reports. No saved human reviews, model weights, virtual environment, original private specification, credentials or local file paths are included. This is a read-only viewer; it does not save collaborator reviews. YouTube receives normal embedded-player requests. Transcripts stay in this static package; no recognition service is called. A public deployment makes the included text/predictions accessible to anyone. Source credits and date-reference caveats remain visible. Third-party content retains its original rights.

## Publish the static site

See the [publishing guide](../PUBLISH-GITHUB-PAGES.txt). Only the CONTENTS of site/ go in your repository. The same files work on any static web host; no backend or API key is needed.

For conclusions and model comparisons, read [Findings](FINDINGS.html) or the [detailed results](RESULTS.html).
