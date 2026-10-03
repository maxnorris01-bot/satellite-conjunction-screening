# Session 2026-10-03: globe Phase 1c fix round (portfolio-site)

Implements the 2026-10-03 "Globe Phase 1c fix round" working-notes entry.

- **Code:** in `portfolio-site`, on branch `fix/satellite-globe-phase-1c-feedback`, cut from
  `main` after Phase 1c merged. Two commits, local only and not pushed.
- **Scope:** orientation and propagation are untouched.

## 1. A way back after isolating debris (fixed)

- **Both of the entry's fixes.** Each collision-history button is now a toggle: pressed, it
  isolates that event's debris and reads "Show everything again". Pressing it again restores
  exactly the previous view, not just everything; a test with Starlink hidden beforehand left
  Starlink hidden after toggling off.
- **Always-visible reset.** A filter bar below the globe ("Showing 683 of 19,246 objects:
  Iridium 33 debris, Cosmos 2251 debris. Show all objects") appears whenever anything is hidden,
  by name filters or colour-category toggles, whichever entry point set it.
- **Show all objects** clears both kinds of filter.

## 2. Nearest-neighbour line (added)

- **Shared line.** The replay's dashed line and on-globe label are now one shared "link"
  component in the engine, used by both near-miss replay and the nearest neighbour. Only one
  shows at a time, since selection is single.
- **Live label.** For the neighbour, the label shows their distance at the displayed moment,
  updated as both objects move. The panel says the nearest-neighbour search ran at the click
  time. The replay keeps its fixed label, the report's `miss_distance_km`.
- **Rings.** The neighbour gets a white ring and the selected object keeps its coral one, and the
  panel keys the neighbour's name to its ring.

## 3. Single-select (fixed)

- **What caused the report:**
  - Inspect, near-miss replay and station views were separate states, so their rings could show
    together, alongside a still-highlighted table row.
  - The pick radius was 10 px. Over the dense LEO disc that caught some object on 16 of 20
    random clicks, so "clicking empty space" usually just selected a different object.
- **Now there's one selection.**
  - Picking an object replaces any other object, pair or station: the marks clear and the table
    row unselects.
  - If the camera was focused on a pair or station, it eases back to free roam from where it is,
    without jumping. The clock is left as it was, and Live resumes real time.
  - A click on no object clears everything, including a replay or station view.
  - The inspect panel has a labelled Deselect button as well as the ×.
- **Pick radius is now 6 px (16 px for touch).** A random click on the full-globe disc still hits
  something about 15 times in 20, because the shell really is that dense at full-globe zoom.
  Off-disc space is empty, and zooming in opens up gaps. Going smaller would make the 2 px points
  hard to hit.

## 4. Zoom floor: the code works; the report was likely a cached bundle or a different mode

The entry's three checks, in order:

- **(a) Deploy.** Production deployed the Phase 1c merge (`1abb50b`): GitHub deployment
  `6833940107`, state `success`, at 2026-10-03 22:34:51Z.
  - I can't fetch the production bundle myself, because the alias is behind Vercel Deployment
    Protection.
  - A local build of `main` produces `SatelliteGlobe-Bo_5C-dv.js`, and that file contains the
    1.1 floor (no 1.15).
  - **For Max:** hard-reload production, then in DevTools > Network confirm the globe chunk is
    `SatelliteGlobe-Bo_5C-dv.js`. Once this fix round merges, the name will change.
- **(b) Every input path.** TrackballControls has a single zoom pipeline, and `minDistance` is
  enforced in `_checkDistances()` on every update. Measured in the browser with the dev-only
  `debugState()` hook, zoomed fully in:

  | Input path | Camera distance from Earth's centre |
  |---|---|
  | Mouse wheel | 1.1000 R (638 km up) |
  | Trackpad pinch (ctrl+wheel) | 1.1000 R |
  | Touch pinch (CDP two-finger events) | 1.1000 R |

  Middle-drag goes through the same clamp.
- **(c) Free roam vs. focus modes.** Station-follow and replay zoom allow about 2 km (measured:
  1.9 km from the ISS), by design.
  - After "Back to full view" the floor is restored to 1.1.
  - Before this round, if a replay was left without "Back" (for example by clicking an object),
    the old flow still restored the floor through `resetView`. This round's ease-out also
    restores it (measured: floor 1.1 after leaving a replay by click).
- **Remaining explanations:** a cached bundle, or testing in a focus mode. Separately, from 1.15
  to 1.10 the view's ground footprint shrinks only by about 1.5x, and both are "fully zoomed in
  on a blurry texture". It's noticeable side by side but not dramatic.

## Verification

All in `portfolio-site`:
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. The globe chunk is
  157.4 KB gzipped, and the dev hook is absent from the production build. `npm test` passes 24/24.
- **Headed Chromium on the M5** against the live bucket, with 0 page errors. Everything in
  sections 1-4 above was exercised by script with the debug hook: toggle and restore, the filter
  bar for both filter types, the neighbour line and label, A then B replacement, empty click,
  Deselect, replay then pick, replay then empty click, and station then empty click.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..fix/satellite-globe-phase-1c-feedback && npm run dev
# after review: git push && gh pr create --fill
# after merge + deploy: hard-reload production and check the SatelliteGlobe chunk name in DevTools
```
