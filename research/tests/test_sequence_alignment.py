from liturgy_lab.align import align_sequence, retrieve_candidates


def reference(texts, services=None):
    return {"units": [{"id": f"u{i}", "index": i, "kind": "spoken", "english": text, "greek": "",
                       "section_id": f"s{i // 5}", "section_title": f"Section {i // 5}",
                       "service_id": services[i] if services else "liturgy", "service_title": "Liturgy"}
                      for i, text in enumerate(texts)]}


def segments(texts, times=None):
    return [{"id": str(i), "start": times[i] if times else i * 10, "end": (times[i] if times else i * 10) + 8,
             "text": text} for i, text in enumerate(texts)]


def test_repeated_response_tracks_correct_occurrence_between_petitions():
    ref = reference(["Lord have mercy", "For favorable weather abundance of the fruits of the earth",
                     "Lord have mercy", "For travelers by land sea and air for the sick and suffering",
                     "Lord have mercy"])
    raw = segments([ref["units"][1]["english"], "Lord have mercy", ref["units"][3]["english"]])
    rows = align_sequence(raw, ref)
    assert [r["match"]["unit_id"] for r in rows] == ["u1", "u2", "u3"]
    assert rows[1]["lexical_match"]["unit_id"] is None
    assert rows[1]["text"] == raw[1]["text"]


def test_forward_skips_and_small_reversal_are_allowed():
    texts = ["For this holy house and those who enter with faith",
             "For the peace from above and salvation of our souls",
             "For travelers by land sea and air and those in captivity",
             "For deliverance from affliction wrath danger and necessity",
             "Remembering our most holy pure blessed and glorious Lady"]
    ref = reference(texts)
    rows = align_sequence(segments([texts[0], texts[2], texts[1], texts[4]]), ref)
    assert [r["match"]["unit_id"] for r in rows] == ["u0", "u2", "u1", "u4"]


def test_sermon_remains_unknown_and_cannot_jump_back_to_beginning():
    texts = ["For the peace of the whole world for the stability of the holy churches"]
    texts += [f"Distinctive unused text number {i} about a different ceremony" for i in range(20)]
    texts += ["Through the prayers of our holy fathers Lord Jesus Christ have mercy on us"]
    ref = reference(texts)
    rows = align_sequence(segments([texts[-1], "Please be seated we will discuss our church calendar", "of the whole world"]), ref)
    assert rows[0]["match"]["unit_id"] == "u21"
    assert rows[1]["match"]["unit_id"] is None
    assert rows[2]["match"]["unit_id"] is None


def test_gapped_clips_reacquire_instead_of_forcing_previous_position():
    texts = ["Blessed is the kingdom of the Father and the Son and Holy Spirit"]
    texts += [f"Unused section text number {i}" for i in range(20)]
    texts += ["Let us stand aright let us stand in awe and offer in peace"]
    rows = align_sequence(segments([texts[-1], texts[0]], times=[100, 2000]), reference(texts))
    assert [r["match"]["unit_id"] for r in rows] == ["u21", "u0"]
    assert rows[0]["sequence"]["block"] != rows[1]["sequence"]["block"]


def test_combined_services_match_matins_instead_of_suppressing_it():
    texts = ["Our Father who art in heaven hallowed be thy name",
             "Blessed is the kingdom of the Father and the Son and Holy Spirit",
             "Our Father who art in heaven hallowed be thy name"]
    ref = reference(texts, services=["matins", "liturgy", "liturgy"])
    rows = align_sequence(segments(texts), ref)
    assert rows[0]["match"]["unit_id"] == "u0"
    assert rows[0]["match"]["service_id"] == "matins"
    assert rows[2]["match"]["unit_id"] == "u2"
    assert rows[2]["match"]["service_id"] == "liturgy"


def test_unanchored_repeated_reply_does_not_invent_occurrence():
    rows = align_sequence(segments(["Lord have mercy", "Amen"]), reference(["Lord have mercy", "Amen", "Lord have mercy", "Amen"]))
    assert all(r["match"]["unit_id"] is None for r in rows)


def test_sequence_chooses_local_noisy_phrase_over_impossible_future_match():
    texts = ["For this holy house and for those who enter with faith reverence and fear of God",
             "Remembering our most holy pure blessed and glorious Lady the Theotokos",
             "For favorable weather and an abundance of the fruits of the earth"]
    texts += [f"Unused line number {i} in a different liturgical section" for i in range(40)]
    texts += ["Remember our most holy blessed glorious Lady"]
    ref = reference(texts)
    rows = align_sequence(segments([texts[0], "Remember our most holy blessed glorious Lady", texts[2]]), ref)
    assert rows[1]["lexical_match"]["unit_id"] == "u43"
    assert rows[1]["match"]["unit_id"] == "u1"


def test_latin_spelled_greek_is_retrieval_evidence_without_rewriting_asr():
    ref = reference(["Let us pray to the Lord", "Let us stand aright let us stand in awe"])
    ref["units"][0]["greek"] = "τοῦ Κυρίου δεηθῶμεν"
    ref["units"][1]["greek"] = "Στῶμεν καλῶς στῶμεν μετὰ φόβου"
    candidates = retrieve_candidates("To Kyrieu Dei Thomen", ref)
    assert candidates[0]["unit_id"] == "u0"
    assert candidates[0]["language"] == "el-Latn"
    assert candidates[0]["score"] > 0.8


