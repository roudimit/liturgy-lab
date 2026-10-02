# Local liturgy pre-MVP: expanded experiment

The Mac can run this pipeline entirely locally. It can often locate a service passage even when the Greek transcript contains many errors. The present evidence supports a service-following/navigation prototype, but does not support promising reliable verbatim Greek captions, especially for chant.

Tested on an Apple M5 MacBook Air with 32 GB unified memory. Inference used MLX/Metal in the project's Python virtual environment; audio and transcripts were not sent to an inference service. Model downloads preceded the timed comparison runs. ASR and LLM inference jobs ran serially.

## Working approach at a glance

The working configuration is **Whisper Large v3 Turbo on the Mac, followed by an offline sequence-aware text matcher**. An LLM is not required for the current viewer.

1. Transcribe each recording locally in independent 30-second audio chunks, detecting the language per chunk and preserving the original video timestamps. Keep this raw ASR output, including errors.
2. Assemble the relevant Greek/English Matins and Liturgy texts from GOA, including dated material where available and explicit notices where a substitute or reconstructed reference is used.
3. Retrieve plausible text passages with Greek/English lexical similarity, then find a plausible sequence through them. The matcher allows skipped passages, small backward steps, repeated text, and UNKNOWN for unsupported speech. It can use later context to resolve an earlier position.
4. Save the predictions once and display them alongside the video and canonical service text. Section buttons seek to the first supported fragment, which may be later than a section's actual beginning. Playing the viewer does not run ASR or an LLM.

ASR and LLM comparisons were performed on the first recording. The chosen Turbo configuration and sequence matcher were then applied to all four recordings. This is a working offline navigation demo, not validated live cue detection.

## What to tell collaborators

Spoken, formulaic liturgical Greek is often recognizable enough to identify the prayer. Chant is much less dependable: all three Whisper models made substantial word errors, omitted phrases, repeated unrelated text, or selected the wrong language. Greek can appear in Latin characters, and generated subtitle credits such as AUTHORWAVE are clear warning signs. English is generally easier to read, although sung English also contains errors.

The full non-turbo Whisper Large v3 is feasible on this Mac, but it did not consistently improve Greek in the controlled sample. Matching more text is useful evidence of better localization, not proof of better transcription: a matcher can retrieve the correct prayer from a few surviving words, and a sequence model can also propagate a wrong anchor. A small independent listening/transcription set is still needed to measure WER and section-location accuracy.

This review compared raw model text with plausible printed passages. It was **not** an independent human listening transcription. Canonical text remains separate from raw ASR in both the saved data and viewer.

## Controlled ASR comparison

Sixteen identical 90-second windows, totaling 24 minutes, cover Matins, spoken prayers, chant, the Liturgy opening, readings, later liturgical material, and an extra-liturgical address. Each model used independent 30-second chunks, automatic language detection per chunk, temperature zero, no previous-text conditioning, word timestamps, and no canonical-text prompt. Windows were chosen purposefully, not randomly. Each model ran in a fresh process after download.

| Model | Time for 24 min audio | Speed relative to playback | Peak MLX allocation |
|---|---:|---:|---:|
| Whisper Small | 65.6 s | 21.95× | 1.23 GB |
| Whisper Large v3 Turbo | 113.1 s | 12.73× | 2.19 GB |
| Whisper Large v3 | 202.9 s | 7.10× | 3.90 GB |

Large v3 was **1.79× slower than Turbo**, or about 90 extra seconds for these 24 minutes. Timings include model loading and first-use compilation inside inference and exclude download/audio decode; they are single runs, not repeated thermal-controlled benchmarks. Peak MLX allocation does not include all Python/application/system memory.

The complete original recording was also processed with non-turbo Large v3: **7,667.9 seconds of audio in 1,381.9 seconds (23.0 minutes), 5.55× faster than playback, 3.90 GB peak MLX allocation**. The earlier complete Turbo run took 606.7 seconds (10.1 minutes, 12.64× playback). Large v3 therefore took 2.28× as long on the full recording, adding 12.9 minutes. This full-run ratio and the paired-window ratio answer different timing questions; audio mix and run conditions vary, and neither is a repeated thermal-controlled measurement.

