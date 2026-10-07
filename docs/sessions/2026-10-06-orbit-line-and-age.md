# Session 2026-10-06: orbit line for the selected satellite; satellite age paused (portfolio-site)

Future features 1 and 2 from the 2026-10-06 brainstorm list in `docs/todo.md`.

- **Code:** in `portfolio-site`, on branch `feat/orbit-line-and-age`. One commit, local only and not
  pushed:
  - `4ccb460` feat: draw the selected object's orbit as a closed loop
- **Feature 2 (satellite age) was not built.** The brief said to stop if the launch designator
  wasn't already in the objects data the site loads, and it isn't. The two ways forward are below
  under "Decision needed". Nothing in this repo's code was changed.

## Feature 1: orbit line

### What it does

- **Selection:** selecting an object draws its whole orbit as one closed loop through it.
  - A new selection replaces the line.
  - Deselect, a click on empty space, a near-miss pair view or a station view removes it.
  - It shows in both Globe and Sky.
- **Panel:** the selected-object panel gains an **Orbit** row, a short stroke in the line's
  colour plus the period ("93.0 min period", "23.9 h period"), so the new line has a key.

### How

- **Samples:** the period is 2π over the elements' mean motion (`satrec.no`, radians per
  minute). The loop is 360 SGP4 positions from half a period before the displayed moment to half
  a period after, in the scene's existing inertial (ECI) frame. There an orbit is very nearly a
  fixed ellipse, while the Earth turns under it.
  - **The object is on its own track:** the samples *are* its trajectory over that span, so the
    object is exactly on the line, not just close to it.
  - **Closing chord on the far side:** SGP4's perturbations keep the two ends from meeting.
    Drawn as a loop, the closing chord sits opposite the object and is no longer than an ordinary
    step.
  - **Measured gaps:** ISS 31 km (0.45% of its orbit radius), MTG-S1 (geostationary) 15 km, POLAR
    (eccentricity 0.66) 34 km.
- **Recompute threshold: half a period.** Inside that span the object is on its sampled track.
  Past it the object is on its next revolution, which perturbations, mainly J2 nodal precession
  (about 0.3° per orbit in low Earth orbit), have shifted.
  - **Measured shift:** at +½ period it's 29 km for the ISS, 9 km for POLAR and 0.5 km for MTG-S1.
  - **When it fires:** the engine checks every frame and resamples once the displayed time is
    more than half a period from the loop's centre. That covers normal play, 50x and slider jumps
    in either direction.
  - **Cost:** 0.10 ms per resample for the ISS and 0.16 ms for POLAR (Node on the M5). At 50x the
    ISS resamples about once a minute of real time.
- **Rendering rules:**
  - **Dimming:** the line has its own material, so the dimming system (which rewrites point
    colours) never touches it.
  - **Culling:** `frustumCulled = false` on both lines, since the geometry is replaced on each
    resample (the stale-bounding-sphere bug from the conjunction view).
  - **Picking:** the line isn't part of the point buffers that picking searches, so it can't
    block a pick.
- **Wide lines (`Line2`, 2 CSS px).** A first version used plain WebGL lines, one device pixel
  wide (half a CSS pixel on a 2x screen). In screenshots that was readable against space but
  nearly invisible over the Earth's disc and its shell of points. three.js's `Line2` fixes that.
  It adds 29 kB (7.8 kB gzip) to the globe chunk, which loads only on this page. The chunk was
  already over Vite's 500 kB warning before this change.
- **Sky.** This turned out to be a small change, so it's built.
  - **Projection:** each frame, the same samples are turned into directions from the observer at
    the displayed moment and drawn on the dome at 1.005x its radius. That's just behind the points
    and in front of the dome grid.
  - **Below the horizon:** the existing ground hemisphere hides that part, so only the
    above-horizon arc shows, and the line never draws over the ground.
  - **Selection below the horizon:** the arc still shows while the object's own ring and label
    are hidden.

### Colour: pale periwinkle `#b0a8ff`

The brief preferred white or a pale blue. I measured candidates against every colour already in
use: the type and owner series, gold, the selection ring, the cyan station ring, the risk colours,
the Sky horizon and the grid.
- **White** is already the neighbour's dashed line and pair ring A, so it was out.
- **Plain pale blues** (`#cfdcff`, `#b8c9ff`, `#a9c4ff`, `#d6e2ff`) were within 0-5 (OKLab
  distance x100) of the cyan station ring under colour-blind simulation, and 5-8 from the Sky
  horizon line, which the Sky arc meets.
- **`#b0a8ff`**, a slightly more saturated pale periwinkle blue:
  - at least 13 from every colour in use, and at least 8 under deuteranopia/protanopia
    simulation;
  - contrast 9.5:1 against the sky `#05070d` and 6.3:1 against the Sky ground `#26303c`;
  - its nearest colour is the cyan station ring, which only shows in a station view, and
    selecting an object ends that view, so the two never share the screen.
