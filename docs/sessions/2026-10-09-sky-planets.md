# Session 2026-10-09: planets and the Moon in the Sky view (portfolio-site)

- **Code:** `portfolio-site`, branch `feat/sky-planets`, one commit, local only:
  - `5d17f35` feat: planets, the Moon and a clickable Sun in the Sky view
- **Browser checks:** headless Chromium only (SwiftShader WebGL), per the repo's headless rule.

## Decision: the ephemeris

| Option | Cost | Accuracy | Moon parallax | Verification burden |
|---|---|---|---|---|
| (a) astronomy-engine, lazy-loaded | 22.7 kB gzipped chunk (51.8 kB minified) | about 1 arcsecond | built in (topocentric with an observer) | spot checks |
| (b) self-written low-precision | about 3-5 kB | about 0.01-0.1 degree planets; the Moon needs a sizeable series to stay under a fraction of a degree | write it | a full reference suite |

- **Chose (a).** The library is loaded with `import()` the first time the Sky view gets an
  observer. In the browser the Globe view fetched neither `planets.ts` nor astronomy-engine; they
  arrived only after a location was set.
- **Dependency change:** astronomy-engine moved from devDependencies to dependencies.
- **Globe chunk:** grew 9.4 kB (UI and placement code; about 3 kB gzipped).

## What changed

- **Bodies:** the seven planets, the Moon and the Sun are computed for the observer
  (`src/globe/planets.ts`).
  - Positions are topocentric and geometric (no refraction, like the satellites).
  - Each body also gets its magnitude, its distance, and for the Moon the illuminated fraction
    and whether it's waxing.
  - Updates happen at most every 100 ms of real time, and only when the displayed time moved a
    second; a new observer or a jump of over a minute updates at once. Each update costs
    0.09-0.8 ms.
- **Markers:** discs with a dark rim, like the satellite points.
  - **Planets:** sized by magnitude, 13 - 1.6 x mag px, between 6 and 20 (Venus 20, Jupiter about
    17, Saturn 13, Uranus and Neptune 6).
  - **Sun and Moon:** 30 px each.
  - **Colours:** stylized light tints.
  - **Drawing order:** under the satellite points, so a satellite crossing the Moon stays visible.
- **The Moon's phase:** its disc is redrawn when the phase or the on-screen limb direction changes
  (illuminated fraction by 0.003, or the angle by 2 degrees). The lit limb points along the great
  circle toward the Sun, projected on screen, so it stays right as you look around.
- **Selection:** the same single model as satellites (`nextSelection` in `src/globe/skybodies.ts`).
  - Picking a body replaces a satellite and the other way round; an empty click or Deselect clears
    either.
  - Switching to the Globe clears a body and keeps a satellite.
  - **Panel:** azimuth, elevation, magnitude, distance (AU for planets and the Sun, km for the
    Moon), and for the Moon the illuminated percentage and phase name. On a phone it folds to two
    lines (name, az/el) with Details, like the satellite panel.
- **Pick priority:**
  1. a click inside a body's disc picks the body;
  2. otherwise the nearest satellite within 6 px (16 px touch);
  3. otherwise a body within that distance of its disc edge.
- **Dimming:** a body selection dims every satellite, like any selection.
- **Your sky panel:** a plain-text line, "Up now: Neptune 33°, Saturn 28°", highest first. It
  isn't in any live region; the one live region announces only "Selected Saturn" or "Deselected".
- **Labels:** `placeLabels` in `src/globe/layout.ts` places them in priority order (the selected
  body, then by brightness).
  - **Spots tried:** below, right, above, left of the marker. The first spot that's on screen,
    above the horizon, and clear of the grid and compass labels, the body discs, the selected
    satellite's name and the labels already placed is used.
  - **No free spot:** the label is hidden, unless the body is selected.
  - **Phone (under 640 px):** only the Sun, the Moon, planets brighter than magnitude 1.5 and the
    selected body are labelled.

## Verification

