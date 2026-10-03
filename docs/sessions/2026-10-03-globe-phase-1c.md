# Session 2026-10-03: globe Phase 1c (portfolio-site)

Implements the 2026-10-03 "Globe Phase 1c" working-notes entry.

- **Code:** in `portfolio-site`, on branch `feat/satellite-globe-phase-1c`, cut from `main` after
  Phase 1b merged. Three commits, local only and not pushed.
- **This repo:** this docs branch only.

## What changed and why

- **Keyword filters:** a collapsible "Filter by name" section in the legend panel. Each group has
  a checkbox and an "only" shortcut, plus "Show all".
  - **Combining:** the filters work alongside Phase 1b's colour-category toggles, so a point
    shows only if neither hides it. They use the same alpha mechanism, so there's no
    re-propagation.
  - **Rules:** deterministic name prefixes, with the specific debris groups matched before their
    broader prefixes.
  - **Groups and cutoff:** Starlink, OneWeb, Kuiper, Qianfan, Hulianwang, Yaogan, NAVSTAR (GPS),
    Iridium 33 debris, Iridium (active), Cosmos 2251 debris, Fengyun-1C debris, then "Everything
    else". That's every constellation in the entry's verified list of roughly 150+ objects, plus
    NAVSTAR.
  - **Excluded:** generic Cosmos and Fengyun, Hubble and Starship, as the entry directed.
- **Stations (ISS, Tiangong):** a button selects every tracked piece of the station.
  - The engine rings them, flies the camera there, and then follows the station as it moves. The
    camera keeps its offset, so you can still orbit and zoom around it.
  - A panel lists the pieces, with "Back to full view". Starting a near-miss replay takes over
    from a station view.
- **Collision-history panel:** below the globe.
  - **Iridium 33 / Cosmos 2251 (2009):** worded as an accidental collision.
  - **Fengyun-1C (2007):** worded explicitly as "Deliberate missile test, not a collision".
  - **Framing:** exactly one confirmed accidental collision ever, against the latest run's
    conjunction count, with the risk tiers called a heuristic, not a probability.
  - **Live counts:** the 2012 catalogued figures are given as 2012 figures, and today's counts
    come from the loaded catalog.
  - Each event has a "Show this debris on the globe" button that sets the name filters to just
    that debris.
  - Both sources are linked.
- **Nearest neighbour on inspect:** selecting an object propagates the whole catalog fresh to the
  displayed moment, once on click, not from the frame-sliced render positions.
  - The panel shows the nearest object and its distance, and labels anything under 50 m "docked
    or co-located".
  - An "Update" link recomputes at the current moment. Hidden objects still count as neighbours.
- **Deeper zoom:** the free-roam floor drops from 1.15 to 1.10 Earth radii, from about 960 km to
  about 640 km. The near clip plane is now bounded by camera altitude.

## Corrections to the scoping entry's catalog notes

Neither changes the scope; both change what the UI says.

1. **The ISS is 5 tracked pieces, not 13.**
   - The 13 was a raw substring count of "ISS", which also matches 4 unrelated objects:
     SWISSCUBE, OUTPOST MISSION 2, AISSAT 4 and DB-GLOBE MISSION EARTH-UT.
   - It also matches 4 objects named `ISS OBJECT YM/YN/YP/YQ`. Propagated to the same moment,
     these are 7,500-11,000 km from the station: free-flying objects deployed from the ISS, not
     station pieces.
   - The station itself is the 5 co-located `ISS (` modules: ZARYA, UNITY, ZVEZDA, DESTINY and
     NAUKA, all 0 km from each other.
   - Tiangong is the entry's 3 `CSS (` modules, also co-located.
2. **Fengyun: 1,954 is the whole `FENGYUN` prefix, which includes working Fengyun satellites.**
   - The ASAT debris is `FENGYUN 1C DEB`: 1,940 in the 2026-10-03 run. The other 14 are Fengyun
     weather satellites (FENGYUN 1C itself, plus the 2/3/4-series).
   - The history panel uses the debris count.

## Decisions made during implementation

- **Zoom floor 1.10, not lower.** I first tried 1.06 (about 380 km, beneath the ISS). The free
  camera always looks at Earth's centre, so from below the dense shell it saw almost no points,
  and the 2k texture was a blur. 1.10 sits just above Starlink's shells.
  - The view at the floor is still sparse: looking straight down through a thin shell catches
    few objects, which is physically right.
  - Close-ups are what replay and station views are for; both go to about 2 km.
  - A useful follow-up would be a "zoom to / follow this object" action from the inspect panel,
    reusing the station follow mode. Not built, since it's out of scope.
- **History copy kept to sourced facts.** I couldn't open CelesTrak's page to check anything
  further (its TLS certificate had expired at the time), so descriptors like "active" or
  "defunct" were left out.

## Verification

All in `portfolio-site`:
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. The globe chunk is
  156.6 KB gzipped, +2.8 KB; the main bundle is unchanged. `npm test` passes 24/24, 4 of them new:
  - group precedence and prefix-only matching
  - station matching that excludes `ISS OBJECT`s and lookalike names
  - nearest-neighbour selection
- **Headed Chromium on the M5** (Playwright) against the live bucket, now the 2026-10-03 run
  (19,246 objects), with 0 page errors:
  - **Filters:** "only" and "Show all" work.
  - **ISS:** 5 pieces, and the station stays centred while the ground moves beneath it.
    Inspecting NAUKA gives "0 km · ISS (ZARYA) (docked or co-located)".
  - **Tiangong:** 3 pieces.
  - **Replay:** starting one clears the station view.
  - **History:** the panel shows 107 and 576 Iridium 33 / Cosmos 2251 fragments and 1,940
    Fengyun-1C, against 54,684 conjunctions. Its buttons isolate each event's debris.
  - **Frame time:** 60 fps at the zoom floor.
  - **Phone:** no overflow at 390 px.
- **Nearest neighbour cross-checked against satellite.js directly:** the panel showed STARLINK-35963
  -> STARLINK-34180 at 96.6 km. An independent full-catalog propagation gives the same neighbour
  at 94.6-98.1 km within the displayed second.
- **`?date=` on a real dated report:** `/api/satellite/summary?date=2026-10-03` returned the
  21:46Z run in 0.6 s, and a missing date returned 404.

## Daily run

It's publishing again. Run `20261003T2146Z-05c185` published at 21:48Z on 2026-10-03, and
`history/index.json` now exists with its first retained date (2026-10-03). The to-do's "Watch the
daily schedule" item covers confirming that the next run fires by itself.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..feat/satellite-globe-phase-1c && npm run dev
# open http://localhost:5173/satellite-conjunction-screening
# after review: git push && gh pr create --fill
```
