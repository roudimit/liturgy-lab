"use strict";

// YouTube playback exposed through the transcript viewer's media interface.
window.createSharedPlayer = function () {
  const host = document.getElementById("youtube-player");
  const status = document.getElementById("player-status");
  const events = new EventTarget();
  let player = null, ready = false, id = null;
  let position = 0, length = 0, pendingYouTubeSeek = null;
  const emit = name => events.dispatchEvent(new Event(name));
  const note = text => { status.textContent = text; };
  const expectedVideo = () => ready && player.getVideoData?.()?.video_id === id;
  const cue = () => {
    if (!ready || !id) return;
    player.cueVideoById({videoId:id, startSeconds:position});
    pendingYouTubeSeek = position;
  };
  const facade = {
    get currentTime() { return position; },
    set currentTime(value) {
      position = Math.max(0, Math.min(Number(value) || 0, length));
      pendingYouTubeSeek = position;
      if (expectedVideo()) player.seekTo(position, true);
      else cue();
      emit("seeked");
    },
    get readyState() { return 1; },
    get duration() { return length; },
    pause() { if (ready) player.pauseVideo(); },
    addEventListener(...args) { events.addEventListener(...args); },
    setRecording(recordingId, duration) {
      facade.pause();
      id = recordingId; length = Number(duration) || 0; position = 0;
      pendingYouTubeSeek = 0;
      host.hidden = false;
      document.getElementById("video-error").hidden = true;
      note(location.protocol === "file:" ? "Start the local server for YouTube playback. Text browsing is available here." : "YouTube playback · Press Play in the video. Predictions are precomputed.");
      cue();
    }
  };
  window.onYouTubeIframeAPIReady = () => {
    player = new YT.Player("youtube-iframe", {
      host:"https://www.youtube-nocookie.com",
      width:"100%", height:"100%",
      playerVars:{playsinline:1, rel:0, origin:location.protocol.startsWith("http") ? location.origin : undefined},
      events:{
        onReady:() => { ready = true; cue(); },
        onStateChange:event => {
          if (!expectedVideo()) return;
          if (pendingYouTubeSeek !== null && [1,2,5].includes(event.data)) {
            const target = pendingYouTubeSeek;
            if (Math.abs(player.getCurrentTime()-target) > 1) player.seekTo(target,true);
          }
        },
        onError:event => {
          note("YouTube playback unavailable (code "+event.data+"). Use Source recording to watch on YouTube. Playback in that separate tab will not synchronize here; text and section browsing remain available.");
        }
      }
    });
  };
  if (location.protocol !== "file:") {
    const script = document.createElement("script");
    script.src = "https://www.youtube.com/iframe_api";
    script.onerror = () => note("YouTube could not load. Check your connection or use Source recording. Text browsing remains available.");
    document.head.append(script);
  }
  setInterval(() => {
    if (!expectedVideo()) return;
    const t = player.getCurrentTime();
    if (!Number.isFinite(t)) return;
    // Do not let an old iframe timestamp undo a queued seek or recording switch.
    if (pendingYouTubeSeek !== null) {
      if (Math.abs(t-pendingYouTubeSeek) > 2) return;
      pendingYouTubeSeek = null;
    }
    position = t; emit("timeupdate");
  },250);
  return facade;
};