- **Red wasn't needed.** Drawn at 75% opacity.

## Verification

All in `portfolio-site`, headed Chromium on the M5, live catalog (19,239 objects).

- **On the line, measured on screen.** The distance from the selected object's drawn point to the
  drawn line was 0 px in every case:
  - ISS at the centre time, at +0.49 period (no resample), at +0.52 period (resampled: the centre
    moved 0.52 periods) and after a +6 h slider-style jump (centre moved 6.00 h);
  - MTG-S1, POLAR, and the ISS at 50x;
  - in Sky, a LEO object and MTG-S1 (0.01 px).
- **Lifecycle:**
  - a new selection replaced the line;
  - Deselect cleared it (`orbit` null, line hidden, not drawn);
  - a near-miss pair view and a station view each removed it;
  - toggling Globe and Sky kept it, with the globe line drawn in Globe and the dome line in Sky,
    never both.
- **Dimming:** with dimming active (bright set: the ISS and its neighbour), the line kept its
  0.75 opacity, and the neighbour line is still white and dashed.
- **Picking:** the script clicked a point on the POLAR line with no object within 63 px. The
  selection cleared, as for any empty-space click, so the line takes no clicks.
- **Rendering:** `Line2`, 2 px, `#b0a8ff`, opacity 0.75, `frustumCulled` false. The engine's
  draw stamp confirmed it rendered in the frame.
- **Screenshots:** desktop Globe (ISS crossing the Earth's disc, the geostationary loop, the
  POLAR ellipse), desktop Sky (a LEO arc, the geostationary arc through MTG-S1), phone Globe and
  phone Sky.
- **Frame time** at 50x with the full catalog and a selection: 16.67 ms mean (p95 17.6) at both
  1x and 4x CPU throttling.
- **Errors:** none on the page.
- **Checks:**
  - `npm run lint`, `npx tsc -b` and `npm run build` are clean. The build's only warning is
    Vite's chunk-size note, which predates this change.
  - `npm test` passes 48/48, including 5 new orbit tests: the period against the TLE's mean
    motion, no loop without a positive mean motion, one period nearly closing the loop, the loop
    being seamless and passing through the object, and the half-period refresh rule.
- **Evals:** none run. No pipeline code changed.

## Feature 2: satellite age, decision needed

**Finding:** `objects/current.json` (2026-10-06) has no designator field. Its object keys are
`norad_id`, `name`, `tle_line1`, `tle_line2`, `element_epoch_utc`, `satcat_owner`, `object_type`,
`active_payload` and `source_groups`. The designator is in the raw GP data (`OBJECT_ID`) and in
the report's object records (`international_designator`), but the objects builder doesn't copy
it. Per the brief, I stopped there and changed nothing in this repo. Two options:

1. **Pipeline: add the field to the objects file.**
   - **Change:** in `src/app/reporting/objects_builder.py`, `object_entry` gains
     `"international_designator": obj.object_id`, the same source as
     `report_builder.py`. It's additive, so `OBJECTS_SCHEMA_VERSION` stays 1 under the module's
     own rule.
   - **Test:** `tests/test_objects_builder.py` adds the key to the expected set and asserts
     `"1998-067A"` for the ISS fixture.
   - **Catch:** it appears from the next daily run only. The 7 retained dated snapshots, which
     the slider can show, would read "Unknown" until they age out.
2. **Site only: parse TLE line 1, columns 10-17.**
   - **Why it works:** the pipeline already writes `OBJECT_ID` there. `omm.initialize` takes it
     from the GP record and the TLE export prints it as `YYNNNA` (`1998-067A` becomes `98067A`).
   - **Coverage:** every one of the 19,239 objects parses (none blank or malformed), launch years
     1964-2026, and it works for every retained snapshot today.
   - **Costs:** a two-digit year (57-99 is 19xx, 00-56 is 20xx, unambiguous until 2057) and
     reading an implicit TLE field rather than a named one.

Either way the age mode itself is as briefed: an "Age" colour mode with under 2 / 2-10 / over 10
years and Unknown, wired into the legend, filters and dimming. It isn't built yet.

## Flag for review

- **Phone Globe panel:** on a phone in Globe mode the existing full selected-object panel covers
  much of the stage, so only part of the orbit shows behind it. That layout predates this change
  (Globe mode was left as it was); a folded panel like Sky's would fix it.
- **Why the closing chord is invisible:** the loop is the object's own track over one period, not
  an idealised ellipse. Its closing chord (15-34 km) sits on the far side and is no longer than a
  normal step, so it doesn't show.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..feat/orbit-line-and-age && npm run dev
# after review (Max): git push -u origin feat/orbit-line-and-age && gh pr create --fill
# docs: cd ../satellite-conjunction-screening && git push -u origin docs/orbit-line && gh pr create --fill
```
