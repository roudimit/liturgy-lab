"""Conservative lexical retrieval and offline alignment for Greek/English ASR.

Scores measure text similarity, not calibrated probabilities. Exact repeated
responses cannot identify their occurrence without surrounding unique anchors.
"""
from __future__ import annotations

import re
import unicodedata
import math
from functools import lru_cache

from rapidfuzz import fuzz, process

ALIGNMENT_VERSION = 4


@lru_cache(maxsize=16384)
def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("ς", "σ")
    return " ".join(re.findall(r"[^\W_]+", text, re.UNICODE))


@lru_cache(maxsize=16384)
def phonetic_greek(text: str) -> str:
    """Light itacism tolerance for ASR spellings, not a transliteration system."""
    text = normalize(text)
    for source, target in (("ει", "ι"), ("οι", "ι"), ("αι", "ε"), ("η", "ι"), ("υ", "ι"), ("ω", "ο")):
        text = text.replace(source, target)
    return text


@lru_cache(maxsize=16384)
def romanized_greek(text: str) -> str:
    """Auxiliary pronunciation-like retrieval form for Greek written in Latin.

    This only expands retrieval evidence. The ASR transcript stays untouched.
    """
    text = normalize(text)
    for source, target in (("ου", "u"), ("αι", "e"), ("ει", "i"), ("οι", "i"), ("υι", "i")):
        text = text.replace(source, target)
    mapping = dict(zip("αβγδεζηθικλμνξοπρστυφχψω", ["a", "v", "g", "d", "e", "z", "i", "th", "i", "k", "l", "m", "n", "x", "o", "p", "r", "s", "t", "i", "f", "ch", "ps", "o"]))
    text = "".join(mapping.get(c, c) for c in text)
    for source, target in (("ou", "u"), ("ei", "i"), ("oi", "i"), ("ai", "e"), ("y", "i"), ("ii", "i")):
        text = text.replace(source, target)
    return text


def _looks_like_romanized_greek(text: str) -> bool:
    tokens = set(normalize(text).split())
    return bool(tokens & {"kyrie", "kyrieu", "kiriu", "kiriou", "theos", "theu", "theou", "agios", "agio", "diagio", "doxan", "thomen", "thios", "pnevmatos", "eleison"})


@lru_cache(maxsize=32768)
def _similarity(query: str, target: str) -> float:
    if not query or not target:
        return 0.0
    if query == target:
        return 1.0
    qt, rt = query.split(), target.split()
    # A short response embedded in a lengthy ASR segment is insufficient support
    # for the whole segment. Conversely a segment can be a fragment of a prayer.
    if len(qt) > len(rt) * 1.4:
        return fuzz.ratio(query, target) / 100
    if f" {query} " in f" {target} ":
        return 1.0
    if len(qt) < 4:
        return fuzz.ratio(query, target) / 100
    partial = fuzz.partial_ratio(query, target) / 100
    # Word coverage prevents high character similarity on unrelated passages.
    coverage = sum(process.extractOne(q, rt, scorer=fuzz.ratio)[1] / 100 for q in qt) / len(qt)
    return 0.75 * partial + 0.25 * coverage


