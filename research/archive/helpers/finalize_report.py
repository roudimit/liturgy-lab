import json
from collections import Counter
from pathlib import Path

WORK = Path(__file__).resolve().parent
PROJECT = Path(__file__).resolve().parents[2]
summary = json.loads((PROJECT / 'data/experiment-summary.json').read_text())
records = {r['id']: r for r in summary['recordings']}
order = ['MIxJvLfaynY', 'vkkeLmltf_4', 'IuZ8WRk-POI', 'n674zECLjTI']
labels = ['September 8 / original', 'December 14 / 11th Sunday of Luke',
          'March 29 / St. Mary of Egypt', 'December 28 / new recording']
lines = [
    '## Completed recordings and viewer',
    '',
    'All four videos have a complete Turbo ASR pass. Model comparisons were confined to the first video; the other three received one Turbo pass, followed by the same sequence matcher. The final matcher version is v4. These section counts measure suggested coverage, not verified accuracy or exact section onsets.',
    '',
    '| Recording | Audio processed | Turbo inference | Suggested Matins sections | Suggested Liturgy sections | Total sections |',
    '|---|---:|---:|---:|---:|---:|',
]
language_lines = []
for recording_id, label in zip(order, labels):
    record = records[recording_id]
    run = next(r for r in record['runs'] if r['id'] == record['default_run'])
    assert run['complete_asr_coverage'], recording_id
    counts = Counter(s['service_id'] for s in run['sections'])
    metrics = run['asr_metrics']
    lines.append(f"| {label} | {metrics['audio_seconds']/60:.1f} min | {metrics['inference_seconds']/60:.1f} min | {counts['matins']} | {counts['liturgy']} | {run['suggested_sections']} |")
    langs = run['associated_by_asr_language']
    other = sum(n for lang, n in langs.items() if lang not in ('el', 'en'))
    language_lines.append(f"| {label} | {langs.get('el', 0)} | {langs.get('en', 0)} | {other} | {run['associated_segments']} |")
lines += [
    '',
    'Additional-recording timings sum saved contiguous hour blocks, including their loading/compilation work. Some blocks were cached from earlier runs; these totals are not a repeated, controlled speed benchmark. Complete audio coverage means the entire recording was submitted to ASR; it does not mean the recognizer emitted words everywhere.',
    '',
    '| Recording | Associated segments from Greek-labeled chunks | From English-labeled chunks | Other language labels | Total associated segments |',
    '|---|---:|---:|---:|---:|',
    *language_lines,
    '',
    'Language labels are Whisper predictions, not independently verified language. Segment counts are comparable for inspecting one fixed transcript, but should not be used to rank ASR models with different segmentation.',
    '',
    'The original video now has 18 Liturgy section suggestions plus 31 Matins suggestions. Its default Turbo run finds Trisagion material but still misses Small Entrance; that passage is available in the separately labeled, selected forced-Greek retry. The new recording has distinctive Small Entrance and Entrance Hymn anchors at 1:00:02.78 and 1:01:30.00 respectively.',
    '',
    'For December 14, no opening blessing was recognized. Its first supported Liturgy anchor is Antiphon 2 at 1:32:00, although shared litany text occurs earlier. The service-jump button is therefore a first suggested location, not an estimate of when the Liturgy truly began. The inspected sermon (7057–7832 s), announcements (12034–12652 s), and later forty-day blessing material remained unassociated. The new recording’s closing address/sermon probe from 7140 s onward also remained unassociated. These probes were chosen from emitted text, not independently annotated audio.',
    '',
    '**Known failure in the St. Mary recording:** the later Memorial rite is absent from its St. Basil reference. Five shared prayer fragments, totaling 11.22 ASR-timestamped seconds around 10502–11043 s, are incorrectly associated with Dismissal. These predictions remain in the results rather than being manually removed to improve the counts. The opening blessing was detected at 5269.42 s; inspected sermon material (6625–7691 s) and closing announcements (11113 s onward) have no accepted associations. Details and raw examples are saved in data/full-recording-audit-IuZ8WRk-POI.json.',
    '',
    'Some accurately recognizable priest prayers also remain unmatched because retrieval currently excludes reference units tagged inaudible, even when the recording microphone captures them. For example, the prayer beginning “No one bound by worldly desires” around 7727.58 s corresponds to liturgy:u0136. This is a reference/retrieval limitation, so an unmatched segment is not necessarily an ASR failure. These final audit findings were documented without changing the frozen matcher or rerunning model comparisons.',
    '',
    'The viewer now follows both the raw transcript and bilingual reference as audio advances or a section is selected. Turning off Follow audio, or searching a panel, allows manual reading. Run-specific references and review fingerprints prevent old decisions from silently attaching to changed predictions. No human review labels were manufactured.',
    '',
]
draft = (WORK / 'report/results-draft.md').read_text()
draft = draft.replace('## Larger local LLMs', '\n'.join(lines) + '\n## Larger local LLMs')
draft += '\n\nThe regression suite passed 84 tests and 12 subtests. Focused browser-script tests cover playback, transcript following, and review isolation; the live browser was checked for recording/run selection, section seeking, reference highlighting, and raw subtitles. See GREEK-EXAMPLES.md for eight exact illustrated comparisons and COLLABORATOR-SUMMARY.txt for a forwardable summary.\n'
(PROJECT / 'RESULTS.md').write_text(draft)
print('Updated RESULTS.md with all four complete recordings.')