With the same full recording, combined reference, and final tracker, Turbo associated **2,133.86 seconds of ASR-timestamped material across 49 sections**, versus **1,828.12 seconds across 45 sections** for Large v3. This is a timestamp/coverage proxy, not word accuracy: segment boundaries differ, and accepted associations can be wrong. Both found the opening blessing and parts of the Trisagion, neither automatically recovered Small Entrance, and neither assigned the final address to the printed service. The final guard also removes the observed false jump from “in the kingdom of heaven” into the Memorial appendix. Full paired-bin details are in `data/full-asr-comparison.json`.

Large v3 sometimes repaired meaningful Greek words, including the phrase “σύμπαντος κόσμου,” but it also introduced long unrelated repetitions and more wrong-language renderings in other passages. There was no consistent Greek advantage across this sample. The artifact `data/asr-model-comparison.json` preserves paired 30-second bins, language-stratified evidence, raw transcripts, and reference candidates. Similarity, accepted speech duration, and model language agreement are proxies, not accuracy percentages. The Greek stratum excludes bins where models disagree about the language, so the difficult wrong-language cases must also be examined.

Two additional, separately labeled 30-second Large v3 retries forced Greek. At 32:30, this restored Greek script and recognizable Matins Antiphon text but retained errors and an AUTHORWAVE artifact. Around 1:22:00, it recovered Small Entrance/Entrance Hymn evidence that automatic detection had largely lost. These targeted retries were selected after seeing failures and are not part of the controlled model ranking. They suggest trying language-aware segmentation before concluding that fine-tuning is necessary.

## How text matching works

Independent text matching normalizes Greek accents and final sigma, compares words/characters, tolerates some pronunciation-related spellings, and recognizes some Romanized Greek. It compares each emitted segment with candidate bilingual units. It is a retrieval baseline, not an LLM transcription correction step.

The earlier prototype had only limited local anchor checks and a restrictive opening-blessing gate. It did not have a full chronological tracker. The updated default uses an offline beam/Viterbi-style sequence path: it can stay on a passage, advance with omissions, move backward by up to three reference units, or assign UNKNOWN. Independent sampled clips and long audio gaps reset the path. Nearby distinctive text anchors are required to place ambiguous replies. Service transitions need supporting context, so a repeated doxology by itself should not move Matins into the Liturgy. These are heuristics and use future context; this is not a streaming implementation.

The local LLM experiments retrieve candidates and ask the model to choose a unit or abstain. Historical comparisons used short consecutive batches and the old reference, so they did not implement global chronology. The new combined-reference experiment also receives nearby sequence anchors, explicitly labeled as fallible, and validates verbatim evidence quotes. A valid quote or well-formed JSON still does not prove that a proposed location is correct.

More matches did not come only from English. In the final full Turbo run on the original video, 290 of 421 accepted segments came from Greek-labeled ASR chunks and 131 from English-labeled chunks. Even the original 56 conservative suggestions included 30 Greek-script segments and 26 English/Latin-script segments. Current language breakdowns use ASR labels, which are imperfect for mixed and Romanized output. The main increase comes from adding missing Matins/date-appropriate material and improving occurrence tracking, rather than demonstrated ASR accuracy gains.

## Why the earlier recordings and sections were missing

The original reference was September 30, 2026, and contained only the Chrysostom Liturgy. The first recording appears to be September 8, 2025; it includes substantial Matins before the Liturgy. The second and third recordings had only 16 minutes of sampled audio each. The old opening gate then hid text associations when it failed to recover the blessing. March 29, 2026, uses St. Basil's Liturgy, so the old Chrysostom reference also omitted relevant prayers.

The expanded viewer separates Matins and Liturgy, retains the exact reference used by each run, and shows source/date caveats. Historical LLM runs remain attached to their original reference rather than reusing incompatible unit IDs. Suggested section buttons seek to the first accepted fragment; that can be later than the real start of the section. Unmatched sermons, missing seasonal material, silence, and unprocessed intervals are not filled with canonical captions.

