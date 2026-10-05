"""Import GOARCH's bilingual table without mistaking rubrics for speech.

The imported date is a reference edition, not the date of a recording. Optional
rites and prayers said inaudibly are retained for reading, but not ASR matching.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

DEFAULT_URL = "https://dcs.goarch.org/goa/dcs/h/s/2026/09/30/li/gr-en/index.html"
SPOKEN_CLASSES = {"dialog", "dialogzero", "dialogwithactor", "hymn", "heirmos", "verse", "versezero", "reading", "readingzero", "chant", "alttext"}
IGNORED_CLASSES = {"mode", "greekmelody", "chapverse", "noprintdesig", "break"}


def _text(node: Tag | None, *, spoken: bool = False) -> str:
    if node is None:
        return ""
    node = copy.copy(node)
    for extra in node.select("script, style, a, .versiondesignation, .key, .hidden, [hidden], .dummy"):
        extra.decompose()
    if spoken:
        for extra in node.select(".actorwithdialog"):
            extra.decompose()
        for extra in node.select("[data-key]"):
            key = extra.get("data-key", "")
            if key.startswith(("actors_", "rubrical_")) or re.search(r"\|misc\.vVerse\d", key):
                extra.decompose()
    return " ".join(node.get_text(" ", strip=True).split())


def _section_title(english: str, classes: set[str]) -> str | None:
    """Only visible source headings become section boundaries."""
    if not english or not re.search(r"[A-Za-z]", english):
        return None
    if "designation" in classes:
        title = re.sub(r"\s+Mode\s+.*$", "", english).strip(" .")
        if re.match(r"(?:PRAYER|SECOND PRAYER|ENTRANCE PRAYER|OFFERTORY PRAYER|AMBO PRAYER)\b", title):
            return None
        # These are local hymn labels within a larger clearly named section.
        if title.startswith(("Apolytikion", "Dynamis", "Kontakion", "Evlogetaria")):
            return None
        return title
    if "mixed" not in classes and "smallcenterboldred" not in classes:
        return None
    if not english.isupper() or english.startswith(("LITURGY OF", "PRAYER", "SECOND PRAYER", "ENTRANCE PRAYER", "OFFERTORY PRAYER", "AMBO PRAYER")):
        return None
    names = {
        "ENARXIS, PEACE LITANY, AND ANTIPHONS": "Opening blessing and Peace Litany",
        "THE ENTRANCE": "Small Entrance",
        "THE TRISAGIOS HYMN": "Trisagios Hymn",
        "THE READINGS": "Readings",
        "ENTRANCE OF THE HOLY GIFTS": "Great Entrance",
        "KISS OF PEACE AND CREED": "Kiss of Peace and Creed",
        "HOLY ANAPHORA": "Holy Anaphora",
        "THE LORD’S PRAYER": "The Lord’s Prayer",
        "ELEVATION – FRACTION – UNION – COMMUNION": "Elevation, Fraction, and Communion",
    }
    return names.get(english, english.title())


def parse_reference(html: str, source_url: str = DEFAULT_URL, *, service_id: str | None = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#biTable")
    if table is None:
        raise ValueError("Expected the GOARCH bilingual #biTable; source format may have changed")
    title = _text(soup.select_one("td.rightCell .sb_cover1"))
    date_text = _text(soup.select_one("td.rightCell .sb_cover3"))
    commemoration = _text(soup.select_one("td.rightCell .sb_cover4"))
    credits = list(dict.fromkeys(_text(x) for x in soup.select("td.rightCell .sb_credits3") if _text(x)))
    books = list(dict.fromkeys(_text(x) for x in soup.select("td.rightCell .servicesources, td.rightCell .servicesourcessection") if _text(x)))
    if not title:
        title = next((book for book in books if "Divine Liturgy" in book), "Matins (Orthros)" if service_id == "matins" else "Service reference")
    if not commemoration:
        commemoration = "; ".join(book for book in books if "Sunday" in book or "Theotokos" in book)
    sections: list[dict] = []
    units: list[dict] = []
    speaker: str | None = None
    current: dict | None = None

    def begin_section(name: str, heading: str) -> None:
        nonlocal current
        if current and current["title"] == name:
            return
        # A source can stack a general heading then a specific heading before
        # any content. Keep the latter rather than creating an empty chapter.
        if current and not current["unit_ids"]:
            current.update(title=name, source_heading=heading)
            return
        current = {"id": f"s{len(sections):03d}", "title": name,
                   "source_heading": heading, "unit_ids": []}
        sections.append(current)

    for row_number, row in enumerate(table.select("tr")):
        left, right = row.select_one("td.leftCell"), row.select_one("td.rightCell")
        if left is None and right is None:
            continue
        lp = left.find("p", recursive=False) if left else None
        rp = right.find("p", recursive=False) if right else None
        node = rp if rp is not None else lp
        if node is None:
            continue
        classes = set(node.get("class", []))
        # The optional Memorial Service is embedded before the final dismissal.
        # Its explicit end marker restores the ordinary Liturgy boundary even
        # though GOARCH does not repeat a visible heading at that exact row.
        if "erc_li_memorial_service" in classes and current and current["title"] == "Memorial Service":
            begin_section("Final blessing and dismissal", "End of optional Memorial Service (GOARCH rubric marker)")
            continue
        if any(c.startswith(("sb", "servicesource", "bkmrk", "brc_", "erc_", "bmc_", "emc_")) for c in classes):
            continue
        if classes & IGNORED_CLASSES:
            continue
        en_raw, el_raw = _text(rp), _text(lp)
        if classes & {"actor", "actorinaudible"}:
            speaker = en_raw.strip(": ").title() or el_raw
            continue
        # The common Matins source has no separate visible heading after Psalm
        # 142. Its explicit first petition marks the following Peace Litany.
        if service_id == "matins" and current and current["title"].startswith("Psalm 142") and node.select_one('[data-key$="|pr.pet01.text"]'):
            begin_section("Peace Litany", "In peace let us pray to the Lord (source prayer key)")
        if service_id == "matins" and node.select_one('[data-key$="|pr.gos03a.text"]'):
            begin_section("Matins Gospel", "The reading is from the holy Gospel (source prayer key)")
        if service_id == "matins" and node.select_one('[data-key$="|pr.sup00.text"]'):
            begin_section("Great Intercession", "O God, save Your people (source prayer key; editorial section label)")
        section = _section_title(en_raw, classes)
        if section:
            begin_section(section, en_raw)
            continue
        if classes & {"mixed", "designation", "smallcenterboldred"}:
            # Includes prayer headings and performance instructions. They must
            # not compete with actually spoken phrases in retrieval.
            kind = "rubric"
        elif "inaudible" in classes:
            kind = "inaudible"
        elif classes & SPOKEN_CLASSES:
            kind = "spoken"
        elif "rubric" in classes:
            kind = "rubric"
        else:
            continue
        greek, english = _text(lp, spoken=kind == "spoken"), _text(rp, spoken=kind == "spoken")
        if not (greek or english) or not re.search(r"[^\W\d_]", greek + english, re.UNICODE):
            continue
        if current is None:
            if kind != "spoken":
                continue
            begin_section("Opening", "Opening")
        actor = rp.select_one(".actorwithdialog") if rp else None
        unit_speaker = _text(actor).strip(": ").title() if actor else speaker
        if classes & {"hymn", "heirmos", "chant", "verse", "versezero"} and actor is None:
            unit_speaker = "Choir"
        # Stable occurrence IDs preserve distinct instances of repeated replies.
        unit = {"id": f"u{len(units):04d}", "index": len(units),
                "section_id": current["id"], "section_title": current["title"],
                "speaker": unit_speaker, "greek": greek, "english": english,
                "kind": kind, "source_row": row_number,
                "source_keys": list(dict.fromkeys(x["data-key"] for x in node.select("[data-key]"))),
                "greek_source_keys": list(dict.fromkeys(x["data-key"] for x in lp.select("[data-key]"))) if lp else [],
                "english_source_keys": list(dict.fromkeys(x["data-key"] for x in rp.select("[data-key]"))) if rp else []}
        units.append(unit)
        current["unit_ids"].append(unit["id"])
    sections = [section for section in sections if section["unit_ids"]]
    if len(units) < 5:
        raise ValueError("Too few bilingual units imported; check the reference HTML")
    date_match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/(?:li\d*|ma\d*)/", source_url)
    return {"schema_version": 1, "source_url": source_url, "title": title,
            "date": "-".join(date_match.groups()) if date_match else None,
            "date_text": date_text, "commemoration": commemoration,
            "source_sha256": hashlib.sha256(html.encode()).hexdigest(),
            "attribution": "Digital Chant Stand — Greek Orthodox Archdiocese of America",
            "source_credits": credits,
            "books": books,
            "notes": ["Reference edition date is not evidence of the recording date.",
                      "Daily readings and hymns vary; optional rites and inaudible prayers are included in this edition.",
                      "Reference text is imported source material, never an ASR transcript."],
            "sections": sections, "units": units}


def combine_service_references(services: list[dict], *, recording_id: str, selection: dict) -> dict:
    """Namespace ordered service parts without presenting substitutions as exact.

    Each service is {id, title, parts: [parsed_reference, ...]}. Matins may have
    the separately published common opening before its dated proper. Original
    source text and occurrence identity survive; only IDs/indexes are remapped.
    """
    units, sections, sources, service_metadata = [], [], [], []
    seen_services = set()
    for service in services:
        service_id, service_title = service["id"], service["title"]
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", service_id) or service_id in seen_services:
            raise ValueError("Service identifiers must be unique simple slugs")
        seen_services.add(service_id)
        service_units, service_sections, source_ids = [], [], []
        for part in service["parts"]:
            source_id = "source-" + hashlib.sha256((part["source_url"] + part["source_sha256"]).encode()).hexdigest()[:16]
            if not any(s["id"] == source_id for s in sources):
                metadata = {k: copy.deepcopy(part.get(k)) for k in ["source_url", "source_sha256", "title", "date", "date_text", "commemoration", "attribution", "source_credits", "books"]}
                for key in ("source_is_composite", "base_source_sha256", "composition_sources", "composition_operations", "composition_file"):
                    if key in part:
                        metadata[key] = copy.deepcopy(part[key])
                sources.append({"id": source_id, **metadata})
            source_ids.append(source_id)
            section_map = {}
            for original in part["sections"]:
                section_id = f"{service_id}:s{len(service_sections):03d}"
                section_map[original["id"]] = section_id
                section = {**copy.deepcopy(original), "id": section_id, "unit_ids": [],
                           "service_id": service_id, "service_title": service_title,
                           "source_section_id": original["id"], "source_id": source_id,
                           "source_url": part["source_url"]}
                sections.append(section)
                service_sections.append(section_id)
            by_section = {s["id"]: s for s in sections}
            for original in part["units"]:
                unit_id = f"{service_id}:u{len(service_units):04d}"
                section_id = section_map[original["section_id"]]
                unit = {**copy.deepcopy(original), "id": unit_id, "index": len(units),
                        "service_index": len(service_units), "section_id": section_id,
                        "service_id": service_id, "service_title": service_title,
                        "source_unit_id": original["id"], "source_id": source_id,
                        "source_url": part["source_url"], "source_date": part.get("date")}
                units.append(unit)
                service_units.append(unit_id)
                by_section[section_id]["unit_ids"].append(unit_id)
        service_metadata.append({"id": service_id, "title": service_title, "unit_ids": service_units, "section_ids": service_sections, "source_ids": source_ids})
    identity = json.dumps({"sources": [(s["source_url"], s["source_sha256"]) for s in sources], "units": units, "selection": selection}, ensure_ascii=False, sort_keys=True)
    return {"schema_version": 2, "reference_id": "ref-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
            "recording_id": recording_id, "title": "Matins (Orthros) and Divine Liturgy",
            "source_url": sources[-1]["source_url"] if sources else None,
            "date": selection.get("edition_date"), "selection": copy.deepcopy(selection),
            "attribution": "Digital Chant Stand — Greek Orthodox Archdiocese of America",
            "source_credits": list(dict.fromkeys(credit for source in sources for credit in source.get("source_credits") or [])),
            "notes": ["Matins ordinary is published separately from the dated proper; both are included in service order.",
                      "Canonical Greek is source text, not a corrected ASR transcript.",
                      "Optional rites, local omissions, repetitions, homilies, and language variants can differ from this reference.",
                      "Recording date is inferred from upload/release metadata and title, not independently verified.",
                      selection.get("caveat", "")],
            "sources": sources, "services": service_metadata, "sections": sections, "units": units}


def load_reference(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_reference(html_path: str | Path, json_path: str | Path, source_url: str = DEFAULT_URL) -> dict:
    reference = parse_reference(Path(html_path).read_text(encoding="utf-8"), source_url)
    target = Path(json_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return reference


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html_path", type=Path)
    parser.add_argument("json_path", type=Path)
    parser.add_argument("--source-url", default=DEFAULT_URL)
    args = parser.parse_args()
    result = save_reference(args.html_path, args.json_path, args.source_url)
    print(f"Imported {len(result['units'])} units in {len(result['sections'])} sections")