class ReferenceIndex:
    def __init__(self, reference: dict | list[dict]):
        self.units = reference["units"] if isinstance(reference, dict) else reference
        self.prepared = []
        for index, unit in enumerate(self.units):
            if unit.get("kind", "spoken") != "spoken":
                continue
            self.prepared.append((unit, index, normalize(unit.get("greek", "")),
                                  normalize(unit.get("english", "")), phonetic_greek(unit.get("greek", "")), romanized_greek(unit.get("greek", ""))))

    def retrieve(self, text: str, top_k: int | None = 6) -> list[dict]:
        query, ph_query = normalize(text), phonetic_greek(text)
        if not query:
            return []
        has_greek = bool(re.search(r"[\u0370-\u03ff\u1f00-\u1fff]", text))
        has_latin = bool(re.search(r"[a-zA-Z]", text))
        roman_query = romanized_greek(text) if has_latin and _looks_like_romanized_greek(text) else None
        candidates = []
        for unit, index, greek, english, phonetic, roman in self.prepared:
            scores = []
            if has_greek:
                scores.append((max(_similarity(query, greek), 0.97 * _similarity(ph_query, phonetic)), "el"))
            if has_latin:
                scores.append((_similarity(query, english), "en"))
            if roman_query:
                scores.append((0.97 * max(_similarity(roman_query, roman),
                                         _similarity(roman_query.replace(" ", ""), roman.replace(" ", ""))), "el-Latn"))
            if not scores:
                continue
            score, language = max(scores)
            candidates.append({"unit_id": unit["id"], "index": unit.get("index", index),
                               "section_id": unit.get("section_id"), "section_title": unit.get("section_title"),
                               "service_id": unit.get("service_id"), "service_title": unit.get("service_title"),
                               "score": round(score, 4), "language": language,
                               "greek": unit.get("greek", ""), "english": unit.get("english", "")})
        candidates.sort(key=lambda item: (-item["score"], item["index"]))
        return candidates if top_k is None else candidates[:top_k]


def retrieve_candidates(text: str, reference: dict | list[dict] | ReferenceIndex, top_k: int = 6) -> list[dict]:
    index = reference if isinstance(reference, ReferenceIndex) else ReferenceIndex(reference)
    return index.retrieve(text, top_k)


def _decision(candidate: dict | None, *, status: str, reason: str, method: str = "lexical") -> dict:
    accepted = candidate is not None and status == "matched"
    return {"unit_id": candidate["unit_id"] if accepted else None,
            "unit_index": candidate["index"] if accepted else None,
            "section_id": candidate["section_id"] if accepted else None,
            "section_title": candidate["section_title"] if accepted else None,
            "score": candidate["score"] if candidate else 0.0,
            "status": status, "method": method, "reason": reason}


def align_segments(segments: list[dict], reference: dict | list[dict], top_k: int = 6) -> list[dict]:
    index = ReferenceIndex(reference)
    output, rankings, anchors = [], [], []
    for i, segment in enumerate(segments):
        candidates = index.retrieve(segment.get("text", ""), top_k=None)
        rankings.append(candidates)
        top = candidates[0] if candidates else None
        second_score = candidates[1]["score"] if len(candidates) > 1 else 0
        tokens = normalize(segment.get("text", "")).split()
        threshold = 0.86 if len(tokens) >= 4 else 0.97
        margin = top["score"] - second_score if top else 0
        short_fragment = (top is not None and len(tokens) <= 4
                          and normalize(segment.get("text", "")) not in
                          {normalize(top.get("greek", "")), normalize(top.get("english", ""))})
        if not tokens or top is None:
            decision = _decision(None, status="unknown", reason="No recognized text")
        elif top["score"] < 0.68:
            decision = _decision(top, status="unknown", reason="No sufficiently similar reference text")
        elif top["score"] >= threshold and margin >= 0.075 and not short_fragment:
            decision = _decision(top, status="matched", reason="Distinctive text match")
            # At least four words are required to locate ambiguous replies later.
            if len(tokens) >= 4:
                anchors.append((i, top["index"]))
        else:
            decision = _decision(top, status="uncertain", reason="Repeated phrase or insufficient text evidence")
        output.append({**segment, "match": decision, "candidates": candidates[:top_k]})
    # Only two nearby, consistent unique anchors can disambiguate a repeated
    # reply. Never force early speech to the beginning of the reference.
    for i, result in enumerate(output):
        if result["match"]["status"] != "uncertain":
            continue
        before = next(((si, ui) for si, ui in reversed(anchors) if si < i), None)
        after = next(((si, ui) for si, ui in anchors if si > i), None)
        if before is None or after is None:
            continue
        if after[0] - before[0] > 10 or not 0 < after[1] - before[1] <= 16:
            continue
        # Independent clips must not lend context to one another merely because
        # they occupy adjacent rows in a batch.
        start = segments[before[0]].get("end", segments[before[0]].get("start"))
        end = segments[after[0]].get("start")
        if start is not None and end is not None and (end < start or end - start > 120):
            continue
        best_score = rankings[i][0]["score"] if rankings[i] else 0
        local = [c for c in rankings[i] if before[1] < c["index"] < after[1]
                 and c["score"] >= max(0.94, best_score - 0.025)]
        if len(local) == 1:
            chosen = local[0]
            result["match"] = _decision(chosen, status="matched", method="context",
                                        reason="Repeated response between two nearby distinctive anchors")
            if chosen["unit_id"] not in {c["unit_id"] for c in result["candidates"]}:
                result["candidates"] = [chosen, *result["candidates"]][:top_k]
    return output


