"""Measure only human-annotated evidence; never report match coverage as accuracy."""
import re
import unicodedata
from .review_context import prediction_context, reference_for_run

def normalize_words(text):
    # Polytonic accents are ignored; spelling and word differences still count.
    text = ''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[^\W_]+', text.replace('ς', 'σ'), re.UNICODE))

def evaluate_reviews(session, reviews):
    from jiwer import process_words
    if isinstance(reviews, dict):
        reviews = reviews.get('reviews', list(reviews.values()))
    if isinstance(reviews, dict):
        reviews = list(reviews.values())
    lookup = {(str(r['id']), str(s['id'])): (r, s) for r in session['runs'] for s in r['segments']}
    recording = session.get('source', {}).get('id')
    valid = []
    excluded = {'unbound_historical': 0, 'changed_prediction': 0, 'other_recording_or_run': 0}
    for review in reviews:
        pair = lookup.get((str(review.get('run_id')), str(review.get('segment_id'))))
        if pair is None or (recording and review.get('recording_id', recording) != recording):
            excluded['other_recording_or_run'] += 1
            continue
        if not review.get('prediction_fingerprint'):
            excluded['unbound_historical'] += 1
            continue
        run, segment = pair
        context = prediction_context(str(recording or review.get('recording_id') or 'default'), run, segment,
                                     review.get('alignment', 'lexical'), reference_for_run(session, run))
        if review['prediction_fingerprint'] != context['prediction_fingerprint']:
            excluded['changed_prediction'] += 1
            continue
        valid.append(review)
    groups = {}
    for review in valid:
        alignment = review.get('alignment', 'lexical')
        key = str(review['run_id']) + (':' + alignment if alignment != 'lexical' else '')
        group = groups.setdefault(key, {'reviewed_segments': 0, 'matched': 0, 'incorrect': 0, 'unknown': 0,
                                         'wer_annotated_segments': 0, 'reference_words': 0, 'word_errors': 0})
        group['reviewed_segments'] += 1
        verdict = review.get('verdict', 'unknown')
        if verdict in ('matched', 'incorrect', 'unknown'):
            group[verdict] += 1
        reference = review.get('reference_transcript', '').strip()
        if reference:
            _, segment = lookup[(str(review['run_id']), str(review['segment_id']))]
            result = process_words(normalize_words(reference), normalize_words(segment['text']))
            group['wer_annotated_segments'] += 1
            group['reference_words'] += result.hits + result.substitutions + result.deletions
            group['word_errors'] += result.substitutions + result.deletions + result.insertions
    for g in groups.values():
        judged = g['matched'] + g['incorrect']
        g['reviewed_match_fraction'] = g['matched'] / judged if judged else None
        g['normalized_wer'] = g['word_errors'] / g['reference_words'] if g['reference_words'] else None
    return {'by_run': groups, 'excluded_reviews': excluded,
            'note': 'Only reviews with the current prediction fingerprint are counted. Unbound and changed-prediction reviews remain historical. These reviewed samples are not a representative accuracy estimate. WER requires a human transcript made by listening to the audio; liturgy text is not ground truth.'}

def evaluate_moments(segments, ground_truth, tolerance=10, method='match'):
    """ground_truth=[{section_id,time}] must be independent human annotations.

    Evaluate section transitions, not every subtitle. Greedily match each annotation
    once, then report unmatched predicted transitions as false positives.
    """
    if tolerance < 0:
        raise ValueError('tolerance must be nonnegative')
    predictions = []
    previous = None
    for seg in sorted(segments, key=lambda s: s['start']):
        m = seg.get(method) or {}
        current = m.get('section_id') if m.get('status') in ('matched', 'accepted') else None
        if current is not None and current != previous:
            predictions.append({'section_id': current, 'time': seg['start']})
            previous = current
    used, details = set(), []
    for truth in ground_truth:
        options = [(abs(p['time']-truth['time']), i, p) for i,p in enumerate(predictions)
                   if i not in used and p['section_id'] == truth['section_id']]
        nearest = min(options, default=None)
        found = nearest is not None and nearest[0] <= tolerance
        if found:
            used.add(nearest[1])
        details.append({**truth, 'detected_within_tolerance': found,
                        'error_seconds': nearest[2]['time']-truth['time'] if nearest else None})
    hits = sum(d['detected_within_tolerance'] for d in details)
    return {'annotated_moments': len(details), 'detected': hits,
            'recall_within_tolerance': hits/len(details) if details else None,
            'unmatched_predicted_transitions': len(predictions)-len(used),
            'tolerance_seconds': tolerance, 'details': details,
            'note': 'Unmatched predictions are false positives only if annotations exhaustively cover the evaluated interval.'}
