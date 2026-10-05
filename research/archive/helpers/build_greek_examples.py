"""Render exact, source-checked excerpts; CPU only."""
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
DATA = PROJECT / "data"
reference = json.loads((DATA / "reference-MIxJvLfaynY.json").read_text())
units = {unit["id"]: unit for unit in reference["units"]}
checked = []


def load(name):
    return json.loads((DATA / name).read_text())


def link(label, name):
    return f"[{label}]({DATA / name})"


def words(text, start, count):
    spans = list(re.finditer(r"\S+", text))
    return text[spans[start].start():spans[start + count - 1].end()]


def raw(name, segment_id, excerpt=None):
    segment = next(s for s in load(name)["segments"] if str(s["id"]) == str(segment_id))
    text = segment["text"] if excerpt is None else excerpt
    assert text in segment["text"], (name, segment_id, text)
    checked.append({"file": name, "segment_id": segment_id, "start": segment["start"], "end": segment["end"], "quote": text})
    return f"“{text}”"


def canonical(unit_id, start=None, count=None, suffix=False):
    text = units[unit_id]["greek"]
    if suffix:
        text = text[text.index("Ὅτι"):]
    quote = words(text, start, count) if start is not None else text
    assert quote in units[unit_id]["greek"]
    checked.append({"file": "reference-MIxJvLfaynY.json", "unit_id": unit_id, "quote": quote})
    return f"“{quote}” (`{unit_id}`)"


def video(label, seconds):
    beginning, ending = label.split("–")
    def offset(timestamp):
        hours, minutes, secs = map(int, timestamp.split(":"))
        assert 0 <= minutes < 60 and 0 <= secs < 60
        return hours * 3600 + minutes * 60 + secs
    assert offset(beginning) == seconds, (label, seconds)
    assert offset(ending) >= seconds, label
    return f"[{label}](https://www.youtube.com/watch?v=MIxJvLfaynY&t={seconds}s)"


def row(model, name, sid, quote=None):
    return f"| {link(model, name)} | {raw(name, sid, quote)} |"


parts = ["""# Greek recognition: eight illustrative examples

These are **text-only observations, not an independent audio transcription or a WER evaluation**. The examples were deliberately selected to show different behaviors; they are not representative statistics. A recognizable passage can still contain substantial word errors.

Small, Turbo and Large v3 below used the same recorded audio and fixed 30-second chunks with automatic language selection. The two marked retries forced Large v3 to Greek (`el`). Segment boundaries differ between models. Quoted excerpts are copied exactly, without spelling or accent corrections; repetitive outputs are shortened by selecting a contiguous excerpt. Linked JSON files contain the full text. Times are video offsets from saved ASR, not manually verified word timings.

Canonical passages come from the saved combined Matins/Liturgy reference, `ref-e5432ce2789f102a2c0b`. Its dated material uses a **2026-09-08 same-feast substitute**, not an exact verified edition for the recording. The reference is a comparison text, not ground truth for every spoken word.
"""]

parts += [f"**1. A spoken-prayer phrase becomes closer to the reference — {video('01:14:01–01:14:12', 4441)}**\n",
          "| Run | Exact ASR excerpt |\n|---|---|",
          row("Small", "asr-compare-small-4410.json", 2, "σύμματος κόσμου"),
          row("Turbo", "asr-compare-turbo-4410.json", 3, "σήμαντος κόσμα"),
          row("Large v3", "asr-compare-large-v3-4410.json", 5, "σύμπαντος κόσμου ευταθείας"),
          "\nReference: " + canonical("liturgy:u0007", 3, 4) + ".\n",
          "Large v3 recovers the two-word form matching the reference’s σύμπαντος κόσμου. Its following ευταθείας still lacks the σ in εὐσταθείας. This is a local improvement in textual resemblance, not proof that the complete sentence is correct.\n"]

