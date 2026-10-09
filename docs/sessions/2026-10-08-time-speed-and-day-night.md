# Session 2026-10-08: playback speed from any time; clearer day/night (portfolio-site)

- **Code:** `portfolio-site`, branch `fix/time-speed-and-day-night`, two commits, local only:
  - `29f762e` fix: play at the selected speed from any time, not just live
  - `e300b27` fix: make day and night easier to tell apart on the globe

## Commit 1: playback speed

### What happened before (reproduced at localhost:5173)

- The clock had three kinds, and only `live` carried a speed:
  - `live` played from an anchor at `speed`;
  - `offset` (any time picked on the slider) advanced at 1x, fixed;
  - `frozen` (a near-miss replay) held at its TCA.
- After scrubbing 6 h back with 50x selected, the clock became `offset` and advanced at 1.00x. All
  three speed buttons were disabled ("Playback speed applies in Live mode"); a forced click did
  nothing. It didn't snap back to Live; it just ignored the speed.
- A near-miss replay was frozen at 0x, with the buttons disabled.

### The new model (`src/globe/clock.ts`)

Every clock carries the selected speed:

| Kind | Meaning |
|---|---|
| `live` | plays forward from now at `speed` |
| `scrub` | plays forward from a picked moment at `speed`, and stays a scrubbed time |
| `frozen` | paused at `atMs` (end of the range, or a replay's fly-in), speed kept |

Changing speed re-anchors at the displayed moment, so there's no jump. A paused clock resumes when
a speed is picked. Live is the only way back to the present.

### Behaviours, defined

- **Scrubbing keeps the speed:** 50x Live, then scrub 3 h back, plays at 50x.
- **Future end (about 24 h ahead):** playback pauses there, the speed stays selected, and the
  readout says "paused". This applies to Live and to scrubbed time (it used to apply to Live only).
- **From the past side:** a scrubbed time plays through the present and on, without becoming Live
  and without stopping at "now". Chosen so playback never jumps or stops unexpectedly; Live is one
  click away.
- **Snapshot boundaries:** crossing midnight while playing at 50x loads that day's snapshot
  (2026-10-06 to 2026-10-07 took about 2 s, during which the old snapshot keeps animating). Fixed
  along the way: the selected object used to be cleared on every snapshot load. It's now kept by
  NORAD ID when it exists in both snapshots (the ISS stayed selected across the boundary).
- **Near-miss replay:** holds at the TCA while the camera flies in, then plays on at the selected
  speed. At 10x, 22 s of sim time had passed about 2 s after arrival. The on-globe miss label
  shows the reported miss distance at the TCA and the live separation afterwards (e.g. "169 km").
- **Everything that follows the clock works from a scrubbed time at 50x:**
  - the orbit line is resampled at half-period edges;
  - the neighbour refreshes (3.3 sim-min in 4 s);
  - the sun direction and day/night move;
  - Sky's sun line updated ("Sun 24.7° below" to "25.2° below" in 4 s).
- **Slider arrow keys:** not the same root cause. Arrow presses still don't move the slider (0 min
  after two presses). That's the input's value/step snapping, independent of the clock model.
  Left open in `docs/todo.md`.

### Tests

`tests/clock.test.ts` has 7 new tests:
- scrubbed playback at 1/10/50x, past and future;
- a speed change from a scrubbed time;
- scrubbing keeps the speed;
- replay from the TCA at each speed;
- a paused clock resuming;
- the end-of-range pause, live and scrubbed;
- playing through the present without becoming live.

The old test asserting "speed only applies to live" was removed.

## Commit 2: day/night contrast

- **Change:** the lit side is x1.6 brighter (linear) and the night side keeps 3% of the day texture
  instead of 8%. City lights, the soft +3 to -12 degree terminator band and the switch are
  unchanged.
- **Switch off:** still the old look, 1 pixel of 2.4 million differing.
- **Measured improvement:** mean linear luminance of the Earth's lit vs night pixels, full catalog
  showing, rendered without points (`dnc-*` screenshots):

  | View (8 Oct) | Before ratio | After ratio |
  |---|---|---|
  | Europe, 17:00 UTC | 1.62 | 2.46 |
  | Americas, 23:00 UTC | 1.60 | 2.13 |
  | Pacific, 07:30 UTC | 1.55 | 1.95 |

- **Legibility:** WCAG contrast against rendered Earth colours, computed from the textures with the
  shader maths.
  - **Points:** every colour in all four modes still separates at 3:1 or better through its fill or
    its dark rim, on both sides.
    - Night median: fill 5.4-12.5:1.
    - Night 95th percentile: now 4.2-9.7:1 (was 3.1-7.1).
    - Bright day: rim 15.4:1 (was 10.1).
  - **Rings and lines:** on the night side they're unchanged or better (orbit line 7.7-9.8:1). Over
    the brightest day surfaces (cloud, ice), white, gold and cyan are 1.1-1.6:1, a little better
    than before for the orbit line and selection ring. Still under 3:1, as before this change. The
    existing dark-outline to-do covers it; not applied.
- **Frame rate:** 60 fps at 50x, desktop and phone, 1x and 4x CPU throttle, day/night on or off.
  Sky also 60 fps. No page errors.

## Checks

- **Tests:** 75/75. One shading test's bound assumed the old full-day weight of 1. It failed after
  commit 2 was first made, and was fixed before the commit was amended.
- **Lint, typecheck, build:** clean.
- **Evals:** none run. No pipeline code changed.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..fix/time-speed-and-day-night
# after review (Max): git push -u origin fix/time-speed-and-day-night && gh pr create --fill
# docs: cd ../satellite-conjunction-screening && git push -u origin docs/time-speed-day-night && gh pr create --fill
```
