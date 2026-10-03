# Session 2026-10-03: globe Phase 1b (portfolio-site)

Implements the 2026-10-03 "Globe Phase 1b" working-notes entry.

- **Code:** in `portfolio-site`, on branch `feat/satellite-globe-phase-1b`, cut from `main` after
  Phase 1 merged. Three commits, local only and not pushed, per
  `docs/collaboration-conventions.md`.
- **This repo:** this docs branch only.

Orientation, propagation and the data pipeline are unchanged. The sliced propagation loop, the
inertial-frame mapping and the GMST rotation are byte-for-byte the Phase 1 code, and Phase 1's
orientation test still passes.

## What changed and why

- **Category toggles:** each legend row in type or owner mode has a checkbox that hides that
  category's points. There are no checkboxes in flat mode.
  - Each mode remembers its own hidden set.
  - Points carry rgba colours, and alpha 0 discards a point in the shader. Hiding is instant and
    nothing re-propagates.
  - Hidden points also can't be clicked.
- **Playback speed (1x/2x/5x/10x):**
  - **Live only.** The buttons are disabled while scrubbed or replaying, and the slider stays a
    direct jump.
  - **No jumps.** A speed change re-anchors at the moment currently shown.
  - **Default is still 1x real time.** After faster playback, the readout says how far ahead it
    is instead of claiming "real time", and clicking Live snaps back to now.
- **Near-miss replay, both objects:** Phase 1 did draw two rings, one per object, but both were
  white and the same size. A typical flagged pair is tens of metres apart, sub-pixel at any
  normal zoom, so the rings drew as one. Changes:
  - The two objects now get different colours and sizes (white and gold) and read as two
    concentric rings. The panel keys each name to its ring colour.
  - A dashed line joins the two objects at the TCA, with an on-screen label showing the
    conjunction's `miss_distance_km`.
  - Replay can now zoom in to about 2 km (near/far clip planes follow the camera). At full zoom
    the two objects and the line between them are visible even for the 33 m top pair. At normal
    zoom the label carries the distance.
- **Click-to-inspect any object:** a click, as opposed to a drag-to-rotate, picks the nearest
  visible point.
  - **Threshold:** within 10 CSS px, or 20 px for touch. A screen-space threshold, as the scope
    suggested, behaves the same at every zoom.
  - **Skipped:** points behind the Earth or behind the camera.
  - **Panel:** name, NORAD ID, type, SATCAT owner, and latitude/longitude/altitude at the
    displayed moment, updated as the object moves.
  - **Closing:** an empty-space click or the close button.
  - **Layout:** it stacks with the replay panel when both are open.

## Verification

All in `portfolio-site`:
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. The globe chunk is
  153.8 KB gzipped, +3 KB; the main bundle is unchanged. `npm test` passes 20/20, 7 of them new:
  - clock speed and re-anchoring
  - picking with the same pixel threshold at three zoom levels, Earth occlusion, behind-camera
    and hidden points
  - the visibility mask
  - type labels
- **Headed Chromium on the M5** (Playwright, DPR 2) against the live bucket, with 0 page errors:
  - **Toggles:** with active payloads hidden, a click on the disc picked debris, never a payload.
  - **Speed:** 10x put the clock 35 s ahead after 4 s.
  - **Frame time:** 60 fps (16.7 ms mean, p95 17.5) at 10x speed with 4x CPU throttling.
  - **Replay:** two rings and a "0.033 km" label, hidden again after "back".
  - **Inspect and phone:** inspect opened and closed as designed, and at a 390 px phone width it
    worked by tap, with no overflow.
- **Cross-checked against satellite.js directly:**
  - The inspect panel's position for STARLINK-37535 matched within 0.02 degrees (the panel
    updates on a 250 ms tick).
  - For all ten top near misses, the separation the globe draws at the TCA matched the report's
    `miss_distance_km` within 1 m. The browser's satellite.js and the pipeline's Python SGP4
    agree.

## Open questions and things to flag

- **The daily run still hasn't published since 2026-10-02 04:05Z,** about 41 h ago as of
  21:42Z on 2026-10-03.
  - The Machine still has `schedule: daily`, but its last event is the failed 04:43Z start
    (CelesTrak 403) from the earlier session, so the backward slider still has no data.
  - Unverified inference: Fly resets the daily timer on `fly machine update` or a manual start.
    If so, the next scheduled run is around 04:45Z on 2026-10-04. Check then:
    `curl -sI https://satellite-conjunction-screening.fly.storage.tigris.dev/history/index.json`.
- **Vercel preview origins still aren't in the bucket's CORS rule,** so review on
  `localhost:5173` as with Phase 1.
- **Not tested on Safari or real phone hardware.**

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..feat/satellite-globe-phase-1b && npm run dev
# open http://localhost:5173/satellite-conjunction-screening
# after review: git push && gh pr create --fill
```
