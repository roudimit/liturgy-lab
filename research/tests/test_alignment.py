from liturgy_lab.align import align_segments, normalize, retrieve_candidates, detect_liturgy_start, apply_service_context
from liturgy_lab.reference import parse_reference


def make_reference(rows):
    return {"units": [{"id": f"u{i}", "index": i, "greek": el, "english": en,
                       "section_id": f"s{i // 3}", "section_title": f"Section {i // 3}",
                       "kind": "spoken"} for i, (el, en) in enumerate(rows)]}


def test_normalization_removes_polytonic_accents_and_final_sigma():
    assert normalize("Εὐλογημένος, ὁ Θεός!") == normalize("ευλογημενοσ ο θεοσ")


def test_greek_asr_diacritics_and_minor_spelling_errors():
    reference = make_reference([
        ("Εὐλογημένη ἡ βασιλεία τοῦ Πατρὸς καὶ τοῦ Υἱοῦ καὶ τοῦ ἁγίου Πνεύματος.", "Blessed is the kingdom of the Father and the Son and the Holy Spirit."),
        ("Ἐν εἰρήνῃ τοῦ Κυρίου δεηθῶμεν.", "In peace let us pray to the Lord."),
    ])
    raw = {"start": 1807.3, "end": 1817.9, "text": "Εβλογημένη η βασιλεία του Πατρός και του Υιού και του αγίου Πνεύματος"}
    result = align_segments([raw], reference)[0]
    assert result["match"]["unit_id"] == "u0"
    assert result["text"] == raw["text"]
    assert (result["start"], result["end"]) == (1807.3, 1817.9)


def test_repeated_responses_abstain_without_occurrence_context():
    reference = make_reference([
        ("Κύριε ἐλέησον.", "Lord, have mercy."),
        ("Ἀμήν.", "Amen."),
        ("Κύριε ἐλέησον.", "Lord, have mercy."),
    ])
    result = align_segments([{"text": "Κύριε ελέησον"}], reference)[0]
    assert result["match"]["status"] == "uncertain"
    assert result["match"]["unit_id"] is None
    assert result["match"]["section_id"] is None
    assert result["match"]["score"] == 1.0  # Similarity is not probability.


def test_context_requires_two_close_distinctive_anchors():
    reference = make_reference([
        ("", "Lord, have mercy."),
        ("", "For favorable weather an abundance of the fruits of the earth and temperate seasons"),
        ("", "Lord, have mercy."),
        ("", "For travelers by land sea and air for the sick and the suffering"),
        ("", "Lord, have mercy."),
    ])
    segments = [{"start": 100, "end": 110, "text": reference["units"][1]["english"]},
                {"start": 110, "end": 115, "text": "Lord have mercy"},
                {"start": 115, "end": 127, "text": reference["units"][3]["english"]}]
    result = align_segments(segments, reference)
    assert result[1]["match"]["unit_id"] == "u2"
    assert result[1]["match"]["method"] == "context"
    only_left = align_segments(segments[:2], reference)
    assert only_left[1]["match"]["unit_id"] is None
    segments[-1]["start"] = 900
    separated = align_segments(segments, reference)
    assert separated[1]["match"]["unit_id"] is None


def test_unknown_speech_and_empty_segments_are_not_forced_to_reference():
    reference = make_reference([
        ("", "Blessed is the kingdom of the Father and the Son and the Holy Spirit"),
        ("", "For the peace from above and for the salvation of our souls"),
    ])
    results = align_segments([{"text": "Subscribe to our channel and click the notification button"}, {"text": ""}], reference)
    assert all(result["match"]["status"] == "unknown" for result in results)
    assert all(result["match"]["unit_id"] is None for result in results)


def test_excerpt_can_start_anywhere_and_reacquire_after_jumps():
    reference = make_reference([
        ("", "Blessed is the kingdom of the Father and the Son and the Holy Spirit"),
        ("", "Holy God Holy Mighty Holy Immortal have mercy on us"),
        ("", "Let us stand aright let us stand in awe"),
    ])
    result = align_segments([{"text": reference["units"][2]["english"]}, {"text": reference["units"][0]["english"]}], reference)
    assert [s["match"]["unit_id"] for s in result] == ["u2", "u0"]


def test_silent_prayers_do_not_compete_with_spoken_reference():
    reference = make_reference([("", "The secret prayer said privately by the priest"), ("", "For the peace from above and salvation of our souls")])
    reference["units"][0]["kind"] = "inaudible"
    candidates = retrieve_candidates("The secret prayer said privately by the priest", reference)
    assert all(c["unit_id"] != "u0" for c in candidates)


def test_partial_long_prayer_is_retrievable_but_short_word_overlap_is_not():
    reference = make_reference([
        ("", "Let us stand aright let us stand in awe let us be attentive that we may present the holy offering in peace"),
        ("", "Amen"),
    ])
    fragment = align_segments([{"text": "be attentive that we may present the holy offering in peace"}], reference)[0]
    assert fragment["match"]["unit_id"] == "u0"
    unrelated = align_segments([{"text": "We discuss the forecast and the football game this evening amen"}], reference)[0]
    assert unrelated["match"]["unit_id"] is None