def test_short_reply_outside_bracketing_passage_does_not_borrow_reversal_allowance():
    ref = reference(["Amen", "Holy God Holy Mighty Holy Immortal have mercy on us"])
    rows = align_sequence(segments([ref["units"][1]["english"], "Amen", ref["units"][1]["english"]]), ref)
    assert rows[1]["match"]["unit_id"] is None


def test_explicit_audio_windows_reset_independently_of_asr_endpoint_gaps():
    ref = reference(["For the peace from above and salvation of our souls"] + [f"unused prayer section {i}" for i in range(20)] + ["Let us stand aright let us stand in awe and offer in peace"])
    rows = segments([ref["units"][-1]["english"], ref["units"][0]["english"]])
    rows[0]["clip_id"] = "first-window"
    rows[1]["clip_id"] = "second-window"
    aligned = align_sequence(rows, ref)
    assert [r["match"]["unit_id"] for r in aligned] == ["u21", "u0"]


def test_common_formulas_cannot_move_matins_into_liturgy_without_opening():
    texts = ["Come believers let us see where Christ has been born and follow the star",
             "Both now and forever and to the ages of ages amen",
             "Save us and protect us by your grace"]
    ref = reference(texts, services=["matins", "liturgy", "liturgy"])
    rows = align_sequence(segments(texts), ref)
    assert rows[0]["match"]["unit_id"] == "u0"
    assert all(r["match"]["unit_id"] is None for r in rows[1:])
    assert rows[1]["lexical_match"]["unit_id"] == "u1"


def test_common_formula_cannot_jump_far_ahead_within_service():
    texts = ["Come believers let us see where Christ has been born and follow the star"]
    texts += [f"Unused different passage word number {i}" for i in range(30)]
    texts += ["Both now and forever and to the ages of ages amen"]
    rows = align_sequence(segments([texts[0], texts[-1]]), reference(texts))
    assert rows[0]["match"]["unit_id"] == "u0"
    assert rows[1]["match"]["unit_id"] is None


def test_implausibly_short_repeated_long_phrase_retains_raw_text_but_abstains():
    phrase = "May he have mercy on us and save us for he is good"
    raw = segments([phrase, phrase, phrase], times=[0, 0.4, 0.8])
    for row in raw:
        row["end"] = row["start"] + 0.3
    rows = align_sequence(raw, reference([phrase]))
    assert all(r["match"]["unit_id"] is None for r in rows)
    assert all(r["sequence"]["warnings"] == ["implausible_repeated_phrase_timestamps"] for r in rows)
    assert [r["text"] for r in rows] == [r["text"] for r in raw]


def test_two_distinct_later_service_passages_support_crossing_without_opening():
    texts = ["Come believers let us see where Christ has been born and follow the star",
             "Take eat this is my body which is broken for you",
             "Drink from this all of you this is my blood of the new covenant"]
    rows = align_sequence(segments(texts), reference(texts, ["matins", "liturgy", "liturgy"]))
    assert [r["match"]["unit_id"] for r in rows] == ["u0", "u1", "u2"]


def test_single_word_partial_does_not_borrow_neighboring_anchors():
    text = "He has granted to us eternal life and great mercy"
    rows = align_sequence(segments([text, "He", text]), reference([text]))
    assert rows[0]["match"]["status"] == rows[2]["match"]["status"] == "matched"
    assert rows[1]["match"]["unit_id"] is None


def test_function_word_heavy_fragment_cannot_anchor_a_large_appendix_jump():
    texts = ["Save your people and bless your inheritance"]
    texts += [f"Unused separate passage number {i}" for i in range(30)]
    texts += ["Let us ask for the mercies of God the kingdom of heaven and the forgiveness of their sins"]
    rows = align_sequence(segments([texts[0], texts[0], "in the kingdom of heaven", "and in the kingdom of heaven"]), reference(texts))
    assert rows[0]["match"]["unit_id"] == "u0"
    assert all(r["match"]["unit_id"] is None for r in rows[2:])


def test_common_formula_cannot_borrow_one_sided_anchor_from_another_section():
    ref = reference(["Now and forever and to the ages of ages", "May this blessing come upon you by divine grace and love for mankind"])
    ref["units"][1]["section_id"] = "later-section"
    rows = align_sequence(segments([u["english"] for u in ref["units"]]), ref)
    assert rows[0]["match"]["unit_id"] is None
    assert rows[1]["match"]["unit_id"] == "u1"


def test_shared_formula_between_sections_cannot_choose_an_early_boundary():
    shared = "Now and forever and to the ages of ages"
    ref = reference(["Protect all travelers on their journey and bring them safely home. " + shared,
                     "Master Lord who has established the orders and hosts of angels in heaven. " + shared])
    ref["units"][1]["section_id"] = "later-section"
    rows = align_sequence(segments([ref["units"][0]["english"], shared, ref["units"][1]["english"]]), ref)
    assert rows[0]["match"]["unit_id"] == "u0"
    assert rows[1]["match"]["unit_id"] is None
    assert rows[2]["match"]["unit_id"] == "u1"
