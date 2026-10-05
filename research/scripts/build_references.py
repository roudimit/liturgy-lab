"""Acquire/cache official DCS editions and build per-recording combined references.

Run without --fetch to rebuild from data/reference-sources. No generated or
model-corrected liturgical text is used. The unavailable 2025 editions have
explicitly labeled 2026 substitutes; they must not be described as exact.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from liturgy_lab.reference import combine_service_references, parse_reference

DATA = ROOT / "data"
CACHE = DATA / "reference-sources"
BASE = "https://dcs.goarch.org/goa/dcs"
ORDINARY = f"{BASE}/h/b/matinsordinary/normal/gr-en/index.html"
DECEMBER_CALENDAR = "https://www.goarch.org/chapel/calendar?month=12&viewStyle=GridView&viewType=ViewReadings&year=2025"
CONFIGURATIONS = [
    {"id": "ZUMoL5VwJzw", "recording_date": "2026-08-09", "edition_date": "2026-08-09", "matins_code": "ma", "liturgy_title": "Divine Liturgy of St. John Chrysostom", "status": "exact_calendar_date", "calendar_url": "https://dcs.goarch.org/goa/dcs/dcs.html?date=2026-08-09", "caveat": "The August 9, 2026 date is inferred from release/upload metadata and the recording title 10th Sunday of Matthew. Dated GOA texts are used; local omissions, order, and spoken variants remain unverified."},
    {"id": "MIxJvLfaynY", "recording_date": "2025-09-08", "edition_date": "2026-09-08", "matins_code": "ma3", "liturgy_title": "Divine Liturgy of St. John Chrysostom", "status": "same_feast_substitute", "calendar_url": "https://www.goarch.org/chapel?date=9%2F8%2F2025", "caveat": "Exact 2025-09-08 DCS pages returned 404. This reference uses the 2026-09-08 Nativity of the Theotokos edition, including the full festal Matins canon. It is a same-feast substitute; local abbreviations and year-specific details remain unverified."},
    {"id": "vkkeLmltf_4", "recording_date": "2025-12-14", "edition_date": "2026-12-13", "matins_code": "ma", "liturgy_title": "Divine Liturgy of St. John Chrysostom", "status": "same_liturgical_sunday_substitute", "calendar_url": DECEMBER_CALENDAR, "caveat": "Exact 2025-12-14 DCS pages returned 404. This reference uses the 2026-12-13 Sunday of the Holy Forefathers edition. The GOARCH 2025 calendar confirms 11th Sunday of Luke / Forefathers, but the resurrectional mode, Matins Gospel, and daily commemorations can differ. This is a reusable substitute, not the exact 2025 service book."},
    {"id": "IuZ8WRk-POI", "recording_date": "2026-03-29", "edition_date": "2026-03-29", "matins_code": "ma", "liturgy_title": "Divine Liturgy of St. Basil", "status": "exact_calendar_date", "calendar_url": "https://dcs.goarch.org/goa/dcs/dcs.html?date=2026-03-29", "caveat": "The dated 2026-03-29 Matins and St. Basil Liturgy correspond to the recording title Sunday of St. Mary of Egypt. The service date is inferred from release/upload metadata and title; local omissions and spoken variants are not independently verified."},
    {"id": "n674zECLjTI", "recording_date": "2025-12-28", "edition_date": "2026-12-27", "matins_code": "ma", "liturgy_title": "Divine Liturgy of St. John Chrysostom", "status": "same_liturgical_sunday_substitute", "calendar_url": DECEMBER_CALENDAR, "caveat": "Exact 2025-12-28 DCS pages returned 404. This reference uses the 2026-12-27 Sunday after Nativity edition. The Sunday after Nativity core is reusable, but this edition also commemorates St. Stephen and has a different resurrectional mode and Matins Gospel. Those variable passages are not a verified match to the 2025 recording."},
]


def obtain(filename: str, url: str, fetch: bool) -> str:
    path = CACHE / filename
    if not path.is_file():
        if not fetch:
            raise FileNotFoundError(f"Missing {path}; run with --fetch to acquire the official source")
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=60) as response:
            html = response.read().decode("utf-8")
        if "biTable" not in html:
            raise ValueError(f"Source has no bilingual service table: {url}")
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    return path.read_text(encoding="utf-8")


def build_all(fetch: bool = False) -> list[dict]:
    ordinary = parse_reference(obtain("matins-ordinary.html", ORDINARY, fetch), ORDINARY, service_id="matins")
    manifest = []
    for config in CONFIGURATIONS:
        date = config["edition_date"]
        prefix = f"{BASE}/h/s/{date.replace('-', '/')}"
        matins_url, liturgy_url = f"{prefix}/{config['matins_code']}/gr-en/index.html", f"{prefix}/li/gr-en/index.html"
        matins = parse_reference(obtain(f"{date}-{config['matins_code']}.html", matins_url, fetch), matins_url, service_id="matins")
        liturgy = parse_reference(obtain(f"{date}-li.html", liturgy_url, fetch), liturgy_url, service_id="liturgy")
        selection = {k: config[k] for k in ["recording_date", "edition_date", "status", "calendar_url", "caveat"]}
        selection["recording_date_independently_verified"] = False
        if config["recording_date"] != date:
            old_prefix = f"{BASE}/h/s/{config['recording_date'].replace('-', '/')}"
            selection["unavailable_exact_sources"] = [{"url": f"{old_prefix}/{code}/gr-en/index.html", "http_status": 404} for code in ["ma", "li"]]
        reference = combine_service_references([
            {"id": "matins", "title": "Matins (Orthros)", "parts": [ordinary, matins]},
            {"id": "liturgy", "title": config["liturgy_title"], "parts": [liturgy]},
        ], recording_id=config["id"], selection=selection)
        path = DATA / f"reference-{config['id']}.json"
        path.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest.append({"recording_id": config["id"], "file": path.name, "reference_id": reference["reference_id"], "units": len(reference["units"]), "sections": len(reference["sections"]), "selection": selection, "source_urls": [source["source_url"] for source in reference["sources"]]})
        print(f"{config['id']}: {len(reference['units'])} units / {len(reference['sections'])} sections · {selection['status']} · {date}", flush=True)
    (DATA / "reference-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Download any missing official source pages")
    args = parser.parse_args()
    build_all(args.fetch)
