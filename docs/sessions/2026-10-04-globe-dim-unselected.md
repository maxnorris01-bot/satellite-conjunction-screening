# Session 2026-10-04: dim everything except the selected object and its neighbour (portfolio-site)

Implements the 2026-10-04 "Globe: dim everything except the selected object and its live
neighbour" working-notes entry.

- **Code:** in `portfolio-site`, on branch `feat/satellite-globe-dim-unselected`, cut from `main`
  after the live-neighbour branch merged. One commit, local only and not pushed.
- **Scope:** orientation and the frame-sliced propagation are untouched.

## What changed

- **Dimming:** while one object is inspected, every other point is drawn at **20%** of its normal
  alpha (`DIM_ALPHA = 0.2` in `globe/engine.ts`). The selected object and its live nearest
  neighbour stay at full strength.
  - Pair (near-miss) and station views don't dim.
  - Deselecting by empty click, Deselect, or picking a pair or station restores everything.
- **A separate layer, as the entry required.** The engine keeps two buffers:
  - **`rgba`, the filter/colour state:** alpha 0 means hidden by a filter, 1 means shown. It stays
    the only source of truth for "visible", so picking, the neighbour search and the "Showing N
    of M" count are unaffected by dimming.
  - **`drawRgba`, what the GPU draws:** `rgba` with the dimming applied by a pure `dimExcept()`,
    rebuilt from `rgba` only on selection, filter or neighbour changes, never per frame.
    Un-dimming is therefore an exact copy.
  - Dimmed alpha is a multiple of a non-zero alpha, so it never reaches 0: dimmed points stay
    pickable and stay eligible as the neighbour.
- **Neighbour handoff.** On a live refresh that changes the neighbour, the line, label and
  brightness all switch in the same frame. The first neighbour found after a selection is exempt
  from dimming the same way. While a refresh is pending after a time jump, there's no neighbour
  line, so only the selected object is bright.
- **Rendering change this needed.** The points material used `alphaTest: 0.5`, which would have
  discarded a 20% point (hidden, not dimmed).
  - Points now blend: `alphaTest: 0.01`, `transparent`, and no depth writes, so a faint point
    can't block a bright one behind it.
  - They still depth-test against the Earth, so the far side stays hidden, and filter-hidden
    points (alpha 0) are still discarded.
  - With nothing selected, the globe looks the same as before (screenshot compared).
- **Dim level.** 20% kept after looking at it against the dense full-globe shell. The shell reads
  as a faint backdrop with the continents showing through, and the two full-strength points
  inside their rings stand out.

## Verification

All in `portfolio-site`, headed Chromium on the M5 against the live bucket, using the dev-only
debug hook to read which points are drawn at full strength.

- **Selecting** an object leaves exactly `{selected, neighbour}` bright.
- **Handoffs:** 1,201 of 1,201 frames at 10x and 1,201 of 1,201 at 50x had exactly
  `{selected, neighbour}` bright with the dashed line on that same neighbour, through 9 and 42
  neighbour changes respectively. No frame had both or neither bright.
- **Frame time** at 50x with a selection: 16.7 ms mean, p95 17.7, unthrottled; 16.7 ms mean, p95
  17.6, at 4x CPU throttling.
- **Under filters:** with OneWeb, Kuiper and China hidden in owner mode:

  | State | Hidden | Dimmed | Drawn buffer vs filter buffer |
  |---|---|---|---|
  | Nothing selected | 4,524 | 0 | identical |
  | Selected | 4,524 | 14,720 (every shown point but the pair) | differs only by dimming |
  | After Deselect | 4,524 | 0 | identical |

  No shown point ever reached zero alpha, and the filter buffer was unchanged by
  selecting and deselecting.
- **Starlink-only in owner mode:** with a selection, the neighbour is a shown object and the
  filter bar count is unchanged.
- **Picking:** a dimmed point can still be picked, and it becomes the new bright selection.
- **Pair and station views:** no dimming.
- **Errors:** none on the page.
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. `npm test` passes 29/29,
  with a new `dimExcept` test (never hides, keeps the pair, exact restore). The globe chunk is
  158.3 KB gzipped, and the dev hook is absent from the production build.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..feat/satellite-globe-dim-unselected && npm run dev
# after review: git push && gh pr create --fill
```
