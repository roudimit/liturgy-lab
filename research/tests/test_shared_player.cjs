const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Node extends EventTarget {
  constructor(){super();this.hidden=false;this.readyState=0;this.currentTime=0;this.duration=1000;this.files=[];this.classList={add(){},remove(){}};}
  pause(){} load(){} removeAttribute(){} append(){}
}
const elements=new Map();
const get=id=>{if(!elements.has(id))elements.set(id,new Node());return elements.get(id);};
let options, tick, videoId, actual=0, cues=[], seeks=[];
const yt={getVideoData:()=>videoId?{video_id:videoId}:undefined,getCurrentTime:()=>actual,pauseVideo(){},cueVideoById(arg){cues.push(arg);},seekTo(t){seeks.push(t);}};
const ctx={window:{},document:{getElementById:get,createElement:()=>new Node(),head:new Node(),body:new Node()},Event,EventTarget,URL,location:{protocol:'http:',origin:'http://localhost:8766'},setInterval(fn){tick=fn;},YT:{Player:function(id,o){options=o;return yt;}}};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),ctx);
const player=ctx.window.createSharedPlayer();
player.setRecording('first',1000);player.currentTime=330;
ctx.window.onYouTubeIframeAPIReady();options.events.onReady();
assert.equal(cues.at(-1).startSeconds,330);
// The SDK can temporarily return undefined video data during a source switch.
assert.doesNotThrow(()=>{player.currentTime=500;tick();});
assert.equal(player.currentTime,500);
videoId='first';actual=0;tick();assert.equal(player.currentTime,500);
actual=500.5;tick();assert.equal(player.currentTime,500.5);
actual=506;tick();assert.equal(player.currentTime,506);
player.setRecording('second',800);player.currentTime=200;
actual=510;tick();assert.equal(player.currentTime,200);
videoId='second';actual=0;options.events.onStateChange({data:5});
assert.equal(seeks.at(-1),200);
actual=200.2;tick();assert.equal(player.currentTime,200.2);
options.events.onError({data:150});assert.match(get('player-status').textContent,/code 150/);
console.log('PASS: queued seek before SDK readiness, undefined SDK metadata, stale timestamps, recording switches, time progression, and embed error fallback.');
