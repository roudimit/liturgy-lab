from pathlib import Path
import json
from collections import Counter
import sys,re
project=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(project/'scripts'))
from align_sequence import summarize
video='ZUMoL5VwJzw'
session=json.loads((project/f'data/session-{video}.json').read_text())
run=session['runs'][0]; ref=session['reference']; rows=run['segments']; metrics=run['metrics']
elapsed=json.loads((project/f'data/session-build-timing-{video}.json').read_text())['elapsed_seconds']
report=summarize(rows,ref,elapsed)
report['elapsed_description']='Session assembly wall time, including sequence alignment, serialization, and validation.'
# Session assembly timing is recorded by the caller separately; coverage is unaffected.
(project/f'data/sequence-audit-{video}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
accepted=[s for s in rows if s['match']['status']=='matched']
sections=report['sections_with_predictions']
services=Counter(s['service_id'] for s in sections)
langs=Counter(s.get('language','unknown') for s in accepted)
warnings=sum(bool(s.get('asr_warnings')) for s in rows)
audio=metrics['audio_seconds']/60; minutes=metrics['inference_seconds']/60
count=len(sections)
addition=f'''## Added Dormition recording — August 9, 2026

The [10th Sunday of Matthew recording](https://www.youtube.com/watch?v={video}) from Dormition, Somerville, MA, was processed in full with the frozen **Whisper Large v3 Turbo + sequence matcher v4** configuration. No additional LLM, forced-language retry, or matcher tuning was used for this recording. The recording starts during Matins rather than at its beginning.

The service date is inferred from the video title and matching August 9, 2026 release/upload metadata. The [dated GOA Matins](https://dcs.goarch.org/goa/dcs/h/s/2026/08/09/ma/gr-en/index.html), Matins ordinary, and [dated Chrysostom Liturgy](https://dcs.goarch.org/goa/dcs/h/s/2026/08/09/li/gr-en/index.html) form a {len(ref['units'])}-unit bilingual reference. Local order, abbreviations, and spoken variants remain unverified.

| Measurement | Result |
|---|---:|
| Complete audio submitted | {audio:.1f} minutes |
| Turbo inference, including model load/compilation | {minutes:.1f} minutes ({metrics['speedup']:.2f}× playback) |
| Raw transcript segments | {len(rows)} |
| Associated segments | {len(accepted)} |
| Suggested Matins / Liturgy sections | {services['matins']} / {services['liturgy']} |
| Total suggested sections | {count} |
| Associated Greek-labeled / English-labeled segments | {langs['el']} / {langs['en']} |
| Segments flagged for possible subtitle/promotion artifacts | {warnings} |

These are model association and runtime measurements, **not transcription accuracy or independently verified section timing**. Chant still produces substitutions, repetitions, and spurious subtitle-credit text. The raw transcript is preserved; the printed service text does not replace it. Language labels come from ASR and can be wrong. The recording was evaluated with the same settings as the prior recordings, but the timing is a single run, not a controlled comparison. Downloads and audio decoding are excluded from inference timing.

'''
p=project/'RESULTS.md';text=p.read_text()
if True:
 if '## Added Dormition recording — August 9, 2026' in text:
  text=re.sub(r'## Added Dormition recording — August 9, 2026.*?(?=## What to tell collaborators)',lambda m:addition,text,flags=re.S)
 else: text=text.replace('## What to tell collaborators\n',addition+'## What to tell collaborators\n')
 text=re.sub(r'^\| August 9 / 10th Sunday of Matthew.*min.*$',lambda m:f'| August 9 / 10th Sunday of Matthew | {audio:.1f} min | {minutes:.1f} min | {services["matins"]} | {services["liturgy"]} | {count} |',text,flags=re.M)
 text=re.sub(r'^\| August 9 / 10th Sunday of Matthew \| (?!.*min)[0-9]+.*$',lambda m:f'| August 9 / 10th Sunday of Matthew | {langs["el"]} | {langs["en"]} | {len(accepted)-langs["el"]-langs["en"]} | {len(accepted)} |',text,flags=re.M)
 text=text.replace('applied to all four recordings','applied to all five recordings')
 text=text.replace('All four videos have a complete Turbo ASR pass.','All five videos have a complete Turbo ASR pass.')
 text=text.replace('the other three received one Turbo pass','the other four received one Turbo pass')
 text=text.replace('| December 28 / new recording | 148.6 min | 16.0 min | 12 | 21 | 33 |',f'| December 28 / Sunday After Nativity | 148.6 min | 16.0 min | 12 | 21 | 33 |\n| August 9 / 10th Sunday of Matthew | {audio:.1f} min | {minutes:.1f} min | {services["matins"]} | {services["liturgy"]} | {count} |')
 text=text.replace('| December 28 / new recording | 40 | 359 | 0 | 399 |',f'| December 28 / Sunday After Nativity | 40 | 359 | 0 | 399 |\n| August 9 / 10th Sunday of Matthew | {langs["el"]} | {langs["en"]} | {len(accepted)-langs["el"]-langs["en"]} | {len(accepted)} |')
 text=text.replace('Four online recordings from two channels were processed.','Five online recordings from two channels were processed.')
 text=text.replace('the fourth comes from a second parish/channel.','the fourth and fifth come from a second parish/channel.')
 p.write_text(text)
p=project/'COLLABORATOR-SUMMARY.txt';text=p.read_text()
if True:
 text=text.split('\n\nAdditional Dormition test — August 9, 2026')[0]
 text+=f'\n\nAdditional Dormition test — August 9, 2026\n\nThe full 10th Sunday of Matthew recording ({audio:.1f} minutes) was processed with the same Turbo + sequence configuration in {minutes:.1f} inference minutes. It yielded {len(rows)} raw segments, {len(accepted)} accepted associations, and {count} suggested sections ({services["matins"]} Matins, {services["liturgy"]} Liturgy). Accepted ASR labels were {langs["el"]} Greek and {langs["en"]} English; {warnings} raw segments carried subtitle/promotion artifact warnings. Dated GOA August 9, 2026 texts are used; the recording date is inferred from title/release metadata. These are association counts, not word accuracy, and the service begins during Matins. No model retuning or LLM pass was used.\n'
 p.write_text(text)
p=project/'README.md';text=p.read_text().replace('The viewer shows four recordings','The viewer shows five recordings')
p.write_text(text)
for base in [project/'share-template',project/'share-template/site']:
 for name in ['START-HERE.txt','PUBLISH-GITHUB-PAGES.txt']:
  p=base/name
  if p.exists(): p.write_text(p.read_text().replace('four recordings','five recordings').replace('all four recording','all five recording'))
print(json.dumps({'audio_minutes':audio,'inference_minutes':minutes,'segments':len(rows),'associated':len(accepted),'sections':count,'services':dict(services),'languages':dict(langs),'warnings':warnings},indent=2))