| Recording / inferred service date | Reference used |
|---|---|
| Original, Nativity of the Theotokos, September 8, 2025 | Full festal Matins plus Chrysostom Liturgy from the same feast in 2026; explicitly a substitute. |
| 11th Sunday of Luke, December 14, 2025 | Reconstructed Matins + Chrysostom: Mode 2, Eothinon 5, Luke 24:12–35 at Matins; Colossians 3:4–11 and Luke 14:16–24 at Liturgy. |
| Sunday of St. Mary of Egypt, March 29, 2026 | Exact calendar-date GOA Matins and **St. Basil** Liturgy. |
| Added Sunday After Nativity, December 28, 2025 | Reconstructed Matins + Chrysostom: Mode 4, Eothinon 7, John 20:1–10 at Matins; Galatians 1:11–19 and Matthew 2:13–23 at Liturgy. |

Dates remain inferences from titles, release/upload metadata, and textual consistency; upload dates alone are not ground truth. Exact 2025 DCS pages returned 404. December reconstruction uses the [2025 GOARCH calendar](https://www.goarch.org/chapel/calendar?month=12&viewStyle=GridView&viewType=ViewReadings&year=2025), dated parish bulletins, and attributed official DCS donor passages. The new recording's unrelated St. Stephen material from the substitute layout was removed; an unverified prokeimenon remains uncovered. September's [same-feast edition](https://dcs.goarch.org/goa/dcs/h/s/2026/09/08/li/gr-en/index.html) and March's [calendar-date St. Basil edition](https://dcs.goarch.org/goa/dcs/h/s/2026/03/29/li/gr-en/index.html) are linked in the viewer. Per-unit source provenance, donor URLs/hashes, and reconstruction operations are retained in the reference artifacts.

## Completed recordings and viewer

All four videos have a complete Turbo ASR pass. Model comparisons were confined to the first video; the other three received one Turbo pass, followed by the same sequence matcher. The final matcher version is v4. These section counts measure suggested coverage, not verified accuracy or exact section onsets.

| Recording | Audio processed | Turbo inference | Suggested Matins sections | Suggested Liturgy sections | Total sections |
|---|---:|---:|---:|---:|---:|
| September 8 / original | 127.8 min | 10.1 min | 31 | 18 | 49 |
| December 14 / 11th Sunday of Luke | 224.6 min | 19.4 min | 41 | 18 | 59 |
| March 29 / St. Mary of Egypt | 202.8 min | 19.9 min | 33 | 23 | 56 |
| December 28 / new recording | 148.6 min | 16.0 min | 12 | 21 | 33 |

Additional-recording timings sum saved contiguous hour blocks, including their loading/compilation work. Some blocks were cached from earlier runs; these totals are not a repeated, controlled speed benchmark. Complete audio coverage means the entire recording was submitted to ASR; it does not mean the recognizer emitted words everywhere.

| Recording | Associated segments from Greek-labeled chunks | From English-labeled chunks | Other language labels | Total associated segments |
|---|---:|---:|---:|---:|
| September 8 / original | 290 | 131 | 0 | 421 |
| December 14 / 11th Sunday of Luke | 140 | 694 | 0 | 834 |
| March 29 / St. Mary of Egypt | 165 | 708 | 0 | 873 |
| December 28 / new recording | 40 | 359 | 0 | 399 |

Language labels are Whisper predictions, not independently verified language. Segment counts are comparable for inspecting one fixed transcript, but should not be used to rank ASR models with different segmentation.

The original video now has 18 Liturgy section suggestions plus 31 Matins suggestions. Its default Turbo run finds Trisagion material but still misses Small Entrance; that passage is available in the separately labeled, selected forced-Greek retry. The new recording has distinctive Small Entrance and Entrance Hymn anchors at 1:00:02.78 and 1:01:30.00 respectively.

For December 14, no opening blessing was recognized. Its first supported Liturgy anchor is Antiphon 2 at 1:32:00, although shared litany text occurs earlier. The service-jump button is therefore a first suggested location, not an estimate of when the Liturgy truly began. The inspected sermon (7057–7832 s), announcements (12034–12652 s), and later forty-day blessing material remained unassociated. The new recording’s closing address/sermon probe from 7140 s onward also remained unassociated. These probes were chosen from emitted text, not independently annotated audio.

**Known failure in the St. Mary recording:** the later Memorial rite is absent from its St. Basil reference. Five shared prayer fragments, totaling 11.22 ASR-timestamped seconds around 10502–11043 s, are incorrectly associated with Dismissal. These predictions remain in the results rather than being manually removed to improve the counts. The opening blessing was detected at 5269.42 s; inspected sermon material (6625–7691 s) and closing announcements (11113 s onward) have no accepted associations. Details and raw examples are saved in data/full-recording-audit-IuZ8WRk-POI.json.

Some accurately recognizable priest prayers also remain unmatched because retrieval currently excludes reference units tagged inaudible, even when the recording microphone captures them. For example, the prayer beginning “No one bound by worldly desires” around 7727.58 s corresponds to liturgy:u0136. This is a reference/retrieval limitation, so an unmatched segment is not necessarily an ASR failure. These final audit findings were documented without changing the frozen matcher or rerunning model comparisons.

The viewer now follows both the raw transcript and bilingual reference as audio advances or a section is selected. Turning off Follow audio, or searching a panel, allows manual reading. Run-specific references and review fingerprints prevent old decisions from silently attaching to changed predictions. No human review labels were manufactured.

## Larger local LLMs

The original 1.7B/4B models were convenience baselines, not the Mac's limit. Four-bit 30B–35B models fit with useful context headroom. The tested Qwen models are mixture-of-experts models: total parameter count determines much of the storage footprint, while only a subset participates for each token. This makes them attractive for this laptop, but does not guarantee better liturgical interpretation.

The historical 48-row replay keeps the same saved message content across models; 47 rows have candidates and are actually sent to the LLM. It intentionally retains the old, incomplete reference to isolate the model change. A second experiment uses the combined Matins/Liturgy reference and selected Greek/chant/address clips; its results are not directly comparable to that historical replay.

| Local LLM | Total time, 48-row replay | Peak MLX allocation | Invalid segment decisions caught | Guarded matched / uncertain / unknown |
|---|---:|---:|---:|---:|
| Qwen3 1.7B, 4-bit | 163.0 s | 2.65 GB | 22 | 4 / 4 / 40 |
| Qwen3 4B Instruct 2507, 4-bit | 184.6 s | 4.27 GB | 4 | 8 / 13 / 27 |
| Qwen3 30B-A3B Instruct 2507, 4-bit | 235.3 s | 18.53 GB | 0 | 19 / 19 / 10 |
| Qwen3.6 35B-A3B, 4-bit | 279.0 s | 20.44 GB | 7 | 16 / 11 / 21 |

The 35B model's tokenizer/template differs, despite the same message contents. The 1.7B run had two invalid/truncated JSON batches; 4B/30B/35B had valid JSON but could still violate candidate constraints. These are protocol and runtime measurements, not accuracy rankings.

The 30B model followed the candidate-selection protocol most consistently in this small replay. The 35B model generated valid JSON but selected seven IDs that were not allowed for the particular segment, borrowing IDs from other segments in the same batch. Both larger models still proposed unsupported thematic associations. Raw proposals and guards are preserved separately. Match counts and self-rated support are not calibrated confidence or measured accuracy.

The combined-reference 35B run evaluated 42 rows from seven clips in **329.1 seconds**, peaking at **20.56 GB**. It used preserved tracker-v1 hints and was not rerun after the later service/boundary fixes (the current tracker is v4). It produced six candidate-constraint violations and five additional quote-validation rejections. The guarded result contains four matched, 20 uncertain, and 18 unknown rows; the other 914 transcript rows are explicitly untested by that LLM. All six sampled late-address rows ended UNKNOWN through validation/guards, although the model itself attempted some thematic matches. Even an accepted match had an inaccurate explanation of the Greek prayer; an existing quote and plausible location are insufficient to trust the model's linguistic explanation.

To test the larger end of what fits, a [Llama 3.3 70B 2-bit MLX conversion](https://huggingface.co/cnfusion/Llama-3.3-70B-Instruct-Q2-mlx) was downloaded, pinned, validated, and run on two short Greek alignment cases. It loaded in **8.1 seconds**, stayed within **22.51 GB peak MLX allocation**, and took **258.9 seconds total**. Generation was only **2.23–2.49 tokens/second**. Both cases degenerated into repeated text, reached the 180-token cap, and failed JSON validation. There were no usable alignment decisions.

That is a successful hardware-fit test and an unsuccessful task test of this particular conversion. Its hand-selected three-candidate pools and 745/825-token prompts are much smaller/easier than the main benchmark, so runtimes and decision counts are not a like-for-like model ranking. Greek is not one of the eight explicitly supported languages in [Meta's Llama 3.3 card](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct). The result does not establish how every 70B model or quantization would perform. The 32 GB Mac can therefore run some approximately 70B models with aggressive compression and short context; 30B–35B at four bits is the more useful tested fast range. A 70B four-bit model needs about 35 GB just for idealized quantized weights, before other tensors, cache, and the OS. No absolute size ceiling is claimed for lower precision or offloading.

The 70B probe also recorded 4.93 GB process RSS, which is a different accounting measure from MLX's GPU allocations. Mac-wide swap was already 21,763 MB before the probe and ended at 18,285.69 MB; these snapshots cannot isolate pressure from other applications or prove a clean no-swap run. No system memory settings were raised. Details and unedited responses are in `data/llama70b-hardware-probe.json`.

Model sources: [MLX Whisper Large v3](https://huggingface.co/mlx-community/whisper-large-v3-mlx), [Qwen 30B MLX](https://huggingface.co/mlx-community/Qwen3-30B-A3B-Instruct-2507-4bit), and [Qwen 35B MLX](https://huggingface.co/mlx-community/Qwen3.6-35B-A3B-4bit). Pinned larger-LLM revisions, file-size/header validation, raw prompts, responses, and benchmark details are saved in `data/large-model-inventory.json` and the comparison artifacts.

## Implications for the real-time ADS pilot

**Assessment: fully automatic, Greek-capable, offline phone-microphone tracking is a high-risk next step. These results do not establish that the proposed MVP will meet its cue-timing requirements.** The evidence supports continuing a focused feasibility test, with a spoken-anchor/manual-conductor fallback considered from the outset.

This assessment uses the supplied *Audio Descriptive Service (ADS) for the Divine Liturgy — Pilot Specification*, draft dated September 28, 2026, specifically “Phase 0,” “Test MVP definition,” and “Acceptance criteria.” Its target is an iPhone 16 or newer, built-in microphone from the pew, offline operation, and descriptions through Bluetooth headphones. English is first; Greek is conditional on Phase 0. Matins is useful in this experiment but outside that MVP's service scope. The specification is a requirements baseline, not independent evidence that its feasibility assumptions hold.

### Smaller models and speed

Whisper Small had visibly damaged Greek and missed the opening blessing in the controlled sample. With the same 24-minute sample and tracker, it associated 126.66 ASR-timestamped seconds with the reference, compared with 389.10 for Turbo and 342.10 for Large v3. This supports preferring Turbo for this prototype; it is **not** a measured accuracy difference. Missing the opening also affects downstream tracking, so the gap cannot be attributed entirely to word recognition. We did not test Tiny/Base or measure any Whisper model on an iPhone. “Smaller on-device models may struggle” is supported; “all phone-sized models fail” is not.

The larger models still made chant, repetition, and language errors even with well-microphoned online recordings. A phone in the pew adds distance, reverberation, background noise, and possible narration leakage; the size of that degradation remains unmeasured. The large local LLMs also made unsupported associations and do not provide a demonstrated remedy or a tested phone-compatible component.

Mac throughput is encouraging but does not settle live latency. Turbo processed the full first recording at 12.64× playback speed. However, our recognizer receives complete 30-second chunks: a cue near the beginning of a chunk could wait almost 30 seconds before inference even starts. An offline sequence path can additionally use words that occur after the cue. Neither that buffering nor future context fits a guaranteed 10-second live response. A streaming implementation needs short, overlapping incremental windows, explicit provisional/final decisions, and a tracker that uses only audio already heard; their quality and compute cost must be measured anew.

### What remains unproven against the specification

| Proposed requirement in the draft | What this experiment establishes |
|---|---|
| At least 90% of spoken key moments detected within 10 seconds | Not measured. Suggested sections lack independent ground-truth onsets and use offline context. |
| Fewer than one false trigger per liturgy | Not measured. Wrong associations exist; this viewer has no deployed cue scheduler. An association is not itself a narration trigger. |
| Re-anchor within 30 seconds of the next spoken part after chant | Not measured causally. Offline recovery can benefit from subsequent audio. |
| Real time on the test iPhone, acceptable 90-minute battery use; proposed acceptance threshold below 40% battery | No iPhone timing, sustained thermal, battery, or capture/playback tests have been performed. |
| Avoid narrating over Gospel, homily, or words of institution except at Full verbosity | No live gap detection or narration scheduler has been evaluated. UNKNOWN alone does not identify a safe gap. |
| 4–6 complete pew recordings, 30–40 independently marked moments each, two English translations plus a held-out translation | Four online recordings from two channels were processed. They do not fulfill the pew-recording, annotation, or translation-generalization requirements. |

The document's script-following idea is useful, but “fixed order” and “knowing the next language” should be treated as priors. Actual services omit or repeat text, vary the order, alternate Greek and English, and include rites or speech outside the supplied reference. Some cues concern actions whose onset is not uniquely identified by audible words. A conservative live tracker must abstain, tolerate variants, and avoid turning a weak thematic match into an instruction to the listener.

### Recommended next feasibility gate

Replay the original recording at playback speed into a **causal** tracker, logging the wall-clock time when each cue decision becomes available, not merely the earlier ASR timestamp assigned to it. Independently annotate 30–40 key moments and out-of-reference stretches, then measure missed cues, false triggers, late decisions, and recovery. Use the draft's proposed timing/false-trigger thresholds as the gate, reported separately for spoken English, spoken Greek, and chant. Tune on the first recording and freeze the configuration before evaluating other recordings.

If that passes, repeat on the target iPhone with actual pew recordings, the selected headphones, concurrent narration, language switches, translation variants, and a full 90-minute battery/thermal run. Preserve manual section selection and consider the draft's conductor mode if automatic chant tracking remains weak. A parish computer with a direct audio feed is another promising path to test, but changes the phone-only MVP architecture and does not eliminate recognition or cue-timing uncertainty.

## Verification and limits

The original three recordings share one channel; the fourth comes from a second parish/channel. This small set does not establish robustness across parishes or acoustic conditions. The experiment does not isolate the effect of older Greek vocabulary and grammar from chanting, recording conditions, or language switching. Phone microphones, controlled far-field/noise/reverberation tests, real-time latency, battery usage, and mobile deployment remain untested. No fine-tuning has been performed.

The viewer uses the chosen Turbo plus sequence configuration and includes raw subtitles, canonical text, clickable section suggestions, source notices, and a review form. Historical independent-text and LLM comparisons remain in saved experiment artifacts. Reviewers can enter a transcript based on listening and judge the proposed occurrence. Printed canonical text should not be copied into the ground-truth field without checking what was actually spoken or sung.


The regression suite passed 84 tests and 12 subtests. Focused browser-script tests cover playback, transcript following, and review isolation; the live browser was checked for recording/run selection, section seeking, reference highlighting, and raw subtitles. See GREEK-EXAMPLES.md for eight exact illustrated comparisons and COLLABORATOR-SUMMARY.txt for a forwardable summary.