def test_importer_tracks_speakers_rubrics_and_distinct_repeated_occurrences():
    def row(cls, el, en):
        return f"<tr><td class='leftCell'><p class='{cls}'>{el}</p></td><td class='rightCell'><p class='{cls}'>{en}</p></td></tr>"
    html = "<table id='biTable'>" + "".join([
        row("sb_cover1", "", "The Divine Liturgy"),
        row("sb_cover3", "", "on Wednesday, September 30, 2026"),
        row("mixed", "", "ENARXIS, PEACE LITANY, AND ANTIPHONS"),
        row("actor", "", "PRIEST"),
        row("dialog", "Εὐλογημένη ἡ βασιλεία", "Blessed is the kingdom"),
        row("dialogwithactor", "Κύριε ἐλέησον", "<span class='actorwithdialog'>CHOIR:</span> Lord, have mercy.<span class='versiondesignation'>[GOA]</span>"),
        row("dialog", "", "Let us pray to the Lord"),
        row("dialogwithactor", "Κύριε ἐλέησον", "<span class='actorwithdialog'>CHOIR:</span> Lord, have mercy."),
        row("inaudible", "", "A prayer said privately"),
        row("rubric", "", "The priest bows three times"),
        row("designation", "", "Antiphon 1. Mode 2."),
        row("hymn", "", "Through the intercessions of the Theotokos"),
    ]) + "</table>"
    reference = parse_reference(html)
    assert reference["date"] == "2026-09-30"
    assert [s["title"] for s in reference["sections"]] == ["Opening blessing and Peace Litany", "Antiphon 1"]
    units = reference["units"]
    assert units[0]["speaker"] == "Priest"
    assert units[1]["english"] == "Lord, have mercy."
    assert units[1]["speaker"] == "Choir"
    assert units[1]["id"] != units[3]["id"]
    assert units[4]["kind"] == "inaudible"
    assert units[5]["kind"] == "rubric"
    assert all("GOA" not in u["english"] for u in units)


def test_opening_detection_handles_split_greek_without_accepting_shared_doxology():
    matins = [{"id": "a", "start": 1832, "end": 1837, "text": "Ότι ευλόγητε σου το όνομα και δόξαστε σου η"},
              {"id": "b", "start": 1837, "end": 1848, "text": "Βασιλεία του Πατρός και του Υιού και του Αγίου Πνεύματος"}]
    assert detect_liturgy_start(matins)["detected"] is False
    opening = [{"id": "c", "start": 4000, "end": 4004, "text": "Ευλογημένη η βασιλεία"},
               {"id": "d", "start": 4004, "end": 4010, "text": "του Πατρός και του Υιού και του Αγίου Πνεύματος"}]
    result = detect_liturgy_start(matins + opening)
    assert result["start"] == 4000
    assert result["heuristic"] is True
    assert result["independently_verified"] is False
    assert result["evidence"][0]["segment_id"] == "c"
    opening[1]["start"] = 6000
    assert detect_liturgy_start(opening)["detected"] is False


def test_pre_liturgy_shared_text_does_not_create_section_navigation():
    original = {"unit_id": "u2", "section_id": "s1", "section_title": "The Lord’s Prayer",
                "status": "matched", "score": 0.95, "reason": "Distinctive text match"}
    segments = [{"start": 360, "text": "Thy will be done", "match": original, "llm_match": original},
                {"start": 4100, "text": "Let us pray", "match": original}]
    gated = apply_service_context(segments, {"start": 4000})
    assert gated[0]["match"]["unit_id"] is None
    assert gated[0]["llm_match"]["unit_id"] is None
    assert gated[0]["textual_match"] == original
    assert gated[0]["llm_textual_match"] == original
    assert gated[1]["match"]["unit_id"] == "u2"
    assert original["unit_id"] == "u2"  # No mutation.
    no_opening = apply_service_context(segments, None)
    assert all(s["match"]["unit_id"] is None for s in no_opening)
    sampled = apply_service_context(segments, None, known_complete_start=False)
    assert sampled[0]["match"]["context_unverified"] is True
    assert sampled[0]["textual_match"]["unit_id"] == "u2"


def test_shared_fragment_far_ahead_of_supported_liturgy_block_abstains():
    # A generic phrase appearing in Communion does not locate Communion when
    # the recording immediately proceeds through the Gospel dialogue.
    units = [263, 124, 125, 126]
    rows = [{"id": str(i), "start": 5302 + 10 * i, "text": "shared text" if i == 0 else "distinctive text",
             "match": {"unit_id": f"u{ui}", "unit_index": ui, "section_id": "s1",
                       "status": "matched", "score": 1.0}}
            for i, ui in enumerate(units)]
    results = apply_service_context(rows, {"start": 4400})
    assert results[0]["match"]["unit_id"] is None
    assert results[0]["textual_match"]["unit_id"] == "u263"
    assert all(s["match"]["unit_id"] for s in results[1:])
    # Arbitrary noncontiguous samples must not be forced into source order.
    assert apply_service_context(rows, {"start": 4400}, known_complete_start=False)[0]["match"]["unit_id"] == "u263"


def test_four_common_words_in_a_sermon_do_not_locate_a_long_prayer():
    reference = make_reference([("", "For the peace of the whole world for the stability of the holy churches of God and for the unity of all let us pray to the Lord")])
    row = align_segments([{"start": 7528.18, "text": "of the whole world."}], reference)[0]
    assert row["match"]["unit_id"] is None
    assert row["match"]["score"] == 1.0
    # Service-context validation also catches old experimental output generated
    # before this restriction, without discarding its original textual decision.
    row["match"].update(unit_id="u0", section_id="s0", status="matched")
    gated = apply_service_context([row], {"start": 4411.84})[0]
    assert gated["match"]["unit_id"] is None
    assert gated["textual_match"]["unit_id"] == "u0"