parts += [f"**2. The larger model is not consistently closer — {video('01:14:16–01:14:27', 4456)}**\n",
          "| Run | Exact ASR excerpt |\n|---|---|",
          row("Small", "asr-compare-small-4410.json", 3, "μεταπίστευσε βλαβιάς"),
          row("Turbo", "asr-compare-turbo-4410.json", 4, "μεταπίστως ευλαβίας"),
          row("Large v3", "asr-compare-large-v3-4410.json", 7, "μεταπίστευσε βλαβείας"),
          "\nReference: " + canonical("liturgy:u0009", 7, 3) + ".\n",
          "Turbo retains more of the reference’s word sequence here. All three alter word forms or boundaries; simply removing polytonic accents would not resolve these differences.\n"]

parts += [f"**3. Greek-like speech represented in Latin characters — {video('00:32:30–00:33:00', 1950)}**\n",
          "| Run | Exact ASR excerpt |\n|---|---|",
          row("Small", "asr-compare-small-1950.json", 0),
          row("Turbo", "asr-compare-turbo-1950.json", 0),
          row("Large v3, automatic", "asr-compare-large-v3-1950.json", 0),
          row("Large v3, forced Greek", "large-v3-greek-retry-1950.json", 0),
          "\nReference: " + canonical("matins:u0166") + ".\n",
          "Automatic Large v3 labeled this chunk `la` and emitted Latin characters. Forcing `el` restores Greek script, but Κούντες Ιωάννες, κίνθητε still differs substantially from Οἱ μισοῦντες Σιών, αἰσχύνθητε. Both Turbo and the forced retry also emit “Υπότιτλοι AUTHORWAVE” in this chunk. Script selection alone does not fix the words.\n"]

parts += [f"**4. Repetition in the entrance/chant region — {video('01:21:30–01:22:00', 4890)}**\n",
          "| Run | Exact ASR excerpt |\n|---|---|",
          row("Small", "asr-compare-small-4860.json", 6, "Παραπεζητάζω εγώ ξατεμίκης ουρσκός,"),
          row("Turbo", "asr-compare-turbo-4860.json", 9, "Χαραπησήπασαι δόξα τέμει και παρσοπής,"),
          row("Large v3", "asr-compare-large-v3-4860.json", 5, "Ευχαριστώ, Ιησού, για την ευκαιρία του Θεού και για την ευκαιρία του Θεού"),
          "\nA plausible comparison formula in the Small Entrance prayer: " + canonical("liturgy:u0082", 0, 8, suffix=True) + ".\n",
          "Turbo preserves fragments resembling δόξα, τιμὴ καὶ προσκύνησις; Large v3 produces a long repeated phrase instead. This common formula cannot establish a unique location, and the proposed reference association here remains unverified. A larger model has not eliminated repetition failure.\n"]

parts += [f"**5. A selected forced-Greek retry recovers more useful entrance text — {video('01:22:00–01:22:30', 4920)}**\n",
          "| Run | Exact ASR excerpt(s) |\n|---|---|",
          row("Small", "asr-compare-small-4860.json", 8),
          row("Turbo", "asr-compare-turbo-4860.json", 11),
          row("Large v3, automatic", "asr-compare-large-v3-4860.json", 6),
          f"| {link('Large v3, forced Greek', 'large-v3-greek-retry-4920.json')} | {raw('large-v3-greek-retry-4920.json', 0)}; {raw('large-v3-greek-retry-4920.json', 1)}; {raw('large-v3-greek-retry-4920.json', 2)} |",
          "\nReference: " + canonical("liturgy:u0085") + "; " + canonical("liturgy:u0086", 0, 5) + ".\n",
          "The automatic Large v3 chunk was labeled `en` and returned only Alleluia. The forced retry yields several recognizable Greek phrases, while Σου φία ορθή retains boundary/form errors. This is one targeted retry, not evidence that forcing Greek is appropriate throughout a bilingual service.\n"]

