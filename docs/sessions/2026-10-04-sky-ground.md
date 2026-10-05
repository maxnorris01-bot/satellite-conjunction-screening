# Session 2026-10-04: Sky view, lighter ground with a perspective grid (portfolio-site)

Implements the 2026-10-04 "Sky view: lighter ground with a perspective grid" working-notes entry.

- **Code:** in `portfolio-site`, on branch `feat/satellite-sky-ground`. One commit, local only and
  not pushed.
- **Scope:** a visual change in the Sky scene only; the sky maths, time handling and globe are
  untouched.

## What changed

- **Ground.** The existing ground hemisphere, which already hides below-horizon objects, is now
  a muted slate, `#26303c`.
  - **Against the sky:** clearly lighter than the `#05070d` sky (1.51:1).
  - **Against the points:** far darker than any point. Point luminance is 0.22 or more against
    the ground's 0.029, so the points stay the brightest things on screen.
  - Ground and points never overlap, since below-horizon points stay hidden behind it.
- **Perspective grid.** Grid lines sit on a plane one eye-height below the observer, aligned
  north/south and east/west.
  - **True perspective:** the camera sits at the origin, so each plane point is pushed out along
    its own direction onto a sphere just inside the ground. That gives exactly the image of a real
    floor, with lines converging toward the horizon. Each line is subdivided every 0.25
    eye-heights so it curves correctly.
  - **Cell size: 0.6 eye-heights** (about 1 m tiles at a 1.7 m eye height). A cell then spans about
    31° straight down: enough lines to read as a floor without clutter.
  - **Fade: from 3 to 18 eye-heights out** (18 is about 3.2° below the horizon). A first try at 6
    to 30 let the converging lines pile into a lighter band just under the horizon; the closer
    fade removes it, and nothing shimmers.
  - **Colour:** `#6c7a8d` at up to 35% alpha.
  - **Decoration only:** built once, it's not part of the sky geometry.
- **Horizon and labels.** The horizon ring is drawn in front of the ground grid, `#c9d1dc` at 85%,
  keeping the edge crisp. The 30°/60° rings are unchanged.

  | Label | Colour | On the sky (`#05070d`) | On the ground (`#26303c`) |
  |---|---|---|---|
  | N/E/S/W | `#e8ecf4` | 17.0:1 | 11.3:1 |
  | 30°/60°/Zenith | `#a3acbd` | 8.8:1 | 5.9:1 |

  All are above the 4.5:1 target in either place.
- **Looking down.** The look's pitch range is now -89° to 89° (it was 0° to 89° in Phase 1), so
  the ground can actually be seen, as the entry's "looking straight down" check requires. Drag
  still moves the sky with the pointer, and the initial view is unchanged.

## Verification

All in `portfolio-site`, headed Chromium on the M5, live data.

- **Before/after screenshots** at desktop (1440) and phone (390), each looking at the horizon,
  45° down and straight down. The "before, looking down" shots set the pitch directly, since
  Phase 1 couldn't look down.
  - **Before:** an almost-black ground with no depth cue.
  - **After:** a slate floor with a converging grid, a crisp horizon, and the points still the
    brightest elements.
  - **Straight down:** square tiles, with no shimmer at the horizon.
- **Orientation:** the scripted orientation test in `tests/sky.test.ts` still passes (part of
  35/35). In the page, facing north-east, the rendered E label is right of N.
- **Behaviour unchanged:**
  - Drag looks around and now reaches below the horizon, and the wheel changes the field of view.
  - Filters still drive the above-horizon count (all 1,205; Starlink only 411).
- **Frame time** in Sky at 50x with the full catalog: 16.7 ms mean, p95 17.6, at both 1x and 4x
  CPU throttling. The grid adds no measurable cost.
- **Errors:** none on the page.
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. `npm test` passes 35/35.

## Follow-up: a curved dome grid (second commit)

Max liked the lighter ground but wanted a curved grid on the dome itself instead of the floor grid.

- **Dome grid** in the old floor grid's blue-grey, `#6c7a8d`:
  - Elevation rings every 15°, at 28% opacity. The horizon stays separate and crisp.
  - Azimuth lines every 30° from the horizon to the zenith, at 25%, with N/E/S/W at 42%.
  - The azimuth lines fade out between 70° and 84° elevation, leaving a clean disc overhead
    rather than a clump.
  - **No z-fighting:** the grid sits on a sphere just outside the points' sphere and draws before
    them. Seen from the centre, that puts it behind the points.
- **Labels:**
  - Azimuth degrees along the horizon at the 30° steps (30°, 60°, 120° and so on), with N/E/S/W
    unchanged.
  - The 30°/60° elevation labels sit on both the north and south meridians, so they're visible in
    the default south-facing (or north-facing) view.
  - **Colour:** the existing ring-label colour, `#a3acbd`: 8.8:1 on the sky and 5.9:1 on the ground.
  - **No mirroring:** all labels are placed with `skyDirection`. A scripted check facing north found
    30° right of N and 330° left; facing south, 150° left of S and 210° right.
- **Floor grid: kept, very faint (14% alpha, down from 35%).** Screenshots were compared with no
  floor grid, with the full floor grid, and with the faint one. Without any floor grid, the ground
  reads as a flat slab at the horizon. The full one competes with the dome grid. The faint one keeps
  a little receding depth under the dome grid without drawing the eye.
- **Grid toggle:** a labelled checkbox in the Your sky panel's title row, on by default and in both
  the expanded and folded panel. It works by keyboard (Space toggles it) and hides the dome grid and
  its degree labels. N/E/S/W, the zenith mark, the horizon and the faint floor grid stay.
- **Unchanged:** sky maths, drag/zoom/FOV, filters, dimming and time handling. The scripted
  orientation test in `tests/sky.test.ts` passes (35/35).
- **Verified:**
  - **Screenshots:** before/after at desktop and phone width, at the horizon, looking up at the
    zenith, and at narrow (30°) and wide (100°) fields of view.
  - **Frame time:** at 50x with the full catalog, 16.7 ms mean (p95 about 18.4) at both 1x and 4x
    CPU throttling.
  - **Errors:** none on the page.
  - **Checks:** lint, typecheck, tests and build are clean.
- **Noted:** from London the geostationary belt sits at about 30° elevation, so in the default
  south view the "30°" label sits among that row of points. It's still legible, and the overlap is
  latitude-dependent.

## Not in this round

Kept in `todo.md` under Later, per the entry: sky gradient and horizon haze, distance-based point
size/brightness, motion trails, background star field.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..feat/satellite-sky-ground && npm run dev
# after review: git push && gh pr create --fill
```
