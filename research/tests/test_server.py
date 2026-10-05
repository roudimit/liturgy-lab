import json
import pytest
from fastapi.testclient import TestClient
from liturgy_lab import server

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server,'DATA',tmp_path)
    (tmp_path/'media').mkdir()
    (tmp_path/'media/video.mp4').write_bytes(b'0123456789')
    records=[{'id':'a','title':'A','session_file':'a.json','media_file':'video.mp4'},
             {'id':'b','title':'B','session_file':'b.json','media_file':'video.mp4'}]
    (tmp_path/'recordings.json').write_text(json.dumps(records))
    for name in ('a','b'):
        (tmp_path/(name+'.json')).write_text(json.dumps({'source':{'id':name},'runs':[{'id':'r','segments':[{'id':1,'text':'Κύριε','llm_match':{'status':'not_run'}}]}]}))
    with TestClient(server.app) as c:yield c

def test_range_support_and_media_allowlist(client):
    r=client.get('/media/video.mp4',headers={'Range':'bytes=2-5'})
    assert r.status_code==206 and r.content==b'2345'
    assert client.get('/media/secret.mp4').status_code==404
    assert client.get('/api/session?recording=missing').status_code==404

def test_reviews_are_scoped_and_upserted(client):
    review={'recording_id':'a','run_id':'r','segment_id':'1','verdict':'unknown','reference_transcript':'Κύριε ἐλέησον'}
    assert client.post('/api/reviews',json=review).status_code==200
    assert client.post('/api/reviews',json={**review,'verdict':'incorrect'}).status_code==200
    assert client.post('/api/reviews',json={**review,'recording_id':'b'}).status_code==200
    saved=client.get('/api/reviews').json()['reviews']
    assert len(saved)==2 and saved[0]['verdict']=='incorrect'
    assert saved[1]['reference_transcript']=='Κύριε ἐλέησον'

def test_external_origin_and_unknown_fields_are_rejected(client):
    r={'run_id':'r','segment_id':'1','verdict':'unknown'}
    assert client.post('/api/reviews',json=r,headers={'Origin':'https://example.com'}).status_code==403
    assert client.post('/api/reviews',json={**r,'path':'/tmp/wrong'}).status_code==422
    assert client.post('/api/reviews',json={**r,'alignment':'llm'}).status_code==422

def test_no_real_predictions_are_invented(client):
    s=client.get('/api/session?recording=b').json()
    assert s['source']['id']=='b'
    assert s['runs'][0]['segments'][0]['text']=='Κύριε'


def test_local_ui_assets_cannot_remain_stale_after_a_rebuild(client):
    assert client.get('/').headers['cache-control'] == 'no-store'
    assert client.get('/static/app.js').headers['cache-control'] == 'no-store'
    assert client.get('/static/style.css').headers['cache-control'] == 'no-store'


def test_sequence_review_requires_a_sequence_prediction(client):
    review = {'recording_id':'a','run_id':'r','segment_id':'1','verdict':'unknown','alignment':'sequence'}
    assert client.post('/api/reviews',json=review).status_code == 422
    path = server.DATA / 'a.json'
    session = json.loads(path.read_text())
    session['runs'][0]['segments'][0]['sequence_match'] = {'status':'uncertain'}
    path.write_text(json.dumps(session))
    assert client.post('/api/reviews',json=review).status_code == 200
    assert client.get('/api/reviews').json()['reviews'][0]['alignment'] == 'sequence'


def test_rebuilt_prediction_isolates_old_verdicts_without_changing_user_text(client):
    path = server.DATA / 'a.json'
    session = json.loads(path.read_text())
    session['reference'] = {'reference_id': 'ref-1', 'units': [{'id': 'u1', 'greek': 'Κύριε', 'english': 'Lord'}]}
    run = session['runs'][0]
    run.update(reference_id='ref-1', alignment={'method': 'sequence', 'version': 1})
    run['segments'][0]['sequence_match'] = {'status': 'matched', 'unit_id': 'u1', 'method': 'sequence'}
    path.write_text(json.dumps(session))
    legacy = {'recording_id': 'a', 'run_id': 'r', 'segment_id': '1', 'alignment': 'sequence',
              'verdict': 'matched', 'reference_transcript': 'Legacy text: Ἀμήν.\nDo not change this.'}
    (server.DATA / 'reviews.json').write_text(json.dumps([legacy]))
    def fingerprint():
        return client.get('/api/session?recording=a').json()['runs'][0]['segments'][0]['review_fingerprints']['sequence']
    first = fingerprint()
    submitted = {**legacy, 'prediction_fingerprint': first, 'reference_transcript': 'First annotation: Κύριε ἐλέησον.'}
    response = client.post('/api/reviews', json=submitted)
    assert response.status_code == 200
    assert response.json()['review']['alignment_version'] == 1
    assert response.json()['review']['reference_id'] == 'ref-1'
    assert client.get('/api/reviews').json()['reviews'][0] == legacy
    # The filename, run and segment IDs remain unchanged through this rebuild.
    run['alignment']['version'] = 2
    path.write_text(json.dumps(session))
    second = fingerprint()
    assert second != first
    before = (server.DATA / 'reviews.json').read_bytes()
    assert client.post('/api/reviews', json=submitted).status_code == 409
    assert (server.DATA / 'reviews.json').read_bytes() == before
    current = {**submitted, 'prediction_fingerprint': second, 'verdict': 'incorrect', 'reference_transcript': 'Second annotation, unchanged.'}
    assert client.post('/api/reviews', json=current).status_code == 200
    saved = client.get('/api/reviews/export').json()['reviews']
    assert len(saved) == 3
    assert saved[0] == legacy
    assert [r['reference_transcript'] for r in saved] == [legacy['reference_transcript'], submitted['reference_transcript'], current['reference_transcript']]
    # Reference changes and a changed decision independently invalidate context.
    run['reference_id'] = 'ref-2'
    path.write_text(json.dumps(session))
    third = fingerprint()
    assert third != second
    run['segments'][0]['sequence_match']['status'] = 'unknown'
    path.write_text(json.dumps(session))
    assert fingerprint() != third
