# Session 2026-10-07: satellite Age colour mode (portfolio-site)

Future feature 2 from the 2026-10-06 brainstorm list in `docs/todo.md`. It builds on the
pipeline change from 2026-10-06, which added `international_designator` to `objects/current.json`.

- **Code:** in `portfolio-site`, on branch `feat/age-color-mode`. One commit, local only and not
  pushed:
  - `1139801` feat: add an Age color mode from the launch designator (amended before push with
    the revised palette)
- **Not in this commit:** the launch-year range filter, now a follow-up in `docs/todo.md` under
  the Age item. No pipeline code changed.

## What changed and why

- **An "Age" colour mode** next to Type, Owner and Flat, with four buckets: under 2 years, 2 to 10
  years, over 10 years, and Unknown. It uses the same legend checkboxes, filters and dimming as
  the other modes, in Globe and Sky.
- **Launch year: strict parsing** (`launchYear` in `src/globe/colors.ts`).
  - **Accepted:** exactly `YYYY-NNNA`, that is four digits, a dash, three digits and 1-3 capital
    letters, with a year from 1957 (the first launch) and a launch number from 001.
  - **Unknown:** anything else, never an error. That includes a missing key (every snapshot
    written before the field existed), null, the TLE's two-digit form, padding or whitespace, and
    lower case.
  - **Why strict:** guessing at malformed values would make the colour lie. The pipeline never
    pads, so strictness costs nothing today.
- **Reference date: the snapshot's run date** (`generated_at_utc` of the loaded objects file),
  not the playing clock or today.
  - It's the date the snapshot describes, so colours don't change while time plays.
  - Each retained day on the slider is measured against its own date.
  - Age is whole calendar years, `snapshotYear - launchYear`. An object launched in December and
    seen in January of the year after next counts as 2 years old after 13 months, so near the
    edges an object can land one bucket off. The code comment says so, and so does a short legend
    line (desktop only; counts and notes are trimmed on phones, as in the other modes).
- **Bucket edges:** under 2 is 0-1 years, "2 to 10" is 2-10 inclusive, and over 10 is 11 or more.
  A launch year after the snapshot's year is Unknown.
- **Legend:**
  - **All four buckets with counts:** the other modes show counts. The other modes also hide empty
    categories, but Age always lists all four, so an older snapshot reads "0 / 0 / 0 / Unknown
    19,246" instead of silently losing rows.
  - **The Unknown note** appears only while Unknown objects exist. It reads "Older snapshots lack
    launch data." when the file has no designator field at all, otherwise "Unknown: no valid launch
    designator."
- **Colours: an ordered multi-hue ramp** (viridis-style: hue and lightness both change at each
  step), blue -> green -> yellow-lime from newest to oldest, plus a warm grey for Unknown.

  | Bucket | Colour | On the sky `#05070d` | On the Sky ground `#26303c` |
  |---|---|---|---|
  | Under 2 years | `#5f75c1` | 4.60:1 | 3.06:1 |
  | 2 to 10 years | `#05c992` | 9.38:1 | 6.23:1 |
  | Over 10 years | `#d4f73e` | 16.47:1 | 10.94:1 |
  | Unknown | `#8f8978` | 5.77:1 | 3.83:1 |

### Why the palette changed before push

The first version used a one-hue teal ramp (`#258e6a`, `#58ba93`, `#9de3c4`) with a darker grey
for Unknown (`#5c6370`). It stepped in lightness only, and in review the three buckets were too
alike at a glance on the globe and in Sky. It was replaced before anything was pushed.

### How it was chosen

