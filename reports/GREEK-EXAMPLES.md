# Greek recognition: eight illustrative examples

These are **text-only observations, not an independent audio transcription or a WER evaluation**. The examples were deliberately selected to show different behaviors; they are not representative statistics. A recognizable passage can still contain substantial word errors.

Small, Turbo and Large v3 below used the same recorded audio and fixed 30-second chunks with automatic language selection. The two marked retries forced Large v3 to Greek (`el`). Segment boundaries differ between models. Quoted excerpts are copied exactly, without spelling or accent corrections; repetitive outputs are shortened by selecting a contiguous excerpt. Linked JSON files contain the full text. Times are video offsets from saved ASR, not manually verified word timings.

Canonical passages come from the saved combined Matins/Liturgy reference, `ref-e5432ce2789f102a2c0b`. Its dated material uses a **2026-09-08 same-feast substitute**, not an exact verified edition for the recording. The reference is a comparison text, not ground truth for every spoken word.

**1. A spoken-prayer phrase becomes closer to the reference — [01:14:01–01:14:12](https://www.youtube.com/watch?v=MIxJvLfaynY&t=4441s)**

| Run | Exact ASR excerpt |
|---|---|
| [Small](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-small-4410.json) | “σύμματος κόσμου” |
| [Turbo](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-turbo-4410.json) | “σήμαντος κόσμα” |
| [Large v3](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-large-v3-4410.json) | “σύμπαντος κόσμου ευταθείας” |

Reference: “τοῦ σύμπαντος κόσμου, εὐσταθείας” (`liturgy:u0007`).

Large v3 recovers the two-word form matching the reference’s σύμπαντος κόσμου. Its following ευταθείας still lacks the σ in εὐσταθείας. This is a local improvement in textual resemblance, not proof that the complete sentence is correct.

**2. The larger model is not consistently closer — [01:14:16–01:14:27](https://www.youtube.com/watch?v=MIxJvLfaynY&t=4456s)**

| Run | Exact ASR excerpt |
|---|---|
| [Small](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-small-4410.json) | “μεταπίστευσε βλαβιάς” |
| [Turbo](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-turbo-4410.json) | “μεταπίστως ευλαβίας” |
| [Large v3](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-large-v3-4410.json) | “μεταπίστευσε βλαβείας” |

Reference: “μετὰ πίστεως, εὐλαβείας” (`liturgy:u0009`).

Turbo retains more of the reference’s word sequence here. All three alter word forms or boundaries; simply removing polytonic accents would not resolve these differences.

**3. Greek-like speech represented in Latin characters — [00:32:30–00:33:00](https://www.youtube.com/watch?v=MIxJvLfaynY&t=1950s)**

| Run | Exact ASR excerpt |
|---|---|
| [Small](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-small-1950.json) | “Του νδεσίον εσχύθητε από του Κυρίου,” |
| [Turbo](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-turbo-1950.json) | “Κούντες Ιόνες κύνθητε από του Κυρίου” |
| [Large v3, automatic](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-large-v3-1950.json) | “Suntes ion eschinti te apoi tu,” |
| [Large v3, forced Greek](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/large-v3-greek-retry-1950.json) | “Κούντες Ιωάννες, κίνθητε από του Κυρίου ως χόρτος γαρπήρι.” |

Reference: “Οἱ μισοῦντες Σιών, αἰσχύνθητε ἀπὸ τοῦ Κυρίου· ὡς χόρτος γάρ, πυρὶ ἔσεσθε ἀπεξηραμμένοι.” (`matins:u0166`).

Automatic Large v3 labeled this chunk `la` and emitted Latin characters. Forcing `el` restores Greek script, but Κούντες Ιωάννες, κίνθητε still differs substantially from Οἱ μισοῦντες Σιών, αἰσχύνθητε. Both Turbo and the forced retry also emit “Υπότιτλοι AUTHORWAVE” in this chunk. Script selection alone does not fix the words.

**4. Repetition in the entrance/chant region — [01:21:30–01:22:00](https://www.youtube.com/watch?v=MIxJvLfaynY&t=4890s)**

| Run | Exact ASR excerpt |
|---|---|
| [Small](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-small-4860.json) | “Παραπεζητάζω εγώ ξατεμίκης ουρσκός,” |
| [Turbo](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-turbo-4860.json) | “Χαραπησήπασαι δόξα τέμει και παρσοπής,” |
| [Large v3](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-large-v3-4860.json) | “Ευχαριστώ, Ιησού, για την ευκαιρία του Θεού και για την ευκαιρία του Θεού” |

A plausible comparison formula in the Small Entrance prayer: “Ὅτι πρέπει σοι πᾶσα δόξα, τιμὴ καὶ προσκύνησις,” (`liturgy:u0082`).

Turbo preserves fragments resembling δόξα, τιμὴ καὶ προσκύνησις; Large v3 produces a long repeated phrase instead. This common formula cannot establish a unique location, and the proposed reference association here remains unverified. A larger model has not eliminated repetition failure.

**5. A selected forced-Greek retry recovers more useful entrance text — [01:22:00–01:22:30](https://www.youtube.com/watch?v=MIxJvLfaynY&t=4920s)**

| Run | Exact ASR excerpt(s) |
|---|---|
| [Small](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-small-4860.json) | “σ' φυαρθεί, δεύτεμ προσκυνήσομεν, και προσπασομέν Χριστό,” |
| [Turbo](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-turbo-4860.json) | “Αλλα, αλλα, αλλα.” |
| [Large v3, automatic](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-large-v3-4860.json) | “Alleluia.” |
| [Large v3, forced Greek](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/large-v3-greek-retry-4920.json) | “Σου φία ορθή”; “Δεύτε προσκυνήσωμεν”; “Και προσπέσωμεν Χριστό” |

Reference: “Σοφία. Ὀρθοί.” (`liturgy:u0085`); “Δεῦτε προσκυνήσωμεν καὶ προσπέσωμεν Χριστῷ.” (`liturgy:u0086`).

The automatic Large v3 chunk was labeled `en` and returned only Alleluia. The forced retry yields several recognizable Greek phrases, while Σου φία ορθή retains boundary/form errors. This is one targeted retry, not evidence that forcing Greek is appropriate throughout a bilingual service.

**6. Latin-script output and possible language drift — [01:24:17–01:24:23](https://www.youtube.com/watch?v=MIxJvLfaynY&t=5057s)**

| Run | Exact ASR excerpt |
|---|---|
| [Small, broader 5040–5070 chunk](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-small-5040.json) | “ούτε η αγγεία, ούτε η αγγεία,” |
| [Turbo](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-turbo-5040.json) | “To Kyrieu Dei Thomen.” |
| [Large v3](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-large-v3-5040.json) | “To the Lord we give thanks” |

Reference: “Τοῦ Κυρίου δεηθῶμεν.” (`liturgy:u0091`); its supplied English is “Let us pray to the Lord.”

Turbo’s Latin characters approximate the Greek phrase, whereas Large v3 supplies different English wording. This warrants checking language handling and the audio; these outputs alone do not establish whether the speaker switched language or the recognizer drifted.

**7. A familiar chant still has missing or damaged words — [01:24:40–01:25:00](https://www.youtube.com/watch?v=MIxJvLfaynY&t=5080s)**

| Run | Exact ASR excerpt / emitted coverage |
|---|---|
| [Small](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-small-5040.json) | “Παγίος ο Θεός,” |
| [Turbo](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-turbo-5040.json) | No segment overlaps 5080–5100 s in this run. |
| [Large v3](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/asr-compare-large-v3-5040.json) | “Άγιος η Σύνος,” |

Reference: “Ἅγιος ὁ Θεός, ἅγιος Ἰσχυρός, ἅγιος Ἀθάνατος, ἐλέησον ἡμᾶς.” (`liturgy:u0098`).

The plausible Trisagion reference contains ἅγιος Ἰσχυρός; neither quoted output reproduces that phrase. Turbo’s absent output is a timestamp-coverage observation, not a measured deletion error against a human transcript.

**8. Plausible passage localization despite damaged Greek — [01:00:00–01:00:12](https://www.youtube.com/watch?v=MIxJvLfaynY&t=3600s)**

This separate localization example uses the full-recording Turbo input retained in the 35B experiment, not the controlled short-clip transcript.

| Source | Exact text |
|---|---|
| [Full-recording Turbo, segment 455](/Users/andrewrouditchenko/Documents/Codex/2026-09-30/can-x20/outputs/liturgy-lab/data/qwen35b-combined-MIxJvLfaynY.json) | “η πηγή της ζωής εκ της τυραστικτέται, η χάρη σκαρπογόνην λαμπρός απαρχεται.” |

Reference: “ἡ πηγὴ τῆς ζωῆς, ἐκ τῆς στείρας τίκτεται· ἡ χάρις καρπογονεῖν, λαμπρῶς ἀπάρχεται.” (`matins:u0394`).

The saved 35B run associates this with matins:u0394, “Stichera for the Feast,” but retains **uncertain** status because the reference repeats the hymn. The distinctive wording gives a plausible location while τυραστικτέται and σκαρπογόνην remain corrupted. This experiment used **sequence v1 hints**; it does not evaluate the current tracker and is not an independently verified alignment.

Source editions: [GOARCH Digital Chant Stand Matins](https://dcs.goarch.org/goa/dcs/h/s/2026/09/08/ma3/gr-en/index.html) and [Divine Liturgy](https://dcs.goarch.org/goa/dcs/h/s/2026/09/08/li/gr-en/index.html). Canonical wording and the one English rendering above are copied from the saved reference; no new translations were produced. All model excerpts were checked as exact substrings of their linked saved segments.
