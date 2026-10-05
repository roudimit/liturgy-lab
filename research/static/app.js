"use strict";

(() => {
  const $ = id => document.getElementById(id);
  const state = { session: null, recordings: [], recordingId: null, run: null, segments: [], alignment: "sequence", reviews: [], drafts: new Map(), activeId: null, selectedId: null, dirty: false, unitTimes: new Map(), sectionTimes: new Map(), referenceNodes: new Map(), transcriptNodes: new Map(), currentUnit: null, requestId: 0 };
  const video = $("video");
  const videoSlot = $("video-slot");
  const floatingToggle = $("floating-player-toggle");
  let floatingCollapsed = false;
  let floatingFrame = null;
  function updateFloatingPlayer() {
    floatingFrame = null;
    const floated = !$("app").hidden && videoSlot.getBoundingClientRect().bottom < 0;
    if (!floated) floatingCollapsed = false;
    videoSlot.classList.toggle("floating", floated);
    videoSlot.classList.toggle("collapsed", floated && floatingCollapsed);
    floatingToggle.hidden = !floated;
    floatingToggle.textContent = floatingCollapsed ? "Show video ↗" : "Hide video ×";
    floatingToggle.setAttribute("aria-expanded", String(!floatingCollapsed));
  }
  function scheduleFloatingPlayer() {
    if (floatingFrame == null) floatingFrame = requestAnimationFrame(updateFloatingPlayer);
  }
  floatingToggle.addEventListener("click", () => {
    floatingCollapsed = !floatingCollapsed;
    updateFloatingPlayer();
  });
  window.addEventListener("scroll", scheduleFloatingPlayer, { passive: true });
  window.addEventListener("resize", scheduleFloatingPlayer, { passive: true });
  const accepted = match => match && ["matched", "accepted"].includes(match.status) && match.unit_id != null && !match.context_unverified;
  const matchOf = segment => {
    const match = segment && (state.alignment === "llm" ? segment.llm_match : state.alignment === "sequence" ? segment.sequence_match || (segment.match?.method === "sequence" ? segment.match : null) : segment.lexical_match || (segment.match?.method !== "sequence" ? segment.match : null));
    return match?.status === "not_run" ? null : match;
  };
  const key = value => String(value ?? "");
  const formatTime = seconds => {
    const value = Math.max(0, Math.floor(Number(seconds) || 0));
    const hours = Math.floor(value / 3600);
    const minutes = Math.floor((value % 3600) / 60);
    const sec = String(value % 60).padStart(2, "0");
    return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${sec}` : `${minutes}:${sec}`;
  };
  const normalize = text => String(text ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();
  const duration = () => Number(state.session?.source?.duration) || (Number.isFinite(video.duration) ? video.duration : state.segments.at(-1)?.end || 1);
  const reference = () => state.session?.references?.[state.run?.reference_id] || state.session?.reference || {};
  const alignmentTitle = () => state.alignment === "llm" ? "LLM" : state.alignment === "sequence" ? "Sequence" : "Independent text";
  const reviewFingerprint = (segment = state.selectedId, alignment = state.alignment) => state.segments.find(s => key(s.id) === key(segment))?.review_fingerprints?.[alignment] || null;
  const reviewKey = (recording = state.recordingId, run = state.run?.id, segment = state.selectedId, alignment = state.alignment, fingerprint = reviewFingerprint(segment, alignment)) => JSON.stringify([key(recording), key(run), key(segment), alignment, fingerprint]);
  const scopedReviews = id => state.reviews.filter(r => key(r.recording_id ?? state.recordings[0]?.id) === key(state.recordingId) && key(r.run_id) === key(state.run.id) && key(r.segment_id) === key(id) && (r.alignment || "lexical") === state.alignment);
  const currentReview = id => {
    const fingerprint = reviewFingerprint(id);
    return fingerprint ? scopedReviews(id).find(r => r.prediction_fingerprint === fingerprint) : undefined;
  };
  const processedWindows = () => {
    const ranges = state.run.intervals || state.run.windows || state.run.chunks;
    if (ranges?.length) return ranges;
    if (Number.isFinite(state.run.start) && Number.isFinite(state.run.end)) return [{ start: state.run.start, end: state.run.end }];
    return state.segments;
  };
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };
  const empty = (container, message) => container.append(el("p", "empty-state", message));
  const safeLink = (node, url) => {
    try {
      const parsed = new URL(url);
      if (!["http:", "https:"].includes(parsed.protocol)) throw new Error();
      node.href = parsed.href;
      node.hidden = false;
    } catch { node.removeAttribute("href"); node.hidden = true; }
  };
  async function api(url, options = {}) {
    const response = await fetch(url, { cache: "no-store", ...options });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "The request could not be completed. Please check the selected segment and try again.");
    return result;
  }
  function showError(message) {
    $("error").textContent = message;
    $("error").hidden = false;
  }
  function clearReview() {
    state.selectedId = null;
    state.dirty = false;
    $("review-form").hidden = true;
    $("review-empty").hidden = false;
    $("review-status").textContent = "";
    $("review-history").hidden = true;
  }
  async function selectRecording(id) {
    const requestId = ++state.requestId;
    video.pause();
    $("error").hidden = true;
    $("loading").hidden = false;
    $("loading").textContent = "Loading this recording’s experiment…";
    $("app").hidden = true;
    updateFloatingPlayer();
    $("workspace").hidden = true;
    try {
      const session = await api(`/api/session?recording=${encodeURIComponent(id)}`);
      if (requestId !== state.requestId) return;
      state.recordingId = id;
      state.session = session;
      state.activeId = null;
      state.currentUnit = null;
      $("video-error").hidden = true;
      video.src = `/media/recording/${encodeURIComponent(id)}`;
      video.load();
      $("source-title").textContent = session.source?.title || "Local recording";
      $("caveat").textContent = session.source?.caveat || "The supplied service text may differ from the recording. Seasonal hymns, readings, Matins, and sermons may have no corresponding reference passage.";
      safeLink($("source-link"), session.source?.webpage_url);
      safeLink($("reference-link"), session.source?.reference_url);
      $("video-duration").textContent = `${formatTime(session.source?.duration)} recording`;
      $("transcript-search").value = "";
      $("reference-search").value = "";
      const run = (session.runs || []).find(r => key(r.id) === key(session.default_run)) || session.runs?.[0];
      if (!run) throw new Error("This recording has no completed model runs yet. Refresh after processing finishes.");
      clearReview();
      selectRun(run.id, true);
      $("workspace").hidden = false;
      $("app").hidden = false;
      $("loading").hidden = true;
      scheduleFloatingPlayer();
    } catch (error) {
      if (requestId !== state.requestId) return;
      $("loading").hidden = true;
      // Keep the recording selector available so another ready recording can be opened.
      $("app").hidden = false;
      showError(error.message);
    }
  }
  function selectRun(id, seekFirst = false) {
    const run = state.session.runs.find(r => key(r.id) === key(id));
    if (!run) return;
    state.run = run;
    state.segments = [...(run.segments || [])].filter(s => Number.isFinite(s.start) && Number.isFinite(s.end) && s.end > s.start).sort((a, b) => a.start - b.start);
    state.alignment = "sequence";
    $("reference-search").value = "";
    $("service-filter").replaceChildren(el("option", null, "All services"));
    $("service-filter").firstChild.value = "";
    for (const service of reference().services || []) {
      const option = el("option", null, service.title);
      option.value = service.id;
      $("service-filter").append(option);
    }
    renderReferenceNotice();
    clearReview();
    renderStats();
    renderAlignment();
    const windows = processedWindows();
    const inside = windows.some(w => video.currentTime >= w.start && video.currentTime < w.end);
    const testedLLM = state.alignment === "llm" ? state.segments.filter(s => s.llm_match && s.llm_match.status !== "not_run") : [];
    if (testedLLM.length && !testedLLM.some(s => video.currentTime >= s.start && video.currentTime < s.end)) {
      seek(testedLLM[0].start);
    } else if ((seekFirst || !inside) && state.segments.length) {
      const preview = seekFirst ? Number(state.session.source?.preview_start) : NaN;
      seek(Number.isFinite(preview) && windows.some(w => preview >= w.start && preview < w.end) ? preview : state.run.start ?? windows[0]?.start ?? state.segments[0].start);
    }
  }
  function renderReferenceNotice() {
    const ref = reference();
    const selection = ref.selection || {};
    const historical = !!state.run.historical_reference;
    const composite = selection.status === "calendar_component_substitute";
    $("reference-title").textContent = ref.services?.length ? "Matins & Liturgy" : "The Divine Liturgy";
    $("reference-notice-title").textContent = historical ? "HISTORICAL COMPARISON" : composite ? "RECONSTRUCTED SERVICE REFERENCE" : selection.status === "exact_calendar_date" ? "DATED SERVICE REFERENCE" : "SUBSTITUTE SERVICE EDITION";
    $("reference-notice-copy").textContent = historical ? "This run uses the original September 30, 2026 Liturgy-only text. Matins is not covered." : composite ? `${selection.recording_date} calendar components · Mode ${selection.mode}, Eothinon ${selection.eothinon} (${selection.matins_reading}). Official texts combined; local order remains unverified.` : selection.status === "exact_calendar_date" ? `${selection.edition_date} · Matins and ${ref.services?.[1]?.title || "Liturgy"}` : `${selection.edition_date || ref.date || "Undated"} edition used for the ${selection.recording_date || "recorded"} service. Variable hymns and readings may differ.`;
    $("reference-notice").classList.toggle("historical", historical);
    $("caveat").textContent = selection.caveat || state.session.source?.caveat || "Service details require verification.";
    safeLink($("reference-link"), ref.source_url || state.session.source?.reference_url);
    const sourceNote = $("reference-sources");
    sourceNote.replaceChildren(el("span", null, composite ? "Matching text (reconstructed): " : "Matching text: "));
    const sources = ref.sources?.length ? ref.sources : [{ source_url: ref.source_url, title: "GOA service text", date: ref.date }];
    sources.forEach((source, index) => {
      if (index) sourceNote.append(document.createTextNode(" · "));
      const service = ref.services?.find(item => item.source_ids?.includes(source.id));
      const label = service?.id === "matins" ? (source.date ? "Matins" : "Matins ordinary") : service?.id === "liturgy" ? "Liturgy" : source.title;
      const link = el("a", null, `${label || "GOA text"}${source.date ? ` (${source.date})` : ""}`);
      safeLink(link, source.source_url);
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      sourceNote.append(link);
    });
    const seenSources = new Set(sources.map(source => source.source_url));
    const additional = sources.flatMap(source => source.composition_sources || []).filter(source => {
      if (seenSources.has(source.source_url)) return false;
      seenSources.add(source.source_url);
      return true;
    });
    if (additional.length) {
      const details = el("details");
      details.append(el("summary", null, "Additional source texts used"));
      for (const source of additional) {
        const link = el("a", null, source.source_url);
        safeLink(link, source.source_url);
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        details.append(link);
      }
      sourceNote.append(details);
    }
  }
  function renderStats() {
    const metrics = state.run.metrics || {};
    const rows = [];
    if (Number.isFinite(metrics.audio_seconds)) rows.push([`${(metrics.audio_seconds / 60).toFixed(1)} min`, "AUDIO TESTED"]);
    if (Number.isFinite(metrics.speedup)) rows.push([`${metrics.speedup.toFixed(1)}×`, "ASR SPEED / REAL TIME"]);
    else if (Number.isFinite(metrics.real_time_factor) && metrics.real_time_factor > 0) rows.push([`${(1 / metrics.real_time_factor).toFixed(1)}×`, "ASR SPEED / REAL TIME"]);
    rows.push([state.segments.length.toLocaleString(), "SEGMENTS"]);
    $("run-stats").replaceChildren(...rows.map(([value, label]) => {
      const stat = el("div", "stat");
      stat.append(el("span", "stat-value", value), el("span", "stat-label", label));
      return stat;
    }));
    const contextNote = state.segments.some(s => s.match?.context_unverified || s.llm_match?.context_unverified) ? " Text match · service context unverified: sampled audio may resemble the reference without belonging to the same service section." : "";
    const llmMetrics = state.run.llm_metrics || {};
    const llmCount = state.segments.filter(s => s.llm_match && s.llm_match.status !== "not_run").length;
    const llmNote = state.run.llm_model ? ` LLM: ${state.run.llm_model}. ${llmCount} segments evaluated${Number.isFinite(llmMetrics.total_seconds) ? ` in ${llmMetrics.total_seconds.toFixed(1)} seconds including loading` : ""}; all other segments have no LLM prediction. Displayed decisions may include evidence guards and require human review.` : "";
    $("model-detail").textContent = `ASR model: ${state.run.model || "not specified"}. ${metrics.includes_model_load ? "Reported ASR speed includes model loading and compilation. " : ""}${state.run.notes ? (Array.isArray(state.run.notes) ? state.run.notes.join(" ") : state.run.notes) : ""}${state.session.source?.experiment_note ? ` ${state.session.source.experiment_note}` : ""}${contextNote}${llmNote}`;
  }
  function renderAlignment() {
    state.unitTimes = new Map();
    state.sectionTimes = new Map();
    for (const segment of state.segments) {
      const match = matchOf(segment);
      if (!accepted(match)) continue;
      const unit = reference().units?.find(u => key(u.id) === key(match.unit_id));
      if (!unit) continue;
      const sectionId = key(match.section_id ?? unit.section_id);
      if (!state.unitTimes.has(key(unit.id))) state.unitTimes.set(key(unit.id), segment.start);
      if (!state.sectionTimes.has(sectionId)) state.sectionTimes.set(sectionId, { time: segment.start, title: match.section_title || unit.section_title || "Untitled section", serviceId: unit.service_id, serviceTitle: unit.service_id === "matins" ? "Matins" : unit.service_id === "liturgy" ? "Liturgy" : "" });
    }
    renderSections();
    renderCoverage();
    renderTranscript();
    renderReference();
    state.activeId = null;
    state.currentUnit = null;
    updatePlayback(true);
    if (state.selectedId != null) selectSegment(state.selectedId);
  }
  function renderSections() {
    const sections = $("section-chips");
    sections.replaceChildren();
    const entries = [...state.sectionTimes.entries()].sort((a, b) => a[1].time - b[1].time);
    $("section-count").textContent = `${entries.length} suggested`;
    for (const [id, section] of entries) {
      const button = el("button", "section-chip", section.title);
      button.type = "button";
      button.dataset.section = id;
      button.dataset.service = section.serviceId || "liturgy";
      button.title = `First predicted match at ${formatTime(section.time)}`;
      button.append(el("span", null, `${section.serviceTitle ? `${section.serviceTitle} · ` : ""}${formatTime(section.time)}`));
      button.addEventListener("click", () => seek(section.time));
      sections.append(button);
    }
    if (!entries.length) empty(sections, "No accepted section predictions in this run.");
    const serviceNav = $("service-nav");
    serviceNav.replaceChildren();
    for (const service of reference().services || []) {
      const first = entries.find(([, section]) => section.serviceId === service.id)?.[1];
      if (!first) continue;
      const button = el("button", "service-jump", `${service.id === "matins" ? "Matins (Orthros)" : "Divine Liturgy"} ↗`);
      button.type = "button";
      button.dataset.service = service.id;
      button.append(el("span", null, `First suggested location · ${formatTime(first.time)}`));
      button.addEventListener("click", () => seek(first.time));
      serviceNav.append(button);
    }
    const samples = $("sample-windows");
    samples.replaceChildren();
    const windows = state.run.intervals || state.run.windows || [];
    if (windows.length > 1) {
      samples.append(el("span", "tiny-label", "TESTED WINDOWS"));
      for (const window of windows) {
        const button = el("button", "sample-window", `${formatTime(window.start)}–${formatTime(window.end)}`);
        button.type = "button";
        button.addEventListener("click", () => seek(window.start));
        samples.append(button);
      }
    }
  }
  function ranges() {
    const result = [];
    for (const segment of state.segments) {
      const previous = result.at(-1);
      if (previous && segment.start <= previous.end + .3) previous.end = Math.max(previous.end, segment.end);
      else result.push({ start: segment.start, end: segment.end });
    }
    return result;
  }
  function renderCoverage() {
    const track = $("coverage-track");
    track.replaceChildren();
    let seconds = 0;
    for (const range of ranges()) {
      seconds += range.end - range.start;
      const span = el("button", "coverage-span");
      span.type = "button";
      span.tabIndex = -1;
      span.setAttribute("aria-hidden", "true");
      span.style.left = `${Math.min(100, range.start / duration() * 100)}%`;
      span.style.width = `${Math.min(100, (range.end - range.start) / duration() * 100)}%`;
      span.setAttribute("aria-label", `Transcribed audio ${formatTime(range.start)} to ${formatTime(range.end)}`);
      span.title = `${formatTime(range.start)}–${formatTime(range.end)}`;
      span.addEventListener("click", () => seek(range.start));
      track.append(span);
    }
    const playhead = el("span", "coverage-playhead");
    playhead.id = "coverage-playhead";
    track.append(playhead);
    $("coverage-label").textContent = `${(seconds / 60).toFixed(1)} min with transcript · gaps have no subtitle`;
  }
  function matchLabel(match) {
    if (!match) return state.alignment === "llm" ? "No LLM prediction for this segment" : "No alignment prediction";
    if (match.context_unverified && match.unit_id != null) return `Text association · service position unverified${match.section_title ? ` · ${match.section_title}` : ""}`;
    if (accepted(match) && match.method === "supplemental_adjacent_phrase") return `Supplemental phrase span · ${match.section_title || "suggested match"}`;
    if (accepted(match)) return match.context_unverified ? `Text match · service context unverified${match.section_title ? ` · ${match.section_title}` : ""}` : match.section_title || "Predicted reference match";
    if (match.status === "ambiguous") return "Ambiguous · no accepted reference match";
    if (match.status === "uncertain") return "Uncertain · no accepted reference match";
    return "Unknown · no accepted reference match";
  }
  function renderTranscript() {
    const list = $("transcript-list");
    list.replaceChildren();
    state.transcriptNodes = new Map();
    const query = normalize($("transcript-search").value).trim();
    const filtered = state.segments.filter(segment => !query || normalize(segment.text).includes(query));
    $("transcript-count").textContent = query ? `${filtered.length} of ${state.segments.length}` : `${filtered.length} segments`;
    for (const segment of filtered) {
      const match = matchOf(segment);
      const button = el("button", "transcript-row");
      button.type = "button";
      button.dataset.segment = key(segment.id);
      button.setAttribute("aria-label", `${formatTime(segment.start)}: ${segment.text}`);
      const content = el("div");
      content.append(el("p", "transcript-text", segment.text));
      content.append(el("div", `transcript-note${accepted(match) ? "" : " unknown"}`, `${segment.language ? `${segment.language.toUpperCase()} · ` : ""}${matchLabel(match)}`));
      button.append(el("span", "transcript-time", formatTime(segment.start)), content);
      button.addEventListener("click", () => { seek(segment.start); selectSegment(segment.id); });
      list.append(button);
      state.transcriptNodes.set(key(segment.id), button);
    }
    if (!filtered.length) empty(list, query ? "No transcript segments match this search." : "No transcription has been generated for this run.");
    updateTranscriptClasses();
    followTranscript(state.transcriptNodes.get(state.activeId));
  }
  function renderReference() {
    const list = $("reference-list");
    const oldScroll = list.scrollTop;
    // Cancel any previous follow animation before replacing its target nodes.
    list.scrollTo({ top: oldScroll, behavior: "instant" });
    list.replaceChildren();
    state.referenceNodes = new Map();
    const query = normalize($("reference-search").value).trim();
    const units = reference().units || [];
    let previousSection = null;
    let previousService = null;
    let count = 0;
    for (const unit of units) {
      if ($("service-filter").value && unit.service_id !== $("service-filter").value) continue;
      if (query && !normalize(`${unit.greek} ${unit.english} ${unit.section_title}`).includes(query)) continue;
      if (unit.service_id && unit.service_id !== previousService) {
        list.append(el("h3", "reference-service", unit.service_title || unit.service_id));
        previousService = unit.service_id;
      }
      const sectionId = key(unit.section_id);
      if (sectionId !== previousSection) {
        list.append(el(unit.service_id ? "h4" : "h3", "reference-section", unit.section_title || reference().sections?.find(s => key(s.id) === sectionId)?.title || "Service text"));
        previousSection = sectionId;
      }
      const time = state.unitTimes.get(key(unit.id));
      const row = el("article", `reference-unit${time != null ? " timed" : ""}${unit.kind === "rubric" ? " rubric" : ""}`);
      row.dataset.unit = key(unit.id);
      const meta = el("div", "unit-meta");
      meta.append(el("span", null, unit.speaker || (unit.kind === "rubric" ? "Rubric" : "Service text")));
      if (time != null) {
        row.tabIndex = 0;
        row.setAttribute("role", "button");
        row.setAttribute("aria-label", `Seek to predicted match at ${formatTime(time)}: ${unit.english || unit.greek}`);
        meta.append(el("span", "unit-time", `${formatTime(time)} ↗`));
        row.addEventListener("click", () => seek(time));
        row.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); seek(time); } });
      }
      row.append(meta);
      if (unit.english) { const english = el("p", "reference-english", unit.english); english.lang = "en"; row.append(english); }
      if (unit.greek) { const greek = el("p", "reference-greek", unit.greek); greek.lang = "el"; row.append(greek); }
      list.append(row);
      state.referenceNodes.set(key(unit.id), row);
      count++;
    }
    if (!count) empty(list, query ? "No reference text matches this search." : "No reference text has been loaded.");
    list.scrollTo({ top: oldScroll, behavior: "instant" });
    state.currentUnit = null;
    if (state.run) updatePlayback(true);
  }
  let pendingSeek = null;
  function seek(time) {
    pendingSeek = Number(time);
    if (video.readyState >= 1) {
      video.currentTime = pendingSeek;
      pendingSeek = null;
    }
    updatePlayback(true, Number(time));
  }
  function currentSegment(time) {
    let low = 0, high = state.segments.length - 1, candidate = -1;
    while (low <= high) {
      const middle = (low + high) >>> 1;
      if (state.segments[middle].start <= time) { candidate = middle; low = middle + 1; }
      else high = middle - 1;
    }
    if (candidate >= 0 && time < state.segments[candidate].end) return state.segments[candidate];
    return null;
  }
  function updateTranscriptClasses() {
    for (const [id, node] of state.transcriptNodes) {
      node.classList.toggle("active", id === state.activeId);
      node.classList.toggle("selected", id === state.selectedId);
      if (id === state.activeId) node.setAttribute("aria-current", "true");
      else node.removeAttribute("aria-current");
    }
  }
  function followReference(node, immediate = false) {
    if (!node || !$("follow-toggle").checked || $("reference-search").value.trim()) return;
    const list = $("reference-list");
    const rect = node.getBoundingClientRect(), parentRect = list.getBoundingClientRect();
    if (immediate || rect.top < parentRect.top + 25 || rect.bottom > parentRect.bottom - 25) {
      list.scrollTo({ top: list.scrollTop + rect.top - parentRect.top - 35, behavior: immediate || matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
    }
  }
  function followTranscript(node) {
    if (!node || !$("follow-toggle").checked || $("transcript-search").value.trim()) return;
    const list = $("transcript-list");
    const rect = node.getBoundingClientRect(), parentRect = list.getBoundingClientRect();
    if (rect.top < parentRect.top + 12 || rect.bottom > parentRect.bottom - 12) {
      list.scrollTo({ top: list.scrollTop + rect.top - parentRect.top - 16, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    }
  }
  function updatePlayback(force = false, overrideTime = null) {
    if (!state.run) return;
    const time = overrideTime ?? video.currentTime ?? 0;
    const segment = currentSegment(time);
    const id = segment ? key(segment.id) : null;
    const playhead = $("coverage-playhead");
    if (playhead) playhead.style.left = `${Math.min(100, time / duration() * 100)}%`;
    if (!force && id === state.activeId) return;
    state.activeId = id;
    const match = matchOf(segment);
    const unitId = accepted(match) && reference().units?.some(u => key(u.id) === key(match.unit_id)) ? key(match.unit_id) : null;
    $("subtitle-tray").classList.toggle("unprocessed", !segment);
    $("current-language").textContent = segment?.language || "";
    $("subtitle-time").textContent = segment ? `${formatTime(segment.start)}–${formatTime(segment.end)}` : formatTime(time);
    $("current-subtitle").textContent = segment?.text || "No transcript at this position.";
    const windows = processedWindows();
    const processed = windows.some(w => time >= w.start && time < w.end);
    $("current-alignment").textContent = segment ? matchLabel(match) : processed ? "No speech prediction in this gap" : "Unprocessed audio · no prediction";
    $("alignment-dot").className = `status-dot ${unitId ? "matched" : "unknown"}`;
    $("review-current").hidden = !segment;
    $("reference-state").textContent = unitId ? `${match.context_unverified ? "Text match · service context unverified" : "Predicted location"} · ${match.section_title || "Matched service text"}${state.referenceNodes.has(unitId) ? "" : " · hidden by filter"}` : "No predicted location at this position";
    $("reference-state").classList.toggle("matched", !!unitId);
    const chips = $("section-chips");
    for (const button of chips.querySelectorAll("button")) {
      const active = !!unitId && button.dataset.section === key(match.section_id);
      button.classList.toggle("active", active);
      if (active) {
        button.setAttribute("aria-current", "true");
      } else button.removeAttribute("aria-current");
    }
    if (force || unitId !== state.currentUnit) {
      for (const [rowId, row] of state.referenceNodes) {
        row.classList.toggle("active", rowId === unitId);
        if (rowId === unitId) row.setAttribute("aria-current", "true");
        else row.removeAttribute("aria-current");
      }
      state.currentUnit = unitId;
      followReference(state.referenceNodes.get(unitId), force);
    }
    updateTranscriptClasses();
    followTranscript(state.transcriptNodes.get(id));
  }
  function selectSegment(id) {
    const segment = state.segments.find(s => key(s.id) === key(id));
    if (!segment) return;
    $("review-status").textContent = "";
    state.selectedId = key(id);
    state.dirty = false;
    $("review-empty").hidden = true;
    $("review-form").hidden = false;
    $("review-timestamp").textContent = `${formatTime(segment.start)} – ${formatTime(segment.end)} · ${alignmentTitle()} alignment`;
    $("review-text").textContent = segment.text;
    const match = matchOf(segment);
    const unit = accepted(match) ? reference().units?.find(u => key(u.id) === key(match.unit_id)) : null;
    const prediction = unit ? (segment.language === "el" ? unit.greek || unit.english : unit.english || unit.greek) : "";
    const warnings = segment.asr_warnings?.length ? `\nASR warning: ${segment.asr_warnings.join("; ")}` : "";
    const span = state.alignment === "sequence" ? segment.supplemental_evidence : null;
    const spanNote = span ? `\nSupplemental support: adjacent raw fragments at ${formatTime(span.start)}–${formatTime(span.end)}. Original automatic decision: ${segment.automatic_sequence_match?.status || "unavailable"}. Shared-span evidence does not establish individual word accuracy.` : "";
    $("review-match").textContent = `${matchLabel(match)}${Number.isFinite(match?.score) ? ` · similarity ${match.score.toFixed(2)} (not probability)` : ""}${prediction ? `\nReference: ${prediction}` : ""}${match?.reason ? `\n${match.reason}` : ""}${spanNote}${warnings}`;
    const draft = state.drafts.get(reviewKey());
    const review = draft || currentReview(id);
    $("review-form").reset();
    if (review) {
      const radio = [...$("review-form").querySelectorAll('input[name="verdict"]')].find(input => input.value === review.verdict);
      if (radio) radio.checked = true;
      $("reference-transcript").value = review.reference_transcript || "";
      $("review-status").textContent = draft ? "Unsaved draft restored." : "Saved locally. You can update this review.";
      state.dirty = !!draft;
    }
    renderReviewHistory(id);
    const reviewable = !!reviewFingerprint(id) && (state.alignment !== "llm" || !!matchOf(segment));
    $("save-review").disabled = !reviewable;
    if (!reviewable) $("review-status").textContent = state.alignment === "llm" && !matchOf(segment) ? "Choose lexical alignment to review this segment; it has no LLM prediction." : "Refresh the recording to load its current review context.";
    updateTranscriptClasses();
  }
  function renderReviewHistory(id) {
    const fingerprint = reviewFingerprint(id);
    const historical = scopedReviews(id).filter(r => !r.prediction_fingerprint || r.prediction_fingerprint !== fingerprint);
    $("review-history").hidden = !historical.length;
    $("review-history-summary").textContent = `${historical.length} historical review${historical.length === 1 ? "" : "s"} · not applied to this prediction`;
    const list = $("review-history-list");
    list.replaceChildren();
    for (const review of historical) {
      const entry = el("article", "historical-review");
      const verdict = {matched: "Correct match", incorrect: "Incorrect match", unknown: "Unsure"}[review.verdict] || review.verdict || "Unspecified";
      entry.append(el("p", "historical-review-heading", `${verdict}${review.updated_at ? ` · ${review.updated_at.slice(0, 10)}` : ""}`));
      entry.append(el("p", "subtle", review.prediction_fingerprint ? `Earlier reference / prediction${review.alignment_version != null ? ` · tracker v${review.alignment_version}` : ""}${review.reference_id ? ` · ${review.reference_id}` : ""}` : "This older review did not record its prediction context."));
      if (review.reviewed_audio_and_transcript?.text) entry.append(el("p", "historical-review-text", `Reviewed model transcript: ${review.reviewed_audio_and_transcript.text}`));
      entry.append(el("p", "historical-review-text", review.reference_transcript || "No listening transcript was entered."));
      list.append(entry);
    }
  }
  async function saveReview(event) {
    event.preventDefault();
    if (state.selectedId == null) return;
    const verdict = new FormData($("review-form")).get("verdict");
    if (!verdict) return;
    const fingerprint = reviewFingerprint();
    if (!fingerprint) { $("review-status").textContent = "Refresh the recording before saving this review."; return; }
    const draftKey = reviewKey();
    const payload = { recording_id: state.recordingId, run_id: key(state.run.id), segment_id: state.selectedId, alignment: state.alignment, prediction_fingerprint: fingerprint, verdict, reference_transcript: $("reference-transcript").value };
    $("save-review").disabled = true;
    $("review-status").textContent = "Saving…";
    try {
      const result = await api("/api/reviews", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      state.reviews = state.reviews.filter(r => !(key(r.recording_id ?? state.recordings[0]?.id) === key(payload.recording_id) && key(r.run_id) === payload.run_id && key(r.segment_id) === payload.segment_id && (r.alignment || "lexical") === payload.alignment && r.prediction_fingerprint === payload.prediction_fingerprint));
      state.reviews.push(result.review);
      const liveDraft = state.drafts.get(draftKey);
      const unchangedDraft = !liveDraft || (liveDraft.verdict === payload.verdict && liveDraft.reference_transcript === payload.reference_transcript);
      if (unchangedDraft) state.drafts.delete(draftKey);
      if (state.recordingId === payload.recording_id && key(state.run.id) === payload.run_id && state.selectedId === payload.segment_id && state.alignment === payload.alignment) {
        state.dirty = !unchangedDraft;
        $("review-status").textContent = unchangedDraft ? "Saved for this exact prediction on this Mac." : "Saved the submitted review. Your newer edits are still unsaved.";
        renderReviewHistory(payload.segment_id);
      }
      renderReviewCount();
    } catch (error) { $("review-status").textContent = error.message; }
    finally { $("save-review").disabled = !reviewFingerprint(); }
  }
  function renderReviewCount() {
    $("footer-status").textContent = state.reviews.length ? `${state.reviews.length} saved review${state.reviews.length === 1 ? "" : "s"} · model predictions require human verification` : "Model output requires human review.";
  }
  $("recording-select").addEventListener("change", event => selectRecording(event.target.value));
  $("transcript-search").addEventListener("input", renderTranscript);
  $("reference-search").addEventListener("input", renderReference);
  $("service-filter").addEventListener("change", renderReference);
  $("reference-details-button").addEventListener("click", () => { const details = document.querySelector(".experiment-details"); details.open = true; details.querySelector("summary").focus(); });
  $("follow-toggle").addEventListener("change", () => {
    followReference(state.referenceNodes.get(state.currentUnit), true);
    followTranscript(state.transcriptNodes.get(state.activeId));
  });
  $("review-current").addEventListener("click", () => { if (state.activeId != null) { selectSegment(state.activeId); $("review-panel").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" }); $("review-form").querySelector("input").focus({ preventScroll: true }); } });
  $("review-form").addEventListener("submit", saveReview);
  $("review-form").addEventListener("input", () => { state.dirty = true; state.drafts.set(reviewKey(), { verdict: new FormData($("review-form")).get("verdict"), reference_transcript: $("reference-transcript").value }); $("review-status").textContent = "Unsaved changes"; });
  video.addEventListener("timeupdate", () => updatePlayback());
  video.addEventListener("seeked", () => updatePlayback(true));
  video.addEventListener("loadedmetadata", () => { $("video-error").hidden = true; if (pendingSeek != null) { video.currentTime = pendingSeek; pendingSeek = null; } renderCoverage(); updatePlayback(true); });
  video.addEventListener("error", () => { $("video-error").hidden = false; });
  document.addEventListener("keydown", event => { if (event.key === "/" && !event.metaKey && !event.ctrlKey && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) { event.preventDefault(); $("transcript-search").focus(); } });
  window.addEventListener("beforeunload", event => { if (state.dirty || state.drafts.size) { event.preventDefault(); event.returnValue = ""; } });
  async function initialize() {
    try {
      const [recordings, reviews] = await Promise.all([api("/api/recordings"), api("/api/reviews")]);
      state.recordings = recordings;
      state.reviews = reviews.reviews || [];
      if (!recordings.length) throw new Error("No recordings have been added to the experiment.");
      for (const recording of recordings) {
        const option = el("option", null, recording.title || recording.id);
        option.value = recording.id;
        $("recording-select").append(option);
      }
      $("recording-count").textContent = `${recordings.length} recording${recordings.length === 1 ? "" : "s"}`;
      renderReviewCount();
      await selectRecording(recordings[0].id);
    } catch (error) { $("loading").hidden = true; showError(error.message); }
  }
  initialize();
})();
