"""Reconstruct December calendar components from attributed official DCS text.

The exact 2025 DCS books were unavailable. These are explicitly composite
substitutes, not recovered editions or verified recordings. Run after
build_references.py; only the two December files and their manifest rows change.
Cached donor HTML is retained unchanged in data/reference-sources.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from liturgy_lab.reference import combine_service_references, parse_reference
from build_references import CONFIGURATIONS, ORDINARY, DECEMBER_CALENDAR

DATA = ROOT / "data"
CACHE = DATA / "reference-sources"
BASE = "https://dcs.goarch.org/goa/dcs/h/s"
CONFIG = {
    "vkkeLmltf_4": {"old_mode": 3, "mode": 2, "old_eothinon": 6, "eothinon": 5,
        "donors": ["2026-12-06-ma", "2026-02-08-ma", "2026-08-16-ma", "2026-12-14-ma"],
        "gospel_old": "le.go.mc.d110", "gospel_new": "le.go.mc.d073",
        "matins_reading": "Luke 24:12–35", "epistle": "Colossians 3:4–11", "gospel": "Luke 14:16–24",
        "tone_evidence": "https://bulletinbuilder.org/SNC-SanJose/current/20251214",
        "old_day": "13", "day": "14"},
    "n674zECLjTI": {"old_mode": 5, "mode": 4, "old_eothinon": 8, "eothinon": 7,
        "donors": ["2026-12-20-ma", "2026-12-28-ma", "2026-10-23-li", "2026-12-27-h91"],
        "gospel_old": "le.go.eo.w08", "gospel_new": "le.go.eo.w07",
        "matins_reading": "John 20:1–10", "epistle": "Galatians 1:11–19", "gospel": "Matthew 2:13–23",
        "tone_evidence": "https://bulletinbuilder.org/stgeorgeocean/current/20251228",
        "old_day": "27", "day": "28"},
}


def source_url(name: str) -> str:
    date, code = name.rsplit("-", 1)
    return f"{BASE}/{date.replace('-', '/')}/{code}/gr-en/index.html"


def keyed_nodes(soup):
    return soup.select("#biTable td p [data-key]")


def nearest_mode_row(node):
    row = node.find_parent("tr")
    for previous in row.find_previous_siblings("tr", limit=4):
        keys = [x["data-key"] for x in previous.select("p [data-key]")]
        if any("|misc.Mode" in key for key in keys):
            return previous
        if any(re.search(r"\|(oc|me|eo|he).+\.text$", key) for key in keys):
            return None
    return None


def compose(base_name: str, settings: dict, service: str) -> dict:
    original = (CACHE / f"{base_name}.html").read_text()
    soup = BeautifulSoup(original, "html.parser")
    donors = [(name, BeautifulSoup((CACHE / f"{name}.html").read_text(), "html.parser")) for name in settings["donors"]]
    index = {}
    for name, donor in donors:
        for node in keyed_nodes(donor):
            index.setdefault(node["data-key"], (name, node))
    operations = []

    def replace_node(node, new_key, reason):
        if new_key not in index:
            if not node.get_text(strip=True):
                node.decompose()
                return
            raise ValueError(f"Missing official donor {new_key}")
        name, donor_node = index[new_key]
        replacement = copy.deepcopy(donor_node)
        replacement["data-composition-source"] = source_url(name)
        replacement["data-original-key"] = node["data-key"]
        operations.append({"operation": "replace", "reason": reason, "old_key": node["data-key"], "new_key": new_key, "source_url": source_url(name)})
        node.replace_with(replacement)

    # Hymns, Hypakoe, anavathmoi, lauds, and the resurrectional Matins prokeimenon.
    old_mode, mode = settings["old_mode"], settings["mode"]
    old_eo, eo = settings["old_eothinon"], settings["eothinon"]
    heading_replacements = set()
    for node in list(keyed_nodes(soup)):
        key = node["data-key"]
        new_key = key.replace(f"oc.m{old_mode}.d1_", f"oc.m{mode}.d1_")
        # DCS publishes the Mode5 resurrectional apolytikion under its
        # automelon/heirmologion alias, rather than an oc.m5 key. Replace this
        # exact hymn alias only; other fixed-feast Mode5 hymns stay untouched.
        apolytikion_alias = re.fullmatch(r"he\.a\.m5_(.+)\|heAU\.TonSynanarchonLogon\.text", key) if old_mode == 5 else None
        if apolytikion_alias:
            new_key = f"oc.m{mode}.d1_{apolytikion_alias.group(1)}|ocVE.Apolytikion.text"
        new_key = new_key.replace(f"|psMA.sunday.m{old_mode}.", f"|psMA.sunday.m{mode}.")
        new_key = new_key.replace(f"eo.e{old_eo:02d}_", f"eo.e{eo:02d}_")
        new_key = new_key.replace(f"le.go.eo.w{old_eo:02d}_", f"le.go.eo.w{eo:02d}_")
        if service == "matins":
            new_key = new_key.replace(settings["gospel_old"] + "_", settings["gospel_new"] + "_")
        if new_key == key:
            continue
        # A kathisma's tune heading belongs with that hymn, not the old mode.
        if (key.startswith(f"oc.m{old_mode}.") and key.endswith(".text")) or apolytikion_alias:
            preceding = nearest_mode_row(node)
            name, donor_node = index[new_key]
            donor_heading = nearest_mode_row(donor_node)
            if preceding is not None and donor_heading is not None and id(preceding) not in heading_replacements:
                heading_replacements.add(id(preceding))
                replacement = copy.deepcopy(donor_heading)
                replacement["data-composition-source"] = source_url(name)
                preceding.replace_with(replacement)
        replace_node(node, new_key, "verified resurrectional mode/eothinon")

    # Cover and major section mode labels not immediately adjacent to a hymn.
    for node in list(keyed_nodes(soup)):
        key = node["data-key"]
        if f"|misc.Mode{old_mode}" not in key:
            continue
        row = node.find_parent("tr")
        keys = [n["data-key"] for n in row.select("p [data-key]")]
        if any("Octoechos" in k or "|ti.Lauds" in k or "|ti.Antiphon" in k for k in keys):
            new_key = key.replace(f"|misc.Mode{old_mode}", f"|misc.Mode{mode}")
            if new_key in index:
                replace_node(node, new_key, "mode heading")

    # The civil day's Synaxarion is distinct from the retained Sunday proper.
    daily_old, daily_new = f"sy.m12.d{settings['old_day']}_", f"sy.m12.d{settings['day']}_"
    old_rows = []
    for node in keyed_nodes(soup):
        if node["data-key"].startswith(daily_old) and "commemoration" in node["data-key"]:
            row = node.find_parent("tr")
            if not any(row is x for x in old_rows):
                old_rows.append(row)
    if service == "matins" and old_rows:
        donor_name, daily = next((name, d) for name, d in donors if name.startswith(f"2026-12-{settings['day']}-"))
        replacements = []
        for row in daily.select("#biTable tr"):
            if any(n["data-key"].startswith(daily_new) and "commemoration" in n["data-key"] for n in row.select("p [data-key]")):
                replacement = copy.deepcopy(row)
                replacement["data-composition-source"] = source_url(donor_name)
                replacements.append(replacement)
        for replacement in replacements:
            old_rows[0].insert_before(replacement)
        for row in old_rows:
            row.decompose()
        operations.append({"operation": "replace_daily_synaxarion", "removed_rows": len(old_rows), "inserted_rows": len(replacements), "source_url": source_url(donor_name)})

    # Variable saint insertions inside longer prayers retain the same-day source.
    for node in list(keyed_nodes(soup)):
        key = node["data-key"]
        if key.startswith(f"me.m12.d{settings['old_day']}_") and "|meDA.insert" in key:
            new_key = key.replace(f"me.m12.d{settings['old_day']}_", f"me.m12.d{settings['day']}_")
            if new_key in index:
                replace_node(node, new_key, "civil date saint insertion")
            elif settings["day"] == "28":
                operations.append({"operation": "remove_unrelated_dec27_saint_insertion", "old_key": key})
                node.decompose()

    if settings["day"] == "28":
        # Remove known Dec27-only St Stephen propers, retaining Nativity and
        # Joseph/David/James propers. This is a deliberate partial reconstruction:
        # no unverified local hymn or performative order is invented.
        for row in list(soup.select("#biTable tr")):
            keys = [n["data-key"] for n in row.select("p [data-key]")]
            unwanted = [k for k in keys if k.startswith("me.m08.d02_") or (k.startswith("me.m12.d27_") and any(x in k for x in ["Lauds", "Exaposteilarion"]))]
            right = row.select_one("td.rightCell p")
            heading = right.get_text(" ", strip=True) if right else ""
            if unwanted or ("Stephen" in heading and right and set(right.get("class", [])) & {"mixed", "designation"}):
                operations.append({"operation": "remove_unrelated_dec27_proper", "keys": keys})
                row.decompose()

        if service == "liturgy":
            # Replace Acts (Stephen) with the calendar's Galatians1:11–19.
            for suffix in ("chapverse", "text"):
                target = next(x for x in keyed_nodes(soup) if x["data-key"].endswith(f"|lemcLI.Epistle.{suffix}") and x["data-key"].startswith("le.ep.mc.d086_"))
                donor = next(x for _, d in donors for x in keyed_nodes(d) if x["data-key"].startswith("le.ep.mc.d260_") and x["data-key"].endswith(f"|lemcLI.Epistle.{suffix}"))
                donor_name = next(name for name, d in donors if donor in keyed_nodes(d))
                replacement = copy.deepcopy(donor.find_parent("tr"))
                replacement["data-composition-source"] = source_url(donor_name)
                target.find_parent("tr").replace_with(replacement)
                operations.append({"operation": "replace_epistle_" + suffix, "source_url": source_url(donor_name), "reading": "Galatians 1:11–19"})
            # Reading introduction is a whole bilingual row because Greek word
            # order differs between Acts and Paul's Letter to the Galatians.
            acts = next(x for x in keyed_nodes(soup) if x["data-key"].endswith("|Acts.text"))
            galatians = next(x for name, d in donors if name == "2026-10-23-li" for x in keyed_nodes(d) if x["data-key"].endswith("|Galatians.text"))
            replacement = copy.deepcopy(galatians.find_parent("tr"))
            replacement["data-composition-source"] = source_url("2026-10-23-li")
            acts.find_parent("tr").replace_with(replacement)
            operations.append({"operation": "replace_epistle_introduction", "source_url": source_url("2026-10-23-li")})
            # The old Dec27 prokeimenon is explicitly a St Stephen proper. The
            # local prokeimenon is unverified, so leave it uncovered instead of
            # presenting an unrelated passage as a canonical prediction.
            for row in list(soup.select("#biTable tr")):
                if any("|psLI.m12.d27.prokeimenon" in n["data-key"] for n in row.select("p [data-key]")):
                    row.decompose()
            operations.append({"operation": "omit_unverified_prokeimenon", "reason": "Dec27 St Stephen proper is not evidence for Dec28 Sunday after Nativity"})

    composite_html = str(soup)
    filename = f"composite-2025-12-{settings['day']}-{service}.html"
    (CACHE / filename).write_text(composite_html)
    result = parse_reference(composite_html, source_url(base_name), service_id=service)
    result["source_is_composite"] = True
    result["base_source_sha256"] = hashlib.sha256(original.encode()).hexdigest()
    result["composition_file"] = "reference-sources/" + filename
    result["composition_sources"] = [{"source_url": source_url(name), "file": f"reference-sources/{name}.html", "source_sha256": hashlib.sha256((CACHE / f"{name}.html").read_bytes()).hexdigest()} for name, _ in donors]
    result["composition_operations"] = operations
    result["title"] += " · calendar-component reconstruction"
    result["date_text"] = f"Composite for 2025-12-{settings['day']}; base edition {base_name[:10]}"
    # Record row-level donor attribution on imported units, including embedded
    # pieces of a prayer. A unit without replacements still cites the base.
    rows = soup.select("#biTable tr")
    for unit in result["units"]:
        row = rows[unit["source_row"]]
        urls = [row.get("data-composition-source")] + [n.get("data-composition-source") for n in row.select("[data-composition-source]")]
        urls = list(dict.fromkeys(url for url in urls if url))
        if urls:
            unit["composition_source_urls"] = urls
    return result


def build_december() -> list[dict]:
    ordinary = parse_reference((CACHE / "matins-ordinary.html").read_text(), ORDINARY, service_id="matins")
    manifest = json.loads((DATA / "reference-manifest.json").read_text())
    reports = []
    for recording_id, settings in CONFIG.items():
        config = next(c for c in CONFIGURATIONS if c["id"] == recording_id)
        edition = config["edition_date"]
        parts = [compose(f"{edition}-ma", settings, "matins"), compose(f"{edition}-li", settings, "liturgy")]
        selection = {k: config[k] for k in ["recording_date", "edition_date", "calendar_url"]}
        selection.update(status="calendar_component_substitute", recording_date_independently_verified=False,
            mode=settings["mode"], eothinon=settings["eothinon"], matins_reading=settings["matins_reading"],
            epistle=settings["epistle"], gospel=settings["gospel"], tone_evidence_url=settings["tone_evidence"],
            reading_evidence_url=DECEMBER_CALENDAR,
            caveat=f"The exact {config['recording_date']} DCS pages were unavailable. This composite retains the {edition} same-Sunday layout and feast propers, with official DCS Mode {settings['mode']}, Eothinon {settings['eothinon']} ({settings['matins_reading']}), and same civil-date commemorations substituted. The 2025 GOARCH calendar and dated parish bulletin support these components. This is a documented reconstruction, not the exact 2025 book; local choices, omitted prayers, and hymn order remain unverified.")
        if settings["day"] == "28":
            selection["caveat"] += " The Dec27 St Stephen propers are removed and Galatians 1:11–19 restored. The unverified prokeimenon is intentionally uncovered; minor daily hymn variants may still be missing."
        selection["unavailable_exact_sources"] = [{"url": f"{BASE}/{config['recording_date'].replace('-', '/')}/{code}/gr-en/index.html", "http_status": 404} for code in ["ma", "li"]]
        reference = combine_service_references([
            {"id": "matins", "title": "Matins (Orthros)", "parts": [ordinary, parts[0]]},
            {"id": "liturgy", "title": config["liturgy_title"], "parts": [parts[1]]}], recording_id=recording_id, selection=selection)
        path = DATA / f"reference-{recording_id}.json"
        path.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n")
        item = {"recording_id": recording_id, "file": path.name, "reference_id": reference["reference_id"], "units": len(reference["units"]), "sections": len(reference["sections"]), "selection": selection, "source_urls": [s["source_url"] for s in reference["sources"]]}
        manifest = [item if m["recording_id"] == recording_id else m for m in manifest]
        reports.append(item)
        print(f"{recording_id}: {reference['reference_id']} · {len(reference['units'])} units · Mode {settings['mode']}/Eothinon {settings['eothinon']}", flush=True)
    (DATA / "reference-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return reports


if __name__ == "__main__":
    build_december()
