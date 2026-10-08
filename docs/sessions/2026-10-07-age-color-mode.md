# Session 2026-10-07: satellite Age colour mode (portfolio-site)

Future feature 2 from the 2026-10-06 brainstorm list in `docs/todo.md`. It builds on the
pipeline change from 2026-10-06, which added `international_designator` to `objects/current.json`.

- **Code:** in `portfolio-site`, on branch `feat/age-color-mode`. The first commit is pushed (not
  yet merged); the two after it are local:
  - `1139801` feat: add an Age color mode from the launch designator
  - `7ece7c9` fix: color Age buckets with the shared category colors
  - `31e58e8` fix: draw orbit lines for pair and station views too (see "Orbit lines for list
    selections" below)
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
- **Colours: the shared category colours.** The three buckets use the first three colours of the
  set Type and Owner already share, in order, and Unknown uses the shared grey. Age adds no colours
  of its own.

  | Bucket | Colour | On the sky `#05070d` | On the Sky ground `#26303c` |
  |---|---|---|---|
  | Under 2 years | `#3987e5` (series 1, blue) | 5.53:1 | 3.67:1 |
  | 2 to 10 years | `#d95926` (series 2, orange) | 5.19:1 | 3.44:1 |
  | Over 10 years | `#199e70` (series 3, green) | 5.91:1 | 3.93:1 |
  | Unknown | `#8b8f98` (shared grey) | 6.22:1 | 4.13:1 |

### How the colours got here

1. **One-hue teal ramp** (`#258e6a`, `#58ba93`, `#9de3c4`): stepped in lightness only, and the
   three buckets looked too alike.
2. **Multi-hue ordered ramp** (`#5f75c1`, `#05c992`, `#d4f73e`, warm grey `#8f8978`): clearly
   distinct and validated, but Max found it looked off next to the other modes in use.
3. **Now: the shared category colours.** The ordered ramp was dropped by choice. Age reads like the
   other modes, and its order comes from the legend's labels rather than from the colours.

### Separation (validator model, OKLab x100: Machado 2009 simulation)

| Pair | Normal | Protan | Deutan | Tritan |
|---|---|---|---|---|
| Under 2 vs 2 to 10 | 31.8 | 26.8 | 28.6 | 32.4 |
| 2 to 10 vs over 10 | 26.5 | 12.6 | 9.4 | 32.4 |
| Under 2 vs over 10 | 20.9 | 19.7 | 19.6 | **4.0** |
| Over 10 vs Unknown | **13.5** | **6.6** | **5.1** | 10.3 |
| Under 2 vs Unknown | 15.0 | 13.3 | 15.9 | 10.0 |
| 2 to 10 vs Unknown | 18.5 | 15.9 | 13.7 | 22.6 |
| Buckets vs orbit line `#b0a8ff` (min) | 17.3 | 12.3 | 16.6 | 15.2 |
| Unknown vs orbit line | 16.4 | 15.8 | 15.3 | 12.1 |

- **The three buckets on their own pass every validator check** on both surfaces: colour-blind
  separation (worst 9.4, deutan), the normal-vision floor (worst 20.9) and contrast.
- **They're well clear of the orbit line.**
- **Weak spots.** All three are already in Type mode, which uses the same four colours.
  1. **Over 10 (green) vs Unknown (grey):** below the normal-vision floor of 15, and under the
     colour-blind target of 8 for protan and deutan. With Unknown included the validator fails
     there. In practice the two rarely share the screen: today's snapshot has no Unknowns, and older
     snapshots are entirely Unknown. **Smallest fix (not applied):** a lighter shared grey around
     `#a3a5a7` clears the green (16.2 normal, 8.5 protan/deutan), but it comes within 5.8 of the
     orbit line. So it isn't a free change: it means choosing between the grey/green pair and the
     grey/orbit pair, and it would change Type and Owner too.
  2. **Under 2 (blue) vs over 10 (green) under tritan:** 4.0. The validator reports tritan but
     doesn't gate on it (tritanopia is very rare). Fixing it would mean changing the shared green
     for every mode. Not applied.
  3. **2 to 10 (orange) vs the selection ring `#e85d3f`:** about 3.5 under every vision type. The
     ring is drawn around the point, not as a point, so shape still tells them apart. Debris has
     this already.

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
- **Errors:** none on the page.
- **Checks:**
  - `npm run lint`, `npx tsc -b` and `npm run build` are clean. The build's only warning is Vite's
    existing chunk-size note.
  - `npm test` passes 59/59, including 8 Age tests: valid, malformed, missing, null, non-string
    and whitespace designators; the bucket edges at 2 and 10 years (and 11) plus future years; a
    snapshot without the key (all Unknown, the right note, Unknown still filterable); the four rows
    always listed; no note when nothing is Unknown; and Age reusing Type mode's colours in order.
- **Evals:** none run. No pipeline code changed.

## Orbit lines for list selections (`31e58e8`)

**Reported:** selecting from the conjunctions list or the Stations list (ISS, Tiangong) drew no
orbit line; clicking a point did.

**Reproduced at localhost:5173:**

| Path | What it opens | Inspected object | Orbit before the fix |
|---|---|---|---|
| Click a point | inspect | the object | drawn |
| Conjunctions list, "Show on globe" | near-miss pair view | none | none |
| Stations list, ISS or Tiangong | station view | none | none |

**Root cause: by design, not a hidden bug.** The orbit line followed only the inspected object, and
the pair and station views deliberately clear it under the one-selection model. That is the
"pair and station views remove the orbit line" behaviour recorded on 2026-10-06.

I looked for a second path to the same object:
- clicking one of the pair's objects while the pair view shows inspects it and draws its orbit;
- clicking a docked ISS module in the station view selects the ISS and draws its orbit.

So there was no further bug. (One early test click missed only because the camera was still
flying in.)

**Change:**
- **One rule picks what gets a line** (`orbitTargets` in `src/globe/orbit.ts`):
  - the inspected object, without its neighbour;
  - both objects of a near-miss pair;
  - a station's first piece, which is the station itself (its other pieces are docked and share the
    orbit).
