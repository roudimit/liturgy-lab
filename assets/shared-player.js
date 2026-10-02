"use strict";

// A media interface shared by the existing transcript UI and a YouTube iframe.
// Local files stay on the visitor's device; this viewer never uploads them.
window.createSharedPlayer = function () {
  const native = document.getElementById("video");
  const host = document.getElementById("youtube-player");
  const status = document.getElementById("player-status");
  const events = new EventTarget();
  let player = null, ready = false, mode = "youtube", id = null;
  let position = 0, length = 0, objectURL = null, pendingNativeSeek = 0;
  let pendingYouTubeSeek = null;
  const emit = name => events.dispatchEvent(new Event(name));
  const note = text => { status.textContent = text; };
  const expectedVideo = () => ready && player.getVideoData?.()?.video_id === id;
  const cue = () => {
    if (!ready || !id || mode !== "youtube") return;
    player.cueVideoById({videoId:id, startSeconds:position});
    pendingYouTubeSeek = position;
  };
  const useYouTube = () => {
    native.pause();
    mode = "youtube";
    native.hidden = true;
    host.hidden = false;
    document.body.classList.remove("local-file-mode");
    document.getElementById("video-error").hidden = true;
    note(location.protocol === "file:" ? "Start the local server for YouTube playback, or choose a local video. Text browsing works here." : "YouTube playback · Press Play in the video. Predictions are precomputed.");
    cue();
  };
  const facade = {
    get currentTime() { return mode === "local" && native.readyState ? native.currentTime : position; },
    set currentTime(value) {
      position = Math.max(0, Math.min(Number(value) || 0, length));
      if (mode === "local") {
        pendingNativeSeek = position;
        if (native.readyState) native.currentTime = position;
      } else {
        pendingYouTubeSeek = position;
        if (expectedVideo()) player.seekTo(position, true);
        else cue();
      }
      emit("seeked");
    },
    get readyState() { return 1; }, // Saved timestamps can be explored before playback is ready.
    get duration() { return length; },
    pause() { if (mode === "local") native.pause(); else if (ready) player.pauseVideo(); },
    addEventListener(...args) { events.addEventListener(...args); },
    setRecording(recordingId, duration) {
      facade.pause();
      id = recordingId; length = Number(duration) || 0; position = 0;
      pendingYouTubeSeek = 0;
      native.removeAttribute("src"); native.load();
      if (objectURL) { URL.revokeObjectURL(objectURL); objectURL = null; }
      document.getElementById("local-video").value = "";
      useYouTube();
    }
  };
  native.addEventListener("loadedmetadata", () => {
    if (mode !== "local") return;
    native.currentTime = Math.min(pendingNativeSeek, native.duration || length);
    note("Local video · Match the selected recording and use the untrimmed original to keep timestamps aligned.");
    emit("loadedmetadata");
  });
  for (const type of ["timeupdate", "seeked"]) native.addEventListener(type, () => {
    if (mode === "local") { position = native.currentTime; emit(type); }
  });
  native.addEventListener("error", () => {
    if (mode === "local") note("This video could not be played. Choose a browser-compatible MP4 for the selected recording.");
  });
  document.getElementById("local-video").addEventListener("change", event => {
    const file = event.target.files[0];
    if (!file) return;
    facade.pause();
    if (objectURL) URL.revokeObjectURL(objectURL);
    objectURL = URL.createObjectURL(file);
    pendingNativeSeek = position;
    mode = "local";
    host.hidden = true; native.hidden = false;
    document.body.classList.add("local-file-mode");
    document.getElementById("video-error").hidden = true;
    native.src = objectURL; native.load();
  });
  document.getElementById("use-youtube").addEventListener("click", useYouTube);
  window.onYouTubeIframeAPIReady = () => {
    player = new YT.Player("youtube-iframe", {
      host:"https://www.youtube-nocookie.com",
      width:"100%", height:"100%",
      playerVars:{playsinline:1, rel:0, origin:location.protocol.startsWith("http") ? location.origin : undefined},
      events:{
        onReady:() => { ready = true; cue(); },
        onStateChange:event => {
          if (mode !== "youtube" || !expectedVideo()) return;
          if (pendingYouTubeSeek !== null && [1,2,5].includes(event.data)) {
            const target = pendingYouTubeSeek;
            if (Math.abs(player.getCurrentTime()-target) > 1) player.seekTo(target,true);
          }
        },
        onError:event => {
          if (mode !== "youtube") return;
          note(`YouTube playback unavailable (code ${event.data}). Use Source recording to watch on YouTube, or choose a local video for synchronized playback here. Text and section browsing still work.`);
        }
      }
    });
  };
  if (location.protocol !== "file:") {
    const script = document.createElement("script");
    script.src = "https://www.youtube.com/iframe_api";
    script.onerror = () => note("YouTube could not load. Check your connection, or choose a local video. Text browsing is available offline.");
    document.head.append(script);
  }
  setInterval(() => {
    if (mode !== "youtube" || !expectedVideo()) return;
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