def detect_liturgy_start(segments: list[dict]) -> dict:
    """Find the distinctive opening blessing in contiguous ASR, heuristically.

    Shared doxologies mentioning the kingdom are insufficient. Require the
    actual opening phrase plus Father/Son/Spirit in the same short window. This
    is a reproducible text heuristic, not a human-verified service boundary.
    """
    for i, first in enumerate(segments):
        window = [first]
        for following in segments[i + 1:i + 4]:
            previous_end = window[-1].get("end", window[-1].get("start", 0))
            if following.get("start", previous_end) - previous_end > 5:
                break
            if following.get("end", following.get("start", 0)) - first.get("start", 0) > 40:
                break
            window.append(following)
        joined = " ".join(str(s.get("text", "")) for s in window)
        normalized = normalize(joined)
        greek = phonetic_greek(joined)
        # The phrase must begin in the first segment, or straddle its end. This
        # prevents including the preceding choir response as the boundary.
        first_words = normalize(str(first.get("text", "")))
        first_greek = phonetic_greek(str(first.get("text", "")))
        english_score = fuzz.partial_ratio("blessed is the kingdom", normalized) / 100
        greek_score = fuzz.partial_ratio(phonetic_greek("Ευλογημένη η βασιλεία"), greek) / 100
        en_ok = ("blessed" in first_words and english_score >= 0.92
                 and all(word in normalized for word in ("father", "son", "spirit")))
        el_ok = (fuzz.partial_ratio(phonetic_greek("ευλογημένη"), first_greek) >= 90
                 and greek_score >= 0.92 and phonetic_greek("πατρός") in greek
                 and phonetic_greek("υιού") in greek and phonetic_greek("πνεύματος") in greek)
        if en_ok or el_ok:
            return {"detected": True, "start": first.get("start", 0),
                    "method": "opening_blessing_text_heuristic", "heuristic": True,
                    "independently_verified": False,
                    "similarity_score": round(max(english_score if en_ok else 0, greek_score if el_ok else 0), 4),
                    "evidence": [{"segment_id": s.get("id", i + j), "start": s.get("start"), "text": s.get("text", "")}
                                 for j, s in enumerate(window)],
                    "note": "Opening phrase and Trinitarian continuation found in nearby ASR; inspect the audio to verify."}
    return {"detected": False, "start": None, "method": "opening_blessing_text_heuristic",
            "heuristic": True, "independently_verified": False, "evidence": [],
            "note": "No distinctive opening blessing found. A recording may start late or ASR may miss it."}


