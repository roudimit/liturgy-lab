import copy
import json
from pathlib import Path

import pytest

from liturgy_lab.reference import combine_service_references, parse_reference


def source_html():
    def row(kind, greek, english):
        return f"<tr><td class='leftCell'><p class='{kind}'>{greek}</p></td><td class='rightCell'><p class='{kind}'>{english}</p></td></tr>"
    return "<table id='biTable'>" + "".join([
        row("mixed", "ΟΡΘΡΟΣ", "MATINS"),
        row("actor", "ΙΕΡΕΥΣ", "PRIEST"),
        row("dialog", "Εὐλογητὸς ὁ Θεός", "Blessed is our God"),
        row("dialogwithactor", "Ἀμήν.", "Amen."),
        row("designation", "", "PRAYER 12"),
        row("inaudible", "", "A private prayer"),
        row("designation", "", "Psalm 142 (143)."),
        row("reading", "Κύριε εἰσάκουσον", "Hear my prayer"),
        row("dialog", "Ἐν εἰρήνῃ", "<span data-key='prayers_en_US_goa|pr.pet01.text'>In peace let us pray to the Lord.</span>"),
        row("heirmos", "Ὑμνοῦμεν", "We sing a hymn"),
        row("dialogzero", "Δόξα σοι", "Glory to You"),
        row("dialog", "Εὐαγγέλιον", "<span data-key='prayers_en_US_goa|pr.gos03a.text'>The reading is from the holy Gospel according to</span> Luke"),
    ]) + "</table>"


def part():
    return parse_reference(source_html(), "https://dcs.goarch.org/goa/dcs/h/s/2026/03/29/ma/gr-en/index.html", service_id="matins")


def test_matins_date_heading_boundary_and_sung_classes():
    reference = part()
    assert reference["date"] == "2026-03-29"
    titles = [s["title"] for s in reference["sections"]]
    assert "PRAYER 12" not in titles
    assert "Peace Litany" in titles
    assert "Matins Gospel" in titles
    hymn = next(u for u in reference["units"] if u["english"] == "We sing a hymn")
    assert hymn["kind"] == "spoken"
    assert hymn["speaker"] == "Choir"
    assert any(u["english"] == "Glory to You" for u in reference["units"])
    private = next(u for u in reference["units"] if u["english"] == "A private prayer")
    assert private["kind"] == "inaudible"


def test_combination_preserves_provenance_and_unique_occurrences():
    original = part()
    snapshot = copy.deepcopy(original)
    services = [{"id": "matins", "title": "Matins (Orthros)", "parts": [original, original]},
                {"id": "liturgy", "title": "Divine Liturgy", "parts": [original]}]
    selection = {"edition_date": "2026-03-29", "status": "same_feast_substitute", "caveat": "Explicit substitute"}
    combined = combine_service_references(services, recording_id="video", selection=selection)
    assert original == snapshot
    assert len({u["id"] for u in combined["units"]}) == len(combined["units"])
    assert len({s["id"] for s in combined["sections"]}) == len(combined["sections"])
    assert [u["index"] for u in combined["units"]] == list(range(len(combined["units"])))
    assert combined["units"][0]["greek"] == original["units"][0]["greek"]
    assert combined["units"][0]["source_unit_id"] == original["units"][0]["id"]
    assert combined["units"][0]["source_url"] == original["source_url"]
    assert combined["units"][0]["service_id"] == "matins"
    assert combined["units"][-1]["service_id"] == "liturgy"
    assert len(combined["sources"]) == 1
    assert combined["selection"]["status"] == "same_feast_substitute"
    assert "Explicit substitute" in combined["notes"]
    all_units = {u["id"]: u for u in combined["units"]}
    for section in combined["sections"]:
        assert all(all_units[uid]["section_id"] == section["id"] for uid in section["unit_ids"])
    assert combine_service_references(services, recording_id="video", selection=selection)["reference_id"] == combined["reference_id"]
    original["units"][0]["greek"] += " Ἀμήν."
    assert combine_service_references(services, recording_id="video", selection=selection)["reference_id"] != combined["reference_id"]


def test_combination_rejects_ambiguous_service_identity():
    service = {"id": "matins", "title": "Matins", "parts": [part()]}
    with pytest.raises(ValueError, match="unique"):
        combine_service_references([service, service], recording_id="v", selection={})
    with pytest.raises(ValueError, match="simple slugs"):
        combine_service_references([{**service, "id": "matins:liturgy"}], recording_id="v", selection={})