- **The engine keeps up to two orbit slots.** Each has a globe line and a Sky line, is sampled
  around the displayed moment (the closest approach for a pair, which the replay jumps to), and is
  resampled when the clock moves more than half its own period away.
- **A pair's two loops are drawn alike:** same colour, same 2 px width. The pair is symmetric, so
  a thinner line would imply a ranking that isn't there. Each loop is told apart by the ring its
  object sits in (white or gold), and the two loops cross at the closest-approach point.
- **The pair and station panels gain the orbit key** ("Both orbits, one full period each", "Its
  orbit, one full period").
- **Rules unchanged:**
  - dimming never touches the lines, and they're never frustum-culled;
  - they aren't in the pick buffers. Rechecked: a click on a line 59 px from any object cleared the
    selection like an empty click;
  - one selection at a time.

**Verified** (desktop 1440 px and phone 390 px). The distance from each object to its own line was
measured on screen:
- **Click-picked object:** one loop, 0 px. Only it and its neighbour stay bright.
- **Conjunction from the list:** two loops, both centred exactly on the closest-approach moment and
  both 0 px from their objects. Only the pair stays bright. Moving the clock 52 minutes (over half
  of their 94-minute period) resampled both loops, still 0 px.
- **ISS from the Stations list:** one loop through the station, 0 px.
- **Transitions:**
  - object to pair: 1 loop becomes 2;
  - pair to station: 2 become the station's 1;
  - station to object: the object's loop;
  - Deselect from an object, and Back to full view from a pair or a station: no lines.
- **Globe/Sky toggle:**
  - An inspected object keeps its loop both ways, drawn on the dome in Sky (0 px).
  - Pair and station views end on entering Sky (the Sky 1b decision), so their lines go too.
  - The Stations list isn't shown in Sky.
  - "Show on globe" from Sky returns to Globe with both pair loops.
- **Phone:** all three paths draw their loops; the picked object's loop is also drawn in Sky.
- **Errors:** none on the page.
- **Tests:** 3 new, in `tests/orbit.test.ts`:
  - which objects get lines for an object, a pair and a station;
  - a pair's loops sampled around the closest approach pass through both objects;
  - each loop refreshes on its own period.

## Flag for review

- **Time slider arrow keys don't work while the clock runs.** Found while testing, and it predates
  this branch. The slider's value is the live, unrounded time with a 1-minute step, so Chromium
  snaps each arrow press back to the current minute and the thumb never moves; Home/End did nothing
  on macOS. Mouse and touch work. Not fixed here; it's in `docs/todo.md` under Lower priority.
- **Green vs grey in Age (and Type).** They're weak for deutan/protan viewers. The smallest fix
  trades against the orbit line (see Separation above), so it's left as a choice.
- **Year-only precision.** Objects launched in the boundary years (2024 and 2016, against a 2026
  snapshot) can be one bucket off, which the legend notes. Exact launch dates would need the GCAT
  join.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..feat/age-color-mode && npm run dev
# both branches already have upstreams: git push (portfolio-site), then in this repo: git push
```