def apply_service_context(segments: list[dict], service_start: dict | float | None,
                          known_complete_start: bool = True) -> list[dict]:
    """Separate shared-text associations from candidate service occurrences.

    Apply after lexical and/or LLM alignment. Complete recordings remain
    unlocated until the opening blessing is identified. Truncated samples keep
    their textual suggestions but explicitly lack verified service context.
    Original decisions remain under textual_match / llm_textual_match.
    """
    detection = service_start if isinstance(service_start, dict) else {"start": service_start, "heuristic": True}
    boundary = detection.get("start")
    output = []
    for segment in segments:
        row = dict(segment)
        before = boundary is not None and segment.get("start", 0) < boundary
        unlocated_full = boundary is None and known_complete_start
        state = "before_liturgy_opening" if before else "after_detected_opening" if boundary is not None else "unverified"
        row["service_context"] = {"status": state, "opening_start": boundary,
                                  "heuristic": True, "independently_verified": False}
        for field, retained in (("match", "textual_match"), ("llm_match", "llm_textual_match")):
            if field not in segment:
                continue
            original = dict(segment.get(retained) or segment[field])
            row[retained] = original
            match = dict(original)
            if before or unlocated_full:
                if match.get("unit_id") is not None:
                    match.update(unit_id=None, unit_index=None, section_id=None, section_title=None,
                                 status="uncertain", location_suppressed=True,
                                 reason=("Shared text before the detected Liturgy opening; occurrence is unlocated"
                                         if before else "No Liturgy opening detected in this complete recording; occurrence is unlocated"))
            elif boundary is None:
                match["context_unverified"] = True
            # Also validate previously computed lexical rows. Four generic words
            # can occur in a sermon and inside a long prayer without identifying
            # that prayer's occurrence. Bracketed-context decisions are exempt.
            if match.get("unit_id") and match.get("status") == "matched" and match.get("method") != "context":
                chosen = next((c for c in row.get("candidates", []) if c.get("unit_id") == match["unit_id"]), None)
                query = normalize(row.get("text", ""))
                if chosen and len(query.split()) <= 4 and query not in {normalize(chosen.get("greek", "")), normalize(chosen.get("english", ""))}:
                    match.update(unit_id=None, unit_index=None, section_id=None, section_title=None,
                                 status="uncertain", location_suppressed=True,
                                 reason="Short partial phrase needs surrounding occurrence context")
            row[field] = match
        output.append(row)
    if known_complete_start and boundary is not None:
        _suppress_isolated_forward_jumps(output)
    return output


def _suppress_isolated_forward_jumps(segments: list[dict]) -> None:
    """Reject an early shared phrase that jumps far ahead of a supported block.

    This runs only on a complete recording after an opening is detected. It
    does not force a best path or invent matches. Three later distinct units in
    a locally ordered block provide evidence that a lone much later unit is an
    unreliable location, even if its words occur verbatim in the reference.
    """
    def unit_index(row: dict, field: str) -> int | None:
        decision = row.get(field) or {}
        if decision.get("status") != "matched" or not decision.get("unit_id"):
            return None
        if decision.get("unit_index") is not None:
            return decision["unit_index"]
        return next((c["index"] for c in row.get("candidates", [])
                     if c.get("unit_id") == decision["unit_id"] and "index" in c), None)

    for field in ("match", "llm_match"):
        indexed = [(i, unit_index(row, field)) for i, row in enumerate(segments)]
        indexed = [(i, ui) for i, ui in indexed if ui is not None]
        for position, (i, current_index) in enumerate(indexed):
            later = []
            for j, later_index in indexed[position + 1:]:
                if segments[j].get("start", 0) - segments[i].get("start", 0) > 600:
                    break
                if not later or later_index != later[-1][1]:
                    later.append((j, later_index))
                if len(later) == 12:
                    break
            for k in range(len(later) - 2):
                cluster = later[k:k + 3]
                indexes = [ui for _, ui in cluster]
                if not (indexes[0] < indexes[1] < indexes[2] and indexes[2] - indexes[0] <= 16):
                    continue
                if current_index <= indexes[2] + 24:
                    continue
                decision = segments[i][field]
                decision.update(unit_id=None, unit_index=None, section_id=None, section_title=None,
                                status="uncertain", location_suppressed=True,
                                reason="Shared fragment jumps far ahead of three later nearby reference units; location withheld")
                decision["sequence_evidence_segment_ids"] = [segments[j].get("id", j) for j, _ in cluster]
                break


