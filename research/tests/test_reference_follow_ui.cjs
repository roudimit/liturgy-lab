const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const nodes = new Map();
let reducedMotion = false;
class Node {
  constructor() { this.children = []; this.value = ''; this.checked = false; this.scrollTop = 25180.625; this.calls = []; this.dataset = {}; this.style = {}; this.attributes = {}; this.classList = {toggle(){}}; }
  addEventListener() {}
  setAttribute(k, v) { this.attributes[k] = v; }
  removeAttribute(k) { delete this.attributes[k]; }
  append(...children) { for (const child of children) { child.parent = this; this.children.push(child); } }
  replaceChildren(...children) { this.children = []; this.append(...children); this.scrollTop = 0; }
  querySelectorAll() { return []; }
  getBoundingClientRect() {
    if (this === nodes.get('reference-list')) return {top: 756.26, bottom: 1663.26};
    if (this.parent === nodes.get('reference-list')) {
      const top = 756.26 + this.parent.children.indexOf(this) * 400 - this.parent.scrollTop;
      return {top, bottom: top + 260};
    }
    return {top: 0, bottom: 100};
  }
  scrollTo(options) {
    this.calls.push(options);
    if (options.behavior === 'smooth') this.pending = options;
    else { this.pending = null; this.scrollTop = options.top; }
  }
  finishAnimation() { if (this.pending) this.scrollTop = this.pending.top; this.pending = null; }
  scrollIntoView() { throw Error('Reference following must not scroll the page'); }
}
const context = {document: {getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Node()); return nodes.get(id); },
  createElement() { return new Node(); }, addEventListener() {}}, window: {addEventListener(){}},
  console, URL, matchMedia() { return {matches: reducedMotion}; }, fetch() { throw Error('Unexpected network call'); }};
vm.createContext(context);
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8')
  .replace('  initialize();\n})();', '  globalThis.test = {state, renderReference, followReference};\n})();');
vm.runInContext(source, context);
const {state, renderReference, followReference} = context.test;
const units = Array.from({length: 200}, (_, i) => ({id: `u${i}`, service_id: i < 100 ? 'matins' : 'liturgy',
  service_title: i < 100 ? 'Matins' : 'Liturgy', section_id: i < 100 ? 'matins-s' : 'liturgy-s',
  section_title: i < 100 ? 'Matins Gospel' : 'Entrance Hymn', greek: `Greek hymn ${i}`, english: `English hymn ${i}`}));
state.session = {source: {duration: 8900}, reference: {units}};
state.run = {id: 'n674-full', start: 0, end: 8900};
state.segments = [{id: 's1', start: 3690, end: 3700, text: 'Entrance hymn',
  sequence_match: {status: 'matched', unit_id: 'u130', section_id: 'liturgy-s', section_title: 'Entrance Hymn'}}];
state.alignment = 'sequence';
context.document.getElementById('video').currentTime = 3690;
context.document.getElementById('follow-toggle').checked = true;
context.document.getElementById('reference-transcript').value = 'Unsaved review text';
state.selectedId = 'review-stays-selected';
const list = context.document.getElementById('reference-list');
list.pending = {top: 8000, behavior: 'smooth'}; // Prior recording/filter animation.
context.document.getElementById('service-filter').value = 'matins';
renderReference();
assert.strictEqual(list.pending, null, 'rebuild cancels previous smooth animation even when active unit is filtered out');
context.document.getElementById('service-filter').value = '';
renderReference();
const active = state.referenceNodes.get('u130');
assert.strictEqual(active.attributes['aria-current'], 'true');
assert.strictEqual(list.calls.at(-1).behavior, 'instant', 'filter/seek follow must settle immediately');
assert.ok(Math.abs(active.getBoundingClientRect().top - list.getBoundingClientRect().top - 35) < 0.001);
list.finishAnimation();
assert.ok(Math.abs(active.getBoundingClientRect().top - list.getBoundingClientRect().top - 35) < 0.001, 'an old animation cannot move the visible passage afterward');
followReference(state.referenceNodes.get('u190'));
assert.strictEqual(list.calls.at(-1).behavior, 'smooth', 'ordinary playback may still follow smoothly');
reducedMotion = true;
followReference(state.referenceNodes.get('u190'));
assert.strictEqual(list.calls.at(-1).behavior, 'instant');
assert.strictEqual(nodes.get('reference-transcript').value, 'Unsaved review text');
assert.strictEqual(state.selectedId, 'review-stays-selected');
console.log('PASS: filter rebuild cancels stale animation and reveals active reference immediately; regular follow/reduced motion and review state preserved.');