def test_saved_references_include_common_matins_and_correct_liturgy_family():
    data = Path(__file__).resolve().parents[1] / "data"
    if not (data / "reference-manifest.json").exists():
        pytest.skip("Cached official reference editions are not present")
    for item in json.loads((data / "reference-manifest.json").read_text()):
        reference = json.loads((data / item["file"]).read_text())
        assert reference["reference_id"] == item["reference_id"]
        assert len(reference["sources"]) == 3
        assert [s["id"] for s in reference["services"]] == ["matins", "liturgy"]
        assert any(s["title"] == "The Six Psalms" and s["service_id"] == "matins" for s in reference["sections"])
        assert any(s["title"] == "Great Doxology" and s["service_id"] == "matins" for s in reference["sections"])
        assert reference["units"][0]["english"].startswith("Blessed is our God")
        assert any(u["greek"].startswith("Εὐλογημένη") or u["greek"].startswith("Εὐλογημένη") for u in reference["units"] if u["service_id"] == "liturgy")
        if item["recording_id"] == "IuZ8WRk-POI":
            assert reference["selection"]["status"] == "exact_calendar_date"
            assert reference["services"][1]["title"] == "Divine Liturgy of St. Basil"
        else:
            assert "substitute" in reference["selection"]["status"]


def test_december_calendar_reconstruction_has_expected_readings_and_prayers():
    data = Path(__file__).resolve().parents[1] / "data"
    expectations = [("vkkeLmltf_4", 2, 5, "le.go.mc.d073"),
                    ("n674zECLjTI", 4, 7, "le.go.eo.w07")]
    for recording_id, mode, eothinon, gospel_key in expectations:
        path = data / f"reference-{recording_id}.json"
        if not path.exists():
            pytest.skip("Cached references not present")
        reference = json.loads(path.read_text())
        assert reference["selection"]["status"] == "calendar_component_substitute"
        assert reference["selection"]["mode"] == mode
        assert reference["selection"]["eothinon"] == eothinon
        matins = [u for u in reference["units"] if u["service_id"] == "matins"]
        assert any(any(k.startswith(gospel_key) and k.endswith("Gospel.text") for k in u["source_keys"]) for u in matins)
        intercession = next(u for u in matins if any(k.endswith("|pr.sup00.text") for k in u["source_keys"]))
        assert intercession["section_title"] == "Great Intercession"
        assert any("honorable, heavenly, bodiless powers" in u["english"] for u in matins)
        assert not any("Î" in u["greek"] or "Ï" in u["greek"] for u in reference["units"])
        composite = [s for s in reference["sources"] if s.get("source_is_composite")]
        assert len(composite) == 2
        assert all(s["composition_sources"] and s["composition_operations"] and s["base_source_sha256"] != s["source_sha256"] for s in composite)
        assert any(u.get("composition_source_urls") for u in reference["units"])
        if recording_id == "n674zECLjTI":
            keys = [k for u in reference["units"] for k in u["source_keys"]]
            assert any(k.startswith("le.ep.mc.d260") and k.endswith("Epistle.text") for k in keys)
            assert not any(k.startswith(("le.ep.mc.d086", "me.m12.d27", "me.m08.d02")) for k in keys)
            assert len(reference["selection"]["unavailable_exact_sources"]) == 2


def test_december_resurrectional_apolytikia_match_the_verified_mode_in_both_services():
    data = Path(__file__).resolve().parents[1] / "data"
    for recording_id, mode, donor_date in [("vkkeLmltf_4", 2, "2026-12-06"), ("n674zECLjTI", 4, "2026-12-20")]:
        path = data / f"reference-{recording_id}.json"
        if not path.exists():
            pytest.skip("Cached references not present")
        reference = json.loads(path.read_text())
        donor_url = f"https://dcs.goarch.org/goa/dcs/h/s/{donor_date.replace('-', '/')}/ma/gr-en/index.html"
        donor = parse_reference((data / "reference-sources" / f"{donor_date}-ma.html").read_text(), donor_url, service_id="matins")
        hymn_key = f"oc.m{mode}.d1_en_US_goadedes|ocVE.Apolytikion.text"
        canonical = next(u for u in donor["units"] if hymn_key in u["source_keys"])
        occurrences = [u for u in reference["units"] if hymn_key in u["source_keys"]]
        assert {u["service_id"] for u in occurrences} == {"matins", "liturgy"}
        for unit in occurrences:
            assert (unit["greek"], unit["english"]) == (canonical["greek"], canonical["english"])
            assert donor_url in unit["composition_source_urls"]
        assert not any("heAU.TonSynanarchonLogon.text" in key for u in reference["units"] for key in u["source_keys"])
