# Session 2026-10-03: globe Phase 1 (portfolio-site)

Implements the 2026-10-03 "Globe build plan" working-notes entry and its amendment.

- **Code:** in `portfolio-site`, on branch `feat/satellite-globe`. Four commits, local only and
  not pushed, per `docs/collaboration-conventions.md` (don't push until reviewed).
- **This repo:** this docs branch only.

## What changed and why

- **Globe** (`src/globe/engine.ts`, lazy-loaded through `src/components/SatelliteGlobe.tsx`):
  - **Data:** fetches `objects/current.json` straight from the bucket.
  - **Points:** all 19,240 objects as raw three.js points. Each is propagated with satellite.js
    in the inertial (TEME) frame, a tenth of the catalog per frame (`slice=10`, from the first
    commit).
  - **Earth:** a NASA Blue Marble texture (2048x1024, 524 KB) on a sphere rotated by GMST, with
    no per-object frame conversion.
  - **Clock:** runs in real time by default.
  - **Camera:** trackball-style, with no fixed "up", as the plan asked.
- **Orientation verified two ways:**
  - **Unit test:** `tests/globe.test.ts` checks five places at three moments. The textured
    sphere point (three.js's real UV layout and rotation) must match satellite.js's own
    geodetic -> Earth-fixed -> inertial chain within 0.6 degrees. Flipping the rotation sign or
    mirroring an axis each fails the test.
  - **On screen:** replaying the top near miss put the ring over central Quebec. satellite.js
    puts that pair's ground point at 50.3 N, 69.7 W.
- **Near-miss replay:** selecting a row in the conjunctions table freezes time at that
  conjunction's TCA and flies the camera to the pair.
  - Both objects come from the same snapshot the row came from. A ring marks them, and a panel
    names them, with "Back to full view" returning to Live.
  - The table follows whatever snapshot the globe is showing.
- **Colouring:** a type / owner / flat toggle with a legend and counts. Switching only recolours;
  nothing re-fetches or re-propagates.
- **Time slider:**
  - **Range:** back to the oldest retained day (at most 7) and about 24 h forward, plus a Live
    button.
  - **Past times** load that day's `objects/<date>.json.gz`, chosen from `history/index.json`,
    with the nearest earlier day if one is missing.
  - **Forward times** use `current.json`.
  - **Before any history exists,** the range stops at the current run's window start, with a note.
- **`GET /api/satellite/summary?date=YYYY-MM-DD`:** reads that day's `reports/<date>.json.gz`
  server-side.
  - Dates are strictly validated (400 otherwise), and a missing day returns 404.
  - Dated reports get a day-long CDN cache, since they never change.
- **Bundle:** three.js and satellite.js are in their own chunk (578 KB, 150 KB gzipped), loaded
  only on the satellite route. The main bundle is 266 KB, down from 273 KB on `main`.

## Decisions made during implementation (the plan left these open)

1. **Owner colouring is the top 3 plus "Other", not the top N with N around 6-8.**
   - The globe is a scatter, so every colour must be distinguishable from every other. The
     dataviz validator (all pairs, dark background `#05070d`) passes three hues but fails every
     four-hue set on colour-blind and normal-vision separation.
   - The three are the United States, China and CIS: 89% of objects, assigned by owner code
     rather than rank, so colours don't swap between days.
   - Type mode uses the same three hues: active payload, debris and rocket body, plus grey for
     inactive or unknown.
2. **Past-day near misses come from the API, not the browser.** A dated report is 5.3 MB
   gzipped but 78 MB decompressed, too heavy to parse in a visitor's browser for a 10-row table.
   ADR 0010 already names the Vercel function as the home for history logic.
3. **Vite `worker.format: 'es'`.** satellite.js 7's only entry point also re-exports its WASM
   build, whose worker uses top-level await, and that breaks Vite's default worker format. The
   globe uses the plain-JS API; the built chunk contains no WASM code and no worker file is
   emitted.
4. **Default point size 2.2 CSS px with a dark rim,** tuned from screenshots so the texture shows
   through the dense LEO shell.

## Verification

All in `portfolio-site`:
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. `npm test` passes 13/13
  (7 new: orientation, colours, timeline, `?date=`).
- **Headed Chromium on the M5** (Playwright, DPR 2) against the live bucket:
  - 0 page errors.
  - **Live frame time:** 16.7 ms mean, p95 17.7, unthrottled. 16.7 ms mean, p95 17.5, at 4x
    CPU throttling.
  - Colour modes, replay and back, and the +12 h slider all behave as described.
  - No horizontal overflow at a 390 px phone viewport.
- **Backward range:** checked with a simulated `history/index.json` (the real one doesn't exist
  yet). The slider reached 2026-10-01, the globe loaded that day's objects, and the table
  heading switched to the 2026-10-01 snapshot via `?date=`.

## Open questions and things to flag before merge

- **The daily run is failing, so there's no history yet.** The retention image (`e7f3427`) was
  deployed to Machine `1850e47cdd43e8` at 04:41Z on 2026-10-03.
  - That update interrupted an in-progress run.
  - The manual start at 04:43Z then failed at the very first fetch with `403 Forbidden` from
    CelesTrak (`GROUP=active`). The same URL returns 200 from Max's network. CelesTrak answers
    repeated same-data downloads within about 2 hours with 403, so it's likely a short-term
    block on the Fly IP.
  - **Don't start the Machine repeatedly.** Wait about 2 h and start once, or let the schedule
    fire.
  - The bucket's `current.json` files are still from 2026-10-02 04:05Z, and
    `history/index.json` doesn't exist yet.
- **Vercel preview deployments can't load the globe.** The bucket's CORS rule allows only the
  production alias and localhost, not `portfolio-site-<hash>-max-norris.vercel.app`. The rest of
  the page works on a preview; the globe shows its error state. Two options:
  - review on `localhost:5173`, or
  - approve adding a preview-origin pattern to the CORS rule. Whether Tigris accepts a `*`
    wildcard inside an origin is unverified.
- **Scrolling over the globe zooms it** instead of scrolling the page, which a trackpad user will
  hit.
- **Not tested on Safari or real phone hardware,** the same known risk the plan lists.
- **The Blue Marble texture is the December composite,** so northern Canada is snow-covered year
  round. A different month is a one-file swap.

## Next commands

```bash
# portfolio-site: review locally
cd ../portfolio-site && git log --oneline main..feat/satellite-globe && npm run dev
# then open http://localhost:5173/satellite-conjunction-screening

# after review, per collaboration-conventions.md
git push && gh pr create --fill
```