def _independent_decision(text: str, candidates: list[dict]) -> dict:
    """The old global lexical decision, retained for comparison with tracking."""
    best = candidates[0] if candidates else None
    words = normalize(text).split()
    if not best or not words:
        return _decision(None, status="unknown", reason="No recognized text")
    if best["score"] < 0.68:
        return _decision(best, status="unknown", reason="No sufficiently similar reference text")
    short_fragment = len(words) <= 4 and " ".join(words) not in {normalize(best["greek"]), normalize(best["english"])}
    margin = best["score"] - (candidates[1]["score"] if len(candidates) > 1 else 0)
    if best["score"] >= (0.86 if len(words) >= 4 else 0.97) and margin >= 0.075 and not short_fragment:
        return _decision(best, status="matched", reason="Distinctive global text match")
    return _decision(best, status="uncertain", reason="Repeated phrase or insufficient global text evidence")


def _common_service_formula(text: str) -> bool:
    """Recurring liturgical formulas cannot establish a new service or a large jump."""
    q = normalize(text)
    return bool(re.search(r"mercy|ages|glory|now and|pray to the lord|by your grace|whole life|with all the saints|remembering our most|intercession|apostles|ancestors|john the baptist|life giving cross|holy fathers", q)
                or re.search(r"ελεη|αιωνα|δοξα|πατρι|πατροσ|πνευμα|δεηθ|παντων των αγιων|παναγιασ αχραντου|πρεσβει|αποστολ|θεοπατορ|προδρομ|σταυρου", q))


def _globally_distinctive(candidate: dict, rankings: list[dict], text: str) -> bool:
    rivals = [c["score"] for c in rankings if c["unit_id"] != candidate["unit_id"]]
    words = normalize(text).split()
    # Word count alone made "in the kingdom of heaven" a distinctive anchor.
    # A few content words are needed to start a passage or a substantial skip.
    function_words = set("a an the and or but of for on in at by with from as is are was were be been being has have had he she it they we you i me my our your their his her its us them this that these those who which whom whose all to unto now ever forever καὶ και ο η το οι τα του τησ των τον την τω εν εισ εκ απο προσ με δια στο στη στην στον αυτοσ αυτη αυτο ειναι δε νυν αει ημων υμων σε σου μου".split())
    meaningful = {word for word in words if word not in function_words}
    return (len(words) >= 5 and len(meaningful) >= 3 and candidate["score"] >= 0.84
            and candidate["score"] - max(rivals, default=0) >= 0.035)


def _positive_service_evidence(candidates: list[dict], text: str) -> dict | None:
    if not candidates or len(normalize(text).split()) < 6 or _common_service_formula(text):
        return None
    top = candidates[0]
    rival = max((c["score"] for c in candidates if c["service_id"] != top["service_id"]), default=0)
    if top.get("service_id") and top["score"] >= 0.86 and top["score"] - rival >= 0.10:
        return top
    return None


def _impossible_repetition_runs(segments: list[dict]) -> set[int]:
    """A long phrase repeated several times with subsecond copies is suspect ASR timing."""
    groups = {}
    for i, row in enumerate(segments):
        q = normalize(row.get("text", ""))
        if len(q.split()) >= 8:
            groups.setdefault(q, []).append(i)
    suspect = set()
    for positions in groups.values():
        for i in positions:
            near = [j for j in positions if abs(float(segments[j].get("start", 0)) - float(segments[i].get("start", 0))) <= 15]
            if len(near) >= 3 and any(float(segments[j].get("end", 0)) - float(segments[j].get("start", 0)) < 0.5 for j in near):
                suspect.update(near)
    return suspect


