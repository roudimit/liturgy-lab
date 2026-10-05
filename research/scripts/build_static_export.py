"""Export the frozen default runs and viewer to a dependency-free static site."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import re

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('project',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    src=args.project; out=args.destination; site=out/'site'
    templates=src/'share-template'
    if templates.is_dir(): shutil.copytree(templates,out,dirs_exist_ok=True)
    (site/'assets').mkdir(parents=True,exist_ok=True)
    (site/'reports').mkdir(exist_ok=True)
    records=json.loads((src/'data/recordings.json').read_text())
    data={'recordings':[], 'sessions':{}}
    source_fields={'id','title','duration','webpage_url','reference_url','reference_date','caveat','preview_start','reference_status','experiment_note'}
    run_fields={'model','language_mode','chunk_seconds','start','end','metrics','notes','reference_id','alignment','intervals','id','label','complete','opening_detection'}
    segment_fields={'id','start','end','text','language','sequence_match','match','asr_warnings'}
    for record in records:
        session=json.loads((src/'data'/record['session_file']).read_text())
        run=next(r for r in session['runs'] if r['id']==session['default_run'])
        ref=copy.deepcopy(session.get('references',{}).get(run['reference_id'],session['reference']))
        chosen={k:v for k,v in run.items() if k in run_fields}
        chosen['segments']=[{k:v for k,v in s.items() if k in segment_fields} for s in run['segments']]
        data['recordings'].append({k:record[k] for k in ('id','title')})
        data['sessions'][record['id']]={'source':{k:v for k,v in session['source'].items() if k in source_fields},'reference':ref,'runs':[chosen],'default_run':chosen['id']}
    # Source provenance stays intact; local paths and historical private reviews do not ship.
    def sanitize(value):
        if isinstance(value,dict):
            return {k:sanitize(v) for k,v in value.items() if k not in {'path','local_path','source_path','cache_path','source_file','source_asr_file'} and not k.endswith('_path')}
        if isinstance(value,list): return [sanitize(v) for v in value]
        if isinstance(value,str) and ('/Users/' in value or '/home/' in value): return '[local artifact omitted]'
        return value
    payload=json.dumps(sanitize(data),ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    (site/'assets/data.js').write_text('window.LITURGY_DATA='+payload+';\n')
    html=(src/'static/index.html').read_text()
    html=html.replace('<body>','<body class="shared-viewer">').replace('href="/"','href="./"')
    html=re.sub(r'/static/style\.css\?v=[^\"]+', 'assets/style.css', html)
    html=re.sub(r'<script defer src="/static/app\.js\?v=[^"]+"></script>', '<meta name="referrer" content="strict-origin-when-cross-origin">\n  <script defer src="assets/data.js"></script>\n  <script defer src="assets/shared-player.js"></script>\n  <script defer src="assets/app.js"></script>', html)
    html=html.replace('<title>Liturgy Lab · Local speech experiment</title>','<title>Liturgy Lab · Shared experiment viewer</title>')
    html=html.replace('<main>','<main><div class="share-note">Shared experiment viewer · Saved predictions, not live recognition. <a href="reports/COLLABORATOR-SUMMARY.txt">Findings</a> · <a href="reports/RESULTS.html">Detailed results</a> · <a href="START-HERE.txt">Help</a></div>')
    html=html.replace('<video id="video"', '<div id="youtube-player"><div id="youtube-iframe"></div></div><video hidden id="video"')
    html=html.replace('Local video is not available yet. The transcript and reference remain available to explore.','Playback is unavailable. Use Source recording to watch on YouTube. Text browsing remains available.')
    html=html.replace('<div class="subtitle-tray"', '<div class="shared-player-tools"><p id="player-status" role="status">Loading YouTube…</p></div><div class="subtitle-tray"',1)
    html=html.replace('Review segments below to build a human-checked evaluation.','This shared viewer is read-only; review collection is available in the original local application.')
    html=html.replace('href="/api/reviews/export"','href="#"')
    (site/'index.html').write_text(html)
    js=(src/'static/app.js').read_text().replace('const video = $("video");','const video = window.createSharedPlayer();')
    start=js.index('  async function api(');end=js.index('  function showError',start)
    js=js[:start]+'''  async function api(url, options = {}) {
    if (options.method && options.method !== "GET") throw new Error("This shared viewer is read-only.");
    if (url === "/api/recordings") return window.LITURGY_DATA.recordings;
    if (url === "/api/reviews") return {reviews:[]};
    const id = new URL(url, "https://viewer.invalid").searchParams.get("recording");
    const session = window.LITURGY_DATA.sessions[id];
    if (!session) throw new Error("This recording is not included in the shared viewer.");
    return session;
  }
'''+js[end:]
    js=js.replace('video.src = `/media/recording/${encodeURIComponent(id)}`;\n      video.load();','video.setRecording(id, session.source?.duration);')
    js=js.replace('$("review-current").hidden = !segment;','$("review-current").hidden = true;')
    # Keep review DOM for existing UI helpers, but never collect or export review input.
    js=js.replace('function renderReviewCount() {','function renderReviewCount() {\n    $("footer-status").textContent = "Read-only snapshot · Model predictions require human review."; return;')
    (site/'assets/app.js').write_text(js)
    css=(src/'static/style.css').read_text()+'''
.shared-viewer #review-panel,.shared-viewer #review-current{display:none!important}
.share-note{font-size:11px;line-height:1.7;color:var(--muted);padding-top:12px}
.share-note a{color:var(--green);text-underline-offset:2px}
#youtube-player,#youtube-player iframe{width:100%;height:100%;border:0;min-height:200px}
.shared-viewer .video-wrap{min-height:200px}
.shared-player-tools{padding:10px 18px;font-size:11px;line-height:1.6;background:#faf9f5}
.shared-player-tools p{margin:0}
.shared-viewer .video-slot.floating .video-wrap{width:min(440px,36vw);min-width:200px;min-height:200px}
.shared-viewer .floating-player-toggle{bottom:calc(18px + max(200px,min(247.5px,20.25vw)))}
.shared-viewer .video-slot.collapsed + .floating-player-toggle{bottom:18px}
@media(max-width:850px){
 .shared-viewer .video-slot.floating .video-wrap{width:240px;height:200px;aspect-ratio:auto}
 .shared-viewer .floating-player-toggle{bottom:210px}
 .shared-viewer .video-slot.collapsed + .floating-player-toggle{bottom:10px}
}
'''
    (site/'assets/style.css').write_text(css)
    for name in ('RESULTS.md','COLLABORATOR-SUMMARY.txt','GREEK-EXAMPLES.md'):
        shutil.copy2(src/name,site/'reports'/name)
    # Markdown source is included; readable HTML needs no external renderer.
    from render_report_pages import build_report_pages
    build_report_pages(src,site)
    # New exported data and code should load together after a Pages update.
    import hashlib
    index=(site/'index.html').read_text()
    for name in ('data.js','app.js','shared-player.js','style.css'):
        revision=hashlib.sha256((site/'assets'/name).read_bytes()).hexdigest()[:12]
        index=index.replace('assets/'+name+'"','assets/'+name+'?v='+revision+'"')
    (site/'index.html').write_text(index)
    (site/'.nojekyll').touch()
    print(json.dumps({'recordings':len(records),'data_bytes':len(payload.encode()),'site':str(site)}))

if __name__=='__main__': main()