- **Search:** a small search over viridis-style triples in OKLCH. Every candidate had to meet:
  - 3:1 on both surfaces;
  - at least 15 between buckets under normal vision and under every simulation;
  - at least 10 from the orbit line;
  - at least 8 (the validator's colour-blind target) from each ring and line colour.
- **Scoring:** the winner had the largest worst-case separation between buckets.
- **Model:** the dataviz validator's, OKLab distance x100 with Machado 2009 protan, deutan and
  tritan simulation. The "before" figures are recomputed with the same model; the first session's
  quick check used a different simulation.

### Minimum colour distance, before and after

(OKLab x100; higher is more separable.)

| Pair | Version | Normal | Protan | Deutan | Tritan |
|---|---|---|---|---|---|
| Between the 3 buckets (min) | before | 14.0 | 13.5 | 14.0 | 13.5 |
| | after | **22.9** | **19.1** | **23.0** | **19.2** |
| Buckets vs Unknown | before | 14.0 | 12.5 | 9.3 | 12.1 |
| | after | **15.4** | **14.6** | **10.8** | **11.2** |
| Buckets vs orbit line | before | 20.2 | 15.8 | 14.5 | 10.5 |
| | after | 19.5 | 17.4 | 14.9 | 11.2 |
| Unknown vs orbit line | before | 29.2 | 28.6 | 28.2 | 27.1 |
| | after | 20.4 | 20.3 | 19.3 | 14.5 |
| Closest ring/line colour, all four age colours | before | 10.0 | 6.0 | 10.2 | 5.6 |
| | after | 14.5 | 8.2 | 8.5 | 8.2 |

- **Biggest gains:** between the buckets, up 9 to 9.6 in every column. Contrast is now at least
  3:1 for all four colours on the ground, where the first grey was 2.21:1. The closest overlay
  rises from 5.6 to 8.2; before, the cyan station ring under tritan and the selection ring under
  protan were the near misses.
- **Small losses:** Unknown vs the orbit line drops from 27-29 to 14.5-20.4, still well clear.
  Buckets vs the orbit line is about level (worst 11.2, tritan): no candidate in the search got
  past about 11 there without breaking another floor. In practice the line only appears with a
  selection, which dims every other dot to 0.2, and the screenshots show it standing well apart.
- **Validator, run as categorical with all pairs, on both surfaces:**
  - Pass: colour-blind separation (worst 10.8), the normal-vision floor (worst 15.4) and contrast.
  - Fail, by design: the lightness band (an ordered ramp spans lightness on purpose; the guide
    says sequential ramps fail that check) and the chroma floor (it flags Unknown for being grey,
    which is intended).
- **Rendering:** the dots render a little paler than their legend swatches, because the point
  sprite has a light rim. That's the same in every colour mode.

## Verification

All in `portfolio-site`, headed Chromium on the M5, at `localhost:5173` against the production
bucket.

- **Bucket counts.** Expected counts were computed independently in Node from the published files.
  The legend and the drawn point colours matched exactly:

  | Snapshot | Under 2 | 2 to 10 | Over 10 | Unknown | Total |
  |---|---|---|---|---|---|
  | Today, 2026-10-07 (latest run) | 7,530 | 8,332 | 3,452 | 0 | 19,314 |
  | Oldest retained, 2026-10-03 (slider at its left end) | 0 | 0 | 0 | 19,246 | 19,246 |

  - **Today:** the legend shows "Unknown 0" and no Unknown note; the precision line shows on
    desktop.
  - **Oldest snapshot:** every point draws in the Unknown grey (`#8f8978`), the note reads "Older snapshots
    lack launch data.", and the conjunction table's heading reads "Top conjunctions · 2026-10-03
    snapshot".
  - **Back to Live:** today's counts return and the note goes.
  - **All dated files:** the designator is on all 19,314 objects today (ISS `1998-067A`, every one
    in `YYYY-NNNA` form). It's on none of the objects in the 10-03 to 10-06 files.
- **Works with what exists:**
  - **Filters:** unchecking "Over 10 years" hid exactly 3,452 points (filter bar: "Showing 15,862
    of 19,314").
  - **Clock:** the drawn colours were identical after 2.5 s at 50x.
  - **Selection:** the ISS (launched 1998) is "Over 10 years". It and its live neighbour stayed at
    full alpha while everything else dimmed to 0.2, and the orbit line drew. The same held on the
    oldest snapshot, where the ISS is Unknown.
  - **Pair and station views:** the near-miss pair view dimmed all but the pair. The station view
    showed its rings with no dimming, as before. The legend stayed in Age mode throughout.
  - **Sky:** the dome's point colours matched the globe's for all 19,314 objects. The Age legend
    and counts are the same in Sky.
- **Phone (390 px):**
  - The four mode buttons fit the legend.
  - In Sky, the folded "Colours and filters" legend opens to the four buckets.
  - On the oldest snapshot only the Unknown note shows; the precision line is hidden, like the
    counts.
  - Screenshots: Globe and Sky, today and oldest.
- **Revised palette, seen on screen** (desktop Globe and Sky, phone Globe and Sky, legend visible):
  - **All buckets on:** blue, aqua-green and yellow-lime are distinct at a glance in the globe's
    shell and in the dome.
  - **Each bucket alone** (the other three unchecked): on the globe, exactly 7,530 blue, 8,332
    aqua-green or 3,452 yellow-lime points, each reading as one clean colour. The same held in Sky
    and on the phone.
  - **Oldest snapshot:** an all-warm-grey globe.
  - **With MTG-S1 selected:** the periwinkle orbit line stands apart from the dimmed dots.
- **Errors:** none on the page.
- **Checks:**
  - `npm run lint`, `npx tsc -b` and `npm run build` are clean. The build's only warning is Vite's
    existing chunk-size note.
  - `npm test` passes 56/56, including 8 new Age tests: valid, malformed, missing, null, non-string
    and whitespace designators; the bucket edges at 2 and 10 years (and 11) plus future years; a
    snapshot without the key (all Unknown, the right note, Unknown still filterable); the four rows
    always listed; no note when nothing is Unknown; and the ramp's order (newest darkest, luminance
    rising step by step).
- **Evals:** none run. No pipeline code changed.

## Flag for review

- **Time slider arrow keys don't work while the clock runs.** Found while testing, and it predates
  this branch. The slider's value is the live, unrounded time with a 1-minute step, so Chromium
  snaps each arrow press back to the current minute and the thumb never moves; Home/End did nothing
  on macOS. Mouse and touch work. Not fixed here; it's in `docs/todo.md` under Lower priority.
- **Year-only precision.** Objects launched in the boundary years (2024 and 2016, against a 2026
  snapshot) can be one bucket off, which the legend notes. Exact launch dates would need the GCAT
  join.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..feat/age-color-mode && npm run dev
# after review (Max): git push -u origin feat/age-color-mode && gh pr create --fill
# docs: cd ../satellite-conjunction-screening && git push -u origin docs/age-color-mode && gh pr create --fill
```