- **Reference values** (`tests/skybodies.test.ts`):
  - **Moon phase at eclipses:** illuminated over 0.999 at the 2026-03-03 total lunar eclipse,
    under 0.001 at the 2026-02-17 annular solar eclipse.
  - **Great conjunction:** Jupiter and Saturn 5.9 arcminutes apart on 2020-12-21 (published:
    about 6.1, geocentric).
  - **Venus:** 45.9 degrees from the Sun at its greatest evening elongation, 2026-08-15.
  - **Mercury:** 25.2 degrees at its greatest evening elongation, 2026-10-12.
  - **The Sun** agrees with the globe's own sun module (satellite.js) to under 0.3 degrees.
  - **Moon parallax:** the topocentric Moon sits 0.8-1.05 degrees below a geocentric reference
    when it's low. The geocentric vector had to be rotated from J2000 to the equator of date; a
    first unrotated attempt was off by precession.
- **Santa Cruz, 8 October 2026:**
  - **18:32 PDT (dusk):** Mercury SW (az 238, el 11, mag -0.1), Venus SW (az 239, el 5, mag -4.6),
    Neptune E (el 4), Sun W (el 1).
  - **21:00 PDT:** Saturn E (az 111, el 28, mag 0.2), Neptune ESE (az 119, el 33). Jupiter and
    Mars rise later (morning sky).
  - **Mercury cross-check:** it's 4 days from its greatest evening elongation (2026-10-12, 25.2
    degrees), hence low in the south-west after sunset beside Venus.
- **Moon today:** a 2.9% waning crescent, about 1.5 days before new moon (2026-10-10).
  - **Shapes checked:** a 12% waxing crescent (14 Oct, 19:30 PDT, Sun set in the west) is lit on
    its lower right; 54% (19 Oct) is lit on the right; 26 Oct is full.
- **Browser (headless):**
  - **Pick tests:** a click inside the Moon's 15 px disc, at its edge and 4 px outside all picked
    the Moon; 12 px outside picked nothing; a click on a satellite 19.7 px from the Moon's centre
    (outside the disc, inside its tolerance ring) picked the satellite.
  - **Selection transitions:** Saturn, then a satellite (WILDBLUE-1), then Neptune, then
    Deselect all worked. Saturn selected then the Globe toggle cleared it: no panel, no labels.
  - **Live region:** 0 mutations in 4 s at 50x with the Moon selected, while the "Up now" line
    kept updating.
  - **Label sweep:** 12 times of day x 3 directions, with 0 overlaps against grid labels and 0
    between body labels.
  - **Sun label at sunset:** it first landed on the ground. That's now prevented; it moves beside
    the Sun.
- **Contrast** (WCAG):

  | Mark | Brightest day sky `#223956` | Lighter ground `#26303c` |
  |---|---|---|
  | Planet tints | 6.8-10.9:1 | 7.8-12.4:1 |
  | Moon and Sun | 10.2-10.4:1 | 11.6-11.9:1 |
  | Label ink | 9.9:1 | 11.3:1 |

  - Night sky: all at least 11.7:1.
  - The Moon's unlit side is deliberately faint (1.3:1 on the day sky); the dark rim and the lit
    part carry it.
- **Frame rate (headless, software rendering: relative only):** at 50x, 19.0 fps with bodies vs
  18.9 without at 1x CPU, and 17.3 vs 17.2 at 4x. No measurable cost. 29 ephemeris updates in 3 s
  at 50x, at most 0.2 ms each. Real-GPU frame rates weren't measured: headless rule.
- **Phone (390 px):** at 21:00 facing ESE, both planets are drawn and only Saturn is labelled.
  Tapping Neptune selects it, shows its label, and the folded panel keeps its ring visible.
- **Errors:** none on the page.
- **Checks:** `npm test` 89/89 (19 new), lint, typecheck and build clean. No pipeline code
  changed, so no evals ran.

## Flag for review

- **Dimming on a body selection:** every satellite fades to 20%. It reads clearly and wasn't
  annoying in the checks, but it hides satellite context while you look at a planet. If it
  bothers you in use, a lighter dim for body selections is a one-line change.
- **Colour closeness:** Neptune's tint is 7.9 (OKLab x100, worst vision) from the orbit line,
  just under the 8 target. They're different shapes (a disc and a line) and only meet if a
  selected orbit passes Neptune.
- **Labels and satellite dots:** labels avoid other labels and markers but not the satellite dots
  themselves (too many), so a planet's name can sit over a dot.
- **Not checkable headless:** real-GPU frame rate, real touch hardware, and the real geolocation
  prompt (emulated).

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..feat/sky-planets
# after review (Max): git push -u origin feat/sky-planets && gh pr create --fill
# docs: cd ../satellite-conjunction-screening && git push -u origin docs/sky-planets && gh pr create --fill
```