parts += [f"**6. Latin-script output and possible language drift — {video('01:24:17–01:24:23', 5057)}**\n",
          "| Run | Exact ASR excerpt |\n|---|---|",
          row("Small, broader 5040–5070 chunk", "asr-compare-small-5040.json", 0, "ούτε η αγγεία, ούτε η αγγεία,"),
          row("Turbo", "asr-compare-turbo-5040.json", 3),
          row("Large v3", "asr-compare-large-v3-5040.json", 3),
          "\nReference: " + canonical("liturgy:u0091") + "; its supplied English is “" + units["liturgy:u0091"]["english"] + "”\n",
          "Turbo’s Latin characters approximate the Greek phrase, whereas Large v3 supplies different English wording. This warrants checking language handling and the audio; these outputs alone do not establish whether the speaker switched language or the recognizer drifted.\n"]

parts += [f"**7. A familiar chant still has missing or damaged words — {video('01:24:40–01:25:00', 5080)}**\n",
          "| Run | Exact ASR excerpt / emitted coverage |\n|---|---|",
          row("Small", "asr-compare-small-5040.json", 3),
          f"| {link('Turbo', 'asr-compare-turbo-5040.json')} | No segment overlaps 5080–5100 s in this run. |",
          row("Large v3", "asr-compare-large-v3-5040.json", 11),
          "\nReference: " + canonical("liturgy:u0098") + ".\n",
          "The plausible Trisagion reference contains ἅγιος Ἰσχυρός; neither quoted output reproduces that phrase. Turbo’s absent output is a timestamp-coverage observation, not a measured deletion error against a human transcript.\n"]

parts += [f"**8. Plausible passage localization despite damaged Greek — {video('01:00:00–01:00:12', 3600)}**\n",
          "This separate localization example uses the full-recording Turbo input retained in the 35B experiment, not the controlled short-clip transcript.\n",
          "| Source | Exact text |\n|---|---|",
          row("Full-recording Turbo, segment 455", "qwen35b-combined-MIxJvLfaynY.json", 455),
          "\nReference: " + canonical("matins:u0394", 4, 13) + ".\n",
          "The saved 35B run associates this with matins:u0394, “Stichera for the Feast,” but retains **uncertain** status because the reference repeats the hymn. The distinctive wording gives a plausible location while τυραστικτέται and σκαρπογόνην remain corrupted. This experiment used **sequence v1 hints**; it does not evaluate the current tracker and is not an independently verified alignment.\n"]

# Check claims about omitted output and supplemental artifact text as well.
assert not [s for s in load("asr-compare-turbo-5040.json")["segments"] if s["start"] < 5100 and s["end"] > 5080]
for name in ["asr-compare-turbo-1950.json", "large-v3-greek-retry-1950.json"]:
    assert any(s["text"] == "Υπότιτλοι AUTHORWAVE" for s in load(name)["segments"])
loc = next(s for s in load("qwen35b-combined-MIxJvLfaynY.json")["segments"] if s["id"] == 455)
assert loc["llm_match"]["unit_id"] == "matins:u0394" and loc["llm_match"]["status"] == "uncertain"
retry_audit = load("greek-retry-audit.json")
assert retry_audit["cases"][0]["auto_comparators"]["large-v3"]["detected_language"] == "la"
assert retry_audit["cases"][1]["auto_comparators"]["large-v3"]["detected_language"] == "en"

parts += ["Source editions: [GOARCH Digital Chant Stand Matins](https://dcs.goarch.org/goa/dcs/h/s/2026/09/08/ma3/gr-en/index.html) and [Divine Liturgy](https://dcs.goarch.org/goa/dcs/h/s/2026/09/08/li/gr-en/index.html). Canonical wording and the one English rendering above are copied from the saved reference; no new translations were produced. All model excerpts were checked as exact substrings of their linked saved segments.\n"]
output = "\n".join(parts)
(PROJECT / "GREEK-EXAMPLES.md").write_text(output)
(Path(__file__).parent / "greek-examples-quote-audit.json").write_text(json.dumps(checked, ensure_ascii=False, indent=2))
print(f"Wrote {PROJECT / 'GREEK-EXAMPLES.md'}; verified {len(checked)} raw/reference excerpts; {len(output.split())} whitespace-separated words")
