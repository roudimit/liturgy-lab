// Exercise actual review selection code with a minimal DOM; no browser/network.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const nodes = new Map();
const radios = ['matched', 'incorrect', 'unknown'].map(value => ({value, checked: false}));
class Node {
  constructor() { this.children = []; this.value = ''; this.dataset = {}; this.classList = {toggle(){}}; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener() {}
  setAttribute() {}
  removeAttribute() {}
  querySelector() { return new Node(); }
  querySelectorAll() { return radios; }
  reset() { radios.forEach(r => { r.checked = false; }); nodes.get('reference-transcript').value = ''; }
}
const context = {document: {getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Node()); return nodes.get(id); },
  createElement() { return new Node(); }, addEventListener() {}}, window: {addEventListener(){}},
  URL, console, FormData, matchMedia() { return {matches: true}; }, fetch() { throw Error('Unexpected network call'); }};
vm.createContext(context);
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8')
  .replace('  initialize();\n})();', '  globalThis.test = {state, selectSegment, reviewKey};\n})();');
vm.runInContext(source, context);
const {state, selectSegment, reviewKey} = context.test;
state.recordingId = 'video';
state.recordings = [{id: 'video'}];
state.session = {reference: {units: []}};
state.run = {id: 'same-run'};
state.alignment = 'sequence';
state.segments = [{id: '1', start: 10, end: 15, text: 'raw audio', sequence_match: {status: 'unknown'},
  review_fingerprints: {sequence: 'current'}}];
nodes.set('reference-transcript', new Node());
const base = {recording_id: 'video', run_id: 'same-run', segment_id: '1', alignment: 'sequence', verdict: 'matched'};
state.reviews = [{...base, reference_transcript: 'Legacy text remains unchanged'},
  {...base, prediction_fingerprint: 'old', reference_transcript: 'Prior prediction text remains unchanged'}];
const originals = JSON.stringify(state.reviews);
selectSegment('1');
assert.strictEqual(nodes.get('reference-transcript').value, '');
assert.strictEqual(radios.some(r => r.checked), false, 'old verdicts must not prefill');
assert.strictEqual(nodes.get('review-history').hidden, false);
assert.strictEqual(nodes.get('review-history-list').children.length, 2);
state.reviews.push({...base, prediction_fingerprint: 'current', verdict: 'incorrect', reference_transcript: 'Current annotation'});
selectSegment('1');
assert.strictEqual(nodes.get('reference-transcript').value, 'Current annotation');
assert.strictEqual(radios.find(r => r.value === 'incorrect').checked, true);
state.drafts.set(reviewKey(), {verdict: 'matched', reference_transcript: 'Draft on earlier prediction'});
state.segments[0].review_fingerprints.sequence = 'rebuilt';
selectSegment('1');
assert.strictEqual(nodes.get('reference-transcript').value, '', 'old drafts must not attach to a rebuilt prediction');
assert.strictEqual(radios.some(r => r.checked), false);
assert.strictEqual(nodes.get('review-history-list').children.length, 3);
assert.strictEqual(JSON.stringify(state.reviews.slice(0, 2)), originals, 'historical records are never rewritten');
console.log('PASS: stale verdict and draft isolation, current prefill, historical visibility, original text preservation.');
