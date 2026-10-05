const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const nodes = new Map();
let reducedMotion = true;
class Node {
  constructor() { this.value = ''; this.checked = false; this.scrollTop = 40; this.calls = []; this.style = {}; this.classList = {toggle(){}}; this.rect = {top: 100, bottom: 600}; }
  addEventListener() {}
  setAttribute() {}
  removeAttribute() {}
  querySelectorAll() { return []; }
  getBoundingClientRect() { return this.rect; }
  scrollTo(options) { this.calls.push(options); }
  scrollIntoView() { throw Error('Following must never scroll the page'); }
}
const context = {document: {getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Node()); return nodes.get(id); },
  addEventListener() {}}, window: {addEventListener(){}}, console, URL,
  matchMedia() { return {matches: reducedMotion}; }, fetch() { throw Error('Unexpected network call'); }};
vm.createContext(context);
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8')
  .replace('  initialize();\n})();', '  globalThis.test = {state, updatePlayback, followTranscript};\n})();');
vm.runInContext(source, context);
const {state, updatePlayback, followTranscript} = context.test;
state.session = {source: {duration: 100}, reference: {units: []}};
state.run = {id: 'r', start: 0, end: 100};
state.segments = [{id: 1, start: 10, end: 20, text: 'first'}, {id: 2, start: 20, end: 30, text: 'second'}];
const row = new Node(); row.rect = {top: 900, bottom: 960};
state.transcriptNodes = new Map([['1', row], ['2', row]]);
context.document.getElementById('follow-toggle').checked = true;
context.document.getElementById('reference-transcript').value = 'Review draft stays here';
const list = context.document.getElementById('transcript-list');
updatePlayback(true, 10);
assert.strictEqual(list.calls.length, 1, 'seek follows active transcript row');
assert.strictEqual(list.calls[0].top, 824);
assert.strictEqual(list.calls[0].behavior, 'auto', 'reduced motion is respected');
updatePlayback(false, 11);
assert.strictEqual(list.calls.length, 1, 'same subtitle does not continually scroll');
reducedMotion = false;
updatePlayback(false, 20);
assert.strictEqual(list.calls.length, 2, 'a new active segment is followed');
assert.strictEqual(list.calls[1].behavior, 'smooth');
nodes.get('transcript-search').value = 'search term';
updatePlayback(true, 10);
assert.strictEqual(list.calls.length, 2, 'search results remain stationary');
nodes.get('transcript-search').value = '';
nodes.get('follow-toggle').checked = false;
updatePlayback(true, 20);
assert.strictEqual(list.calls.length, 2, 'follow off leaves list stationary');
nodes.get('follow-toggle').checked = true;
row.rect = {top: 200, bottom: 260};
followTranscript(row);
updatePlayback(true, 40);
assert.strictEqual(list.calls.length, 2, 'visible rows and unprocessed gaps do not scroll');
assert.strictEqual(nodes.get('reference-transcript').value, 'Review draft stays here');
assert.deepStrictEqual([...nodes].filter(([, node]) => node.calls.length).map(([id]) => id), ['transcript-list']);
console.log('PASS: transcript follows seeks/new segments within its own list; search, toggle, reduced motion, and review draft respected.');