def align_sequence(segments: list[dict], reference: dict | list[dict], *,
                   max_reverse_units: int = 3, beam_width: int = 48,
                   top_k: int = 6, gap_seconds: float = 90,
                   progress_callback=None) -> list[dict]:
    """Align an ordered ASR stream with sparse beam/Viterbi sequence tracking.

    Hidden states keep the last reference unit even across unknown speech.
    Forward skips incur a soft cost; small reversals are allowed; larger backward
    jumps require a new independent clip. UNKNOWN is always available at zero
    emission reward. Repeated replies require nearby distinctive anchors before
    they can be accepted. No transcript text is repaired or replaced.

    Combined references use unit.service_id = 'matins' / 'liturgy'. A detected
    opening restricts candidates to the corresponding service on either side;
    it does not suppress Matins. Without that cue crossing services requires two
    nearby distinctive passages in the later service. Common formulas cannot
    establish that transition. This is a heuristic association, not accuracy.
    """
    if max_reverse_units < 0 or beam_width < 2:
        raise ValueError("max_reverse_units must be nonnegative and beam_width at least 2")
    index = ReferenceIndex(reference)
    unit_map = {unit["id"]: unit for unit in index.units}
    detection = detect_liturgy_start(segments)
    opening = detection.get("start")
    available_services = {unit.get("service_id") for unit in index.units}
    service_gate = opening is not None and {"matins", "liturgy"}.issubset(available_services)
    rows, rankings, blocks, choices = [], [], [], []
    service_evidence = []
    suspect_repetition = _impossible_repetition_runs(segments)
    block_start = 0
    for i, source in enumerate(segments):
        explicit_clip_change = i and source.get("clip_id") != segments[i - 1].get("clip_id")
        if i and (explicit_clip_change or float(source.get("start", 0)) - float(segments[i - 1].get("end", segments[i - 1].get("start", 0))) > gap_seconds):
            blocks.append((block_start, i))
            block_start = i
        candidates = index.retrieve(source.get("text", ""), top_k=None)
        evidence = _positive_service_evidence(candidates, source.get("text", ""))
        service_evidence.append(evidence)
        expected_service = None
        if service_gate:
            expected_service = "matins" if float(source.get("start", 0)) < opening else "liturgy"
            candidates = [c for c in candidates if c["service_id"] == expected_service]
        lexical = _independent_decision(source.get("text", ""), candidates)
        row = {**source, "lexical_match": lexical}
        if source.get("match"):
            row["previous_match"] = source["match"]
        # Remove stale pre-Matins gating fields, which refer to a different run.
        row.pop("textual_match", None)
        row["service_context"] = {"status": "service_reference_available",
                                  "service_id": expected_service,
                                  "opening_start": opening, "heuristic": True,
                                  "independently_verified": False}
        rows.append(row)
        rankings.append(candidates)
        words = normalize(source.get("text", "")).split()
        minimum = 0.88 if len(words) <= 3 else 0.79 if len(words) == 4 else 0.68
        eligible = [c for c in candidates if c["score"] >= minimum]
        if i in suspect_repetition:
            eligible = []
        # All exact repeated replies survive retrieval, even if globally tied.
        # Longer fragments keep a wide lexical pool; active-position candidates
        # are added below so a weaker local match can beat a global distraction.
        choices.append(eligible)
        if progress_callback and (i % 100 == 0 or i == len(segments) - 1):
            progress_callback("retrieval", i + 1, len(segments))
    blocks.append((block_start, len(segments)))
    selected: list[dict | None] = [None] * len(segments)
    block_for = {}

    for block_id, (start, stop) in enumerate(blocks):
        # state tuple: cumulative reward, last unit index, backpointer node.
        # node = (previous_node, segment_index, chosen_candidate_or_None).
        beam = [(0.0, -1, None)]
        initial_service = next((service_evidence[j]["service_id"] for j in range(start, stop)
                                if service_evidence[j] is not None
                                and float(segments[j].get("start", 0)) - float(segments[start].get("start", 0)) <= 600), None)
        confirmed_transitions = {j for j in range(start, stop) if service_evidence[j] is not None
                                 and any(k != j and service_evidence[k] is not None
                                         and service_evidence[k]["service_id"] == service_evidence[j]["service_id"]
                                         and service_evidence[k]["unit_id"] != service_evidence[j]["unit_id"]
                                         and abs(float(segments[k].get("start", 0)) - float(segments[j].get("start", 0))) <= 180
                                         for k in range(start, stop))}
        for i in range(start, stop):
            block_for[i] = block_id
            words = normalize(segments[i].get("text", "")).split()
            candidates = choices[i]
            if len(candidates) > 60 and len(words) >= 5:
                near = {c["unit_id"]: c for c in candidates[:40]}
                for _, position, _ in beam:
                    local = [c for c in candidates if position - max_reverse_units <= c["index"] <= position + 32]
                    for c in local[:8]:
                        near[c["unit_id"]] = c
                candidates = list(near.values())
            next_states = {position: (score, position, (node, i, None))
                           for score, position, node in beam}
            for candidate in candidates:
                target = candidate["index"]
                emission = (candidate["score"] - 0.70) * 5
                if len(words) <= 4:
                    exact_unit = normalize(segments[i].get("text", "")) in {normalize(candidate["greek"]), normalize(candidate["english"])}
                    emission *= 0.50 if exact_unit else 0.35
                if emission <= 0:
                    continue
                best_transition = None
                for score, position, node in beam:
                    delta = target - position
                    if position < 0:
                        if not service_gate and len(available_services - {None}) > 1:
                            if initial_service and candidate["service_id"] != initial_service:
                                continue
                            if not initial_service and (service_evidence[i] is None or candidate["service_id"] != service_evidence[i]["service_id"]):
                                continue
                        cost = 0.0
                    elif delta < -max_reverse_units:
                        continue
                    elif delta < 0:
                        cost = 0.20 + 0.13 * abs(delta)
                    elif delta == 0:
                        cost = 0.0
                    else:
                        cost = 0.04 * math.sqrt(delta) + 0.005 * max(0, delta - 20)
                    if position >= 0:
                        previous_service = index.units[position].get("service_id")
                        crossing_service = previous_service != candidate["service_id"]
                        if crossing_service and previous_service and candidate["service_id"]:
                            if delta < 0:
                                continue
                            if not service_gate and not (i in confirmed_transitions and service_evidence[i]["service_id"] == candidate["service_id"]):
                                continue
                        if delta > 24 and not (crossing_service and service_gate):
                            if _common_service_formula(segments[i].get("text", "")) or not _globally_distinctive(candidate, rankings[i], segments[i].get("text", "")):
                                continue
                    value = score + emission - cost
                    if best_transition is None or value > best_transition[0]:
                        best_transition = (value, target, (node, i, candidate))
                if best_transition and best_transition[0] > next_states.get(target, (-math.inf,))[0]:
                    next_states[target] = best_transition
            beam = sorted(next_states.values(), key=lambda state: state[0], reverse=True)[:beam_width]
        if beam:
            node = beam[0][2]
            while node is not None:
                node, i, candidate = node
                selected[i] = candidate

    # A best path is only a proposal. Require textual support and nearby anchors
    # before exposing a location. This keeps a sermon from advancing the tracker
    # merely because a few religious words happen to match a prayer.
    anchors = []
    for i, chosen in enumerate(selected):
        if not chosen:
            continue
        if _globally_distinctive(chosen, rankings[i], segments[i].get("text", "")):
            anchors.append(i)
    anchor_set = set(anchors)

    for i, row in enumerate(rows):
        chosen = selected[i]
        words = normalize(row.get("text", "")).split()
        score = chosen["score"] if chosen else (rankings[i][0]["score"] if rankings[i] else 0)
        neighbors = [j for j in anchors if block_for.get(j) == block_for.get(i)
                     and abs(float(segments[j].get("start", 0)) - float(row.get("start", 0))) <= 150
                     and selected[j]["service_id"] == (chosen or {}).get("service_id")]
        before = next((j for j in reversed(neighbors) if j < i), None)
        after = next((j for j in neighbors if j > i), None)
        accepted, reason, evidence = False, "Insufficient sequence-supported text", []
        common_formula = _common_service_formula(row.get("text", ""))
        location_ambiguous = False
        if chosen and i in anchor_set:
            accepted, reason, evidence = True, "Distinctive text supports this position in the chronological path", [i]
        elif chosen and before is not None and after is not None:
            left, right = selected[before]["index"], selected[after]["index"]
            within = min(left, right) - max_reverse_units <= chosen["index"] <= max(left, right) + max_reverse_units
            if len(words) <= 4:
                within = min(left, right) <= chosen["index"] <= max(left, right)
            close = abs(right - left) <= 45
            if within and close and score >= (0.88 if len(words) <= 3 else 0.74):
                # Identical short replies can identify a section while still
                # leaving several occurrence IDs possible. Do not pick one.
                competing = [c for c in rankings[i] if min(left, right) <= c["index"] <= max(left, right)
                             and c["score"] >= (score - 0.04 if common_formula else max(0.9, score - 0.015))]
                repeated_ambiguous = (len(words) <= 4 or common_formula) and len(competing) > 1 and left != right
                location_ambiguous = repeated_ambiguous
                if not repeated_ambiguous:
                    accepted, reason, evidence = True, "Text located between nearby distinctive sequence anchors", [before, after]
                elif len({c["section_id"] for c in competing}) == 1:
                    row["sequence_section_hint"] = {"section_id": competing[0]["section_id"],
                                                    "section_title": competing[0]["section_title"],
                                                    "service_id": competing[0]["service_id"],
                                                    "reason": "Section supported; repeated response occurrence remains ambiguous"}
        if chosen and not accepted and not location_ambiguous:
            for j in [x for x in (before, after) if x is not None]:
                distance = abs(float(segments[j].get("start", 0)) - float(row.get("start", 0)))
                same_unit = chosen["unit_id"] == selected[j]["unit_id"]
                if common_formula and chosen["section_id"] != selected[j]["section_id"]:
                    continue
                nearby = abs(chosen["index"] - selected[j]["index"]) <= 6
                if ((same_unit and distance <= 45 and score >= 0.8 and len(words) >= 3)
                        or (nearby and distance <= 30 and score >= 0.85 and len(words) >= 5)
                        or (nearby and distance <= 90 and score >= 0.88 and len(words) >= 7)):
                    accepted, reason, evidence = True, "Text continues a nearby anchored passage", [j]
                    break
        if chosen and len(words) <= 2 and normalize(row.get("text", "")) not in {normalize(chosen["greek"]), normalize(chosen["english"])}:
            accepted, reason, evidence = False, "One- or two-word partial fragment cannot establish a text association", []
        status = "matched" if accepted else "uncertain" if score >= 0.68 else "unknown"
        if not chosen and rankings[i] and rankings[i][0]["score"] >= 0.68:
            reason = "Lexical candidate conflicts with the supported chronology or lacks evidence"
        decision = _decision(chosen or (rankings[i][0] if rankings[i] else None), status=status,
                             reason=reason if status != "unknown" else "No sufficiently similar text on the chronological path", method="sequence")
        if accepted:
            decision.update(service_id=chosen["service_id"], service_title=chosen["service_title"])
        else:
            decision.update(service_id=None, service_title=None)
        row["match"] = decision
        row["sequence_match"] = dict(decision)
        if i in suspect_repetition:
            decision.update(unit_id=None, unit_index=None, section_id=None, section_title=None, service_id=None,
                            status="uncertain", reason="Repeated long phrase with implausibly short duplicate timestamps; possible ASR repetition artifact")
            row["sequence_match"] = dict(decision)
        row["sequence"] = {"version": ALIGNMENT_VERSION, "block": block_for.get(i),
                           "max_reverse_units": max_reverse_units,
                           "path_unit_id": chosen["unit_id"] if chosen else None,
                           "evidence_segment_ids": [segments[j].get("id", j) for j in evidence],
                           "service_evidence": service_evidence[i]["service_id"] if service_evidence[i] else None,
                           "warnings": ["implausible_repeated_phrase_timestamps"] if i in suspect_repetition else [],
                           "heuristic": True, "independently_verified": False}
        # Preserve global suggestions but make the selected local passage visible
        # even when its lexical rank fell outside the default top six.
        top = rankings[i][:top_k]
        if chosen and chosen["unit_id"] not in {c["unit_id"] for c in top}:
            top = [chosen, *top][:top_k]
        row["candidates"] = top
    return rows
