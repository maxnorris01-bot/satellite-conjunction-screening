# Session 2026-10-11: descend zoom, Pause/Play, Today's imagery control, orientation and zoom limit (portfolio-site)

Docs-only record in this repo of two `portfolio-site` rounds on the Satellite view. These build
the "next round" decided on 2026-10-10.

- **PR #27, descend zoom** (branch `feat/descend-zoom`). Squash-merged into `portfolio-site`
  `main` as `56100cc` ("feat/descend zoom (#27)"); the four commits survive on the branch:
  - `07d0a75` feat: descend zoom with an automatic hold in the satellite view
  - `8897c0c` feat: Pause / Play button for the shared clock
  - `c188ce9` feat: a clearer "Base map | Today's imagery" choice that fades up close
  - `1357cdf` fix: EOX attribution in EOX's current wording
- **PR #28, orientation and zoom limit** (branch `feat/orientation-zoom-limit`):
  - `e3d3667` feat: heading-up orientation in the satellite view, north up as an option
  - `262399c` feat: closest zoom stops where the base imagery is still sharp

  As of this write-up (fetched 2026-10-11) these two commits are on `origin/feat/orientation-zoom-limit`
  but not yet on `portfolio-site` `main`.

## What changed

**Descend zoom** (`07d0a75`; camera maths in `src/globe/descend.ts`, pure and tested).
- **Zoom toward the pointer.** Scroll and pinch zoom toward the pointer or fingers, so the ground
  (or sky) under them stays under them. Riding the satellite, zooming narrows the field of view,
  down to 30 degrees.
- **Detach.** Zooming in past 30 degrees over the ground, or a double-click/double-tap, detaches
  the camera.
  - It then holds over that ground point, fixed to the Earth's surface: it rotates with the Earth,
    so the spot doesn't drift at any playback speed.
  - Zooming then descends toward the pointer, and dragging pans the ground. The point under the
    pointer stays under it through the hand-over.
- **Return.** A "Return to satellite" chip, Esc, or any look preset goes back to riding the
  satellite. Back still leaves the Satellite view, from a held view too.
- **Transitions.** View changes animate over 500 ms with ease in/out, and are instant under
  `prefers-reduced-motion`.
- **Imagery limit.** The descent eases smoothly into the finest imagery level (within 2.5x of the
  limit each step shrinks, then it stops) instead of hitting a hard stop.

**Pause/Play** (`8897c0c`), next to Live and 1x/10x/50x in the Globe, Sky and Satellite views.
- Pause freezes the shared clock at the moment shown, keeping the selected speed. It works from
  Live, a scrubbed time or playback.
- Play resumes from the paused moment at the selected speed, as a scrubbed time. It never jumps to
  Live; only the Live button does that.
- Space toggles it, except while focus is in a text field or on a control where Space already does
  something.
- At the end of the slider's range, where playback already pauses itself, Play is shown
  unavailable.

**Today's imagery control** (`c188ce9`).
- **The control:** the checkbox became a two-option "Base map | Today's imagery" control near the
  top of the Satellite panel (44 px tall). Beside it is plain-language explanation text: the base
  map is a sharp, seamless, cloud-free 2016 composite with no current weather; Today's imagery
  shows real clouds and storms for the slider's date, with seams between satellite passes.
- **While it's on:** the imagery date is shown prominently ("follows the time slider"), with the
  note that zooming in close fades it to the sharper base map.
- **Fade rule:** the daily layer's finest level is NASA GIBS level 8, ~244 m/px (level 7 on
  phones). It's fully shown while one of its pixels covers at most one screen pixel at the centre
  of the view, gone at two, and smooth in between. Looking straight down at 30 degrees on a 576 px
  tall view, that's from ~263 km down to ~131 km camera height. Fully faded, it's hidden and
  fetches nothing. NASA's acknowledgment shows only while the overlay is visible.
- **Phones hide the long explanation.** This is temporary, until the phone full-screen rework.

**Attribution** (`1357cdf`). The EOX footnote now uses EOX's current wording: "EOxCloudless
https://cloudless.eox.at by EOX IT Services GmbH (Contains modified Copernicus Sentinel data
2016)". That's the wording from its WMTS capabilities and licence summary, replacing the older
s2maps.eu text.

**Orientation** (`e3d3667`).
- **Heading up is the default:** up on screen is the satellite's direction of travel. **North up**
  is an option ("Heading up | North up" in the Satellite panel; switching animates over 500 ms,
  instant under reduced motion).
- **On detach,** the ground direction that was up on screen is captured as the held view's
  heading and kept. From the Down view nothing swings; the camera only moves toward the ground.
- **A small compass** on the map shows where north is. The Looking row names the orientation.
- **Return to satellite** goes back without a swing.
- **Poles:** held views stay at least 0.5 degrees (about 55 km) from a pole, so north stays
  defined.

**Closest zoom rule** (`262399c`).
- **The rule:** one pixel of the finest tile level in use may cover at most 1.0 CSS pixel at the
  centre of the view. It counts CSS pixels, not device pixels, so a 2x display stops at the same
  height as a 1x one.
- **New limits:** **10.27 km** camera height on desktop (EOX level 13, ~9.55 m/px, 576 px tall
  view) and **19.26 km** on phones (level 12). The old limits, 5.13 km and 9.63 km, let one source
  pixel cover two screen pixels, which was visibly soft (e.g. over New York).
- The smooth easing into the limit is unchanged.

**A bug fixed on the way:** loading another snapshot (the same satellite at a new catalog index)
reset a held view. It now keeps the view.

## Measured

Reported from the implementation sessions (headless Chromium, per the headless rule):
- **Pointer accuracy:** the point under the pointer stays within 0.01 px over 7 zoom steps.
- **Drift:** 0 px for a held view at 50x over 6 simulated minutes.
- **Bundle:** the globe chunk grew +10.5 kB (+3.4 kB gzipped) for the descend round and +3.6 kB
  (+1.1 kB gzipped) for the orientation round.
- **Tests:** 139 after the descend round, then 146.

## Still needs checking by hand

- **Real-GPU frame rate:** the headless checks use software WebGL.
- **Touch:** pinch, double-tap and pan on a real phone or tablet.

## Follow-ups added to `docs/todo.md`

- Softer detach swing (a big swing from Forward or a sideways look).
- Return restores the previous field of view (it comes back at 30 degrees, not the starting 70).
- Wheel steps aren't animated on notched mice.
- Soft imagery below about 10 km camera height.
- About 13 wheel steps from GEO to the floor.
- Dragging to look around while riding with North up is off by the roll angle.
- Detaching from Forward changes the compass by about 17 degrees, because the tilt can't carry
  into a straight-down view.
- Show the Today's imagery explanation on phones (in the full-screen rework).
- Backlog: sharper US close-up imagery (USGS National Map aerial, ~1 m/px).

## Next command

```bash
gh pr create --fill
```
