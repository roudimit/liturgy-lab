from liturgy_lab.evaluate import evaluate_moments, evaluate_reviews, normalize_words
from liturgy_lab.review_context import prediction_context, reference_for_run


def bound_review(session, *, alignment='lexical', **values):
    run = session['runs'][0]
    segment = run['segments'][0]
    context = prediction_context(session.get('source', {}).get('id', 'default'), run, segment,
                                 alignment, reference_for_run(session, run))
    return {'run_id': run['id'], 'segment_id': str(segment['id']), 'alignment': alignment,
            'prediction_fingerprint': context['prediction_fingerprint'], **values}

def test_no_annotations_never_claims_accuracy():
    assert evaluate_moments([],[])['recall_within_tolerance'] is None
    assert evaluate_reviews({'runs':[]},[])['by_run']=={}

def test_timestamp_tolerance_and_duplicate_annotations():
    segs=[{'start':100,'match':{'section_id':'a','status':'matched'}},
          {'start':105,'match':{'section_id':'a','status':'matched'}},
          {'start':200,'match':{'section_id':'b','status':'uncertain'}}]
    r=evaluate_moments(segs,[{'section_id':'a','time':90},{'section_id':'a','time':100},{'section_id':'b','time':200}])
    assert r['detected']==1
    assert r['recall_within_tolerance']==1/3

def test_wer_uses_human_text_not_liturgy_match():
    s={'runs':[{'id':'r','segments':[{'id':1,'text':'Lord have mercy'}]}]}
    result=evaluate_reviews(s,[bound_review(s, verdict='matched', reference_transcript='Lord have mercy on us')])
    assert result['by_run']['r']['normalized_wer']==2/5
    assert normalize_words('Κύριε, ἐλέησον.')=='κυριε ελεησον'


def test_current_accuracy_never_counts_unbound_or_stale_verdicts():
    session = {'source': {'id': 'video'}, 'reference': {'reference_id': 'ref-1'},
               'runs': [{'id': 'same-run', 'reference_id': 'ref-1', 'alignment': {'version': 1},
                         'segments': [{'id': 1, 'text': 'Lord have mercy', 'sequence_match': {'status': 'matched', 'unit_id': 'u1'}}]}]}
    legacy = {'recording_id': 'video', 'run_id': 'same-run', 'segment_id': '1', 'alignment': 'sequence',
              'verdict': 'matched', 'reference_transcript': 'Preserved older listening transcript'}
    first = bound_review(session, alignment='sequence', verdict='matched', reference_transcript='Lord have mercy')
    initial = evaluate_reviews(session, [legacy, first])
    assert initial['by_run']['same-run:sequence']['reviewed_segments'] == 1
    assert initial['excluded_reviews']['unbound_historical'] == 1
    session['runs'][0]['alignment']['version'] = 2
    stale = evaluate_reviews(session, [legacy, first])
    assert stale['by_run'] == {}
    assert stale['excluded_reviews']['changed_prediction'] == 1
    current = bound_review(session, alignment='sequence', verdict='incorrect', reference_transcript='Lord have mercy on us')
    result = evaluate_reviews(session, [legacy, first, current])
    assert result['by_run']['same-run:sequence']['reviewed_match_fraction'] == 0
    assert result['by_run']['same-run:sequence']['normalized_wer'] == 2/5
    session['runs'][0]['reference_id'] = 'ref-2'
    assert evaluate_reviews(session, [current])['by_run'] == {}
    assert legacy['reference_transcript'] == 'Preserved older listening transcript'
