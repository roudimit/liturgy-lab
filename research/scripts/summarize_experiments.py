"""Make a compact inventory of completed viewer experiments (not accuracy)."""
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    recordings = []
    for path in sorted(DATA.glob('session*.json')):
        session = read(path)
        if not isinstance(session, dict) or 'runs' not in session:
            continue
        source = session['source']
        runs = []
        for run in session['runs']:
            rows = run['segments']
            is_llm = any(row.get('llm_match') for row in rows)
            field = 'llm_match' if is_llm else 'sequence_match'
            accepted = [row for row in rows if (row.get(field) or {}).get('status') == 'matched']
            reference = session['references'][run['reference_id']]
            units = {unit['id']: unit for unit in reference['units']}
            sections = {}
            for row in accepted:
                match = row[field]
                unit = units[match['unit_id']]
                section_id = match['section_id']
                sections.setdefault(section_id, {
                    'id': section_id, 'title': match['section_title'],
                    'service_id': unit.get('service_id'), 'first_suggestion': row['start']})
            runs.append({
                'id': run['id'], 'label': run['label'], 'reference_id': run['reference_id'],
                'complete_asr_coverage': run.get('complete', False),
                'model': run.get('model'), 'llm_model': run.get('llm_model'),
                'asr_metrics': run.get('metrics'), 'llm_metrics': run.get('llm_metrics'),
                'segments': len(rows), 'status_counts': dict(Counter((r.get(field) or {}).get('status', 'not_run') for r in rows)),
                'associated_segments': len(accepted), 'suggested_sections': len(sections),
                'associated_by_asr_language': dict(Counter(r.get('language', 'unknown') for r in accepted)),
                'segments_by_asr_language': dict(Counter(r.get('language', 'unknown') for r in rows)),
                'associated_by_service': dict(Counter(units[r[field]['unit_id']].get('service_id', 'legacy_liturgy') for r in accepted)),
                'sections': sorted(sections.values(), key=lambda s: s['first_suggestion']),
                'intervals': run.get('intervals'),
            })
        recordings.append({'id': source.get('id', path.stem), 'title': source['title'],
                           'duration': source['duration'], 'session': path.name,
                           'reference_selection': session['reference'].get('selection'),
                           'default_run': session['default_run'], 'runs': runs})
    result = {'meaning': 'Completed artifacts and model association coverage; not accuracy, WER, precision, or recall.',
              'limitations': ['Language categories use ASR predictions, not human labels.',
                              'Section timestamps are the first accepted fragment, not verified section onsets.',
                              'LLM runs may have full underlying ASR but only selected rows were evaluated by the LLM.'],
              'recordings': recordings}
    out = DATA / 'experiment-summary.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for recording in recordings:
        primary = next(r for r in recording['runs'] if r['id'] == recording['default_run'])
        print(f"{recording['title']}: {primary['segments']} segments; "
              f"{primary['associated_segments']} associations; {primary['suggested_sections']} sections; "
              f"full ASR={primary['complete_asr_coverage']}")


if __name__ == '__main__':
    main()
