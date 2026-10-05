# Findings

A preliminary local test of following Matins and the Divine Liturgy.

> **Main takeaway:** Current models look promising for locating passages and following the service, but we should not promise reliable verbatim Greek subtitles, especially for chanting.

## The working approach

Working approach: transcribe the recording locally with Whisper Large v3 Turbo, retrieve candidate passages from the relevant Greek/English GOA service text, and use a sequence-aware matcher to follow plausible progress while allowing skips, small reversals, and unknown passages. Save the predictions and show the raw transcript, canonical text, and clickable section locations alongside the video. The current approach uses no LLM at playback time and no live inference; matching is computed offline and can use later context.

## Choosing the speech recognition model

We compared Whisper Small, Large v3 Turbo, and non-turbo Large v3 on the same 24 minutes of the first recording, and ran both larger models on that complete recording. All inference ran locally with MLX on an Apple M5 MacBook Air with 32 GB memory. Turbo transcribed the full 128-minute recording in about 10 minutes; non-turbo Large v3 took 23 minutes. Large v3 improved some phrases but was worse elsewhere, with no consistent Greek advantage. Turbo is the chosen configuration for the other recordings.

## Greek speech and chant

Spoken, formulaic liturgical Greek often retains enough correct words to identify a prayer. Chant produces more substitutions, omissions, unrelated repetitions, mistaken language detection, and sometimes Greek rendered in Latin characters. English is usually more readable, but sung English also has errors. A targeted forced-Greek retry recovered the Small Entrance where automatic language detection had failed; this was a selected diagnostic example, not evidence of a general improvement.

## What a text match tells us

Matching is not the same as accurate transcription. We compare the raw ASR against bilingual service text and track plausible progress through Matins and the Liturgy, allowing repetitions, skips, limited backward movement, and unmatched passages. A correct location can be recovered from a poor transcript. Repeated phrases and rites absent from the reference can also cause wrong section assignments. Greek contributes many of the original video's associations, so this is not just an English result. Canonical text is displayed separately rather than substituted for the model's words.

## Larger local language models

Four-bit 30B and 35B local LLMs fit and run at useful speeds, but still make unsupported associations and mistakes explaining Greek. A heavily compressed 70B model also fit, but was slow and produced unusable answers in two short probes. The current default therefore uses Turbo plus the sequence-aware text matcher.

## What remains unmeasured

This is a text-based qualitative review against plausible service passages, not independently transcribed listening ground truth. Match counts and similarity scores are not word accuracy. We cannot attribute the errors solely to older Greek vocabulary rather than chanting, acoustics, or language switching. The next useful evaluation is a small independently annotated audio set spanning spoken Greek, Greek chant, English, language switches, and sermons. These recordings do not yet establish performance with a distant phone microphone, background noise, or real-time operation.

## Real-time implications for the ADS pilot

The September 28 pilot specification calls for offline iPhone 16-or-newer operation using a phone microphone in the pew. Its proposed Phase 0 targets include at least 90% of spoken key moments within 10 seconds, fewer than one false trigger per service, recovery at the next spoken passage within 30 seconds, and acceptable 90-minute battery use (below 40% in the proposed acceptance criteria). None has been validated here.

Fully automatic Greek-capable tracking under those conditions looks difficult. Small had damaged Greek and missed the opening in our controlled sample, but we have not established that all smaller models or iPhone implementations would fail. Even Turbo and Large v3 struggled with chant in good audio. Poorer pew acoustics could make that harder. The specification's English-first scope is more promising to test, but English tracking still needs independently timed evaluation.

Fast offline processing does not imply timely live cues: our 30-second input chunks can already exceed a 10-second cue budget, and our matcher uses future context. Short incremental audio windows and a causal tracker must be evaluated separately on the actual phone. A local LLM has not been shown to solve these failures.

The next gate should be a causal replay with 30–40 human-timed key moments per recording, followed by real pew recordings and sustained iPhone battery/thermal tests. Measure actual decision delay, false triggers, missed moments, and recovery; do not count printed-text agreement as accuracy. Keep spoken-anchor tracking and manual/conductor assistance as practical fallbacks. A direct-feed parish computer is also worth testing if the phone-only target proves too restrictive.

## Additional Dormition test — August 9, 2026

The full 10th Sunday of Matthew recording (142.9 minutes) was processed with the same Turbo + sequence configuration in 9.2 inference minutes. It yielded 1669 raw segments, 288 accepted associations, and 29 suggested sections (15 Matins, 14 Liturgy). Accepted ASR labels were 72 Greek and 216 English; 34 raw segments carried subtitle/promotion artifact warnings. Dated GOA August 9, 2026 texts are used; the recording date is inferred from title/release metadata. These are association counts, not word accuracy, and the service begins during Matins. No model retuning or LLM pass was used.

Read the [detailed results](RESULTS.html) for the measurements, reference caveats, and full limitations, or [Help](HELP.html) to use the viewer.
