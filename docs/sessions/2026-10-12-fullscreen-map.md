# Session 2026-10-12: full-screen map on phones, and the page-width fix (portfolio-site)

Docs-only record in this repo of `portfolio-site` PR #29, merged to `main` as the squash commit
**`e0fbdf3`** ("feat/fullscreen map (#29)"). The branch commits (dated 2026-10-11), now only on
the deleted feature branch:
- `b0888ca` fix: the conjunction table no longer widens the page on phones
- `dbea6df` feat: full-screen map state logic
- `3224927` feat: full-screen map mode, and a clean map on phones

## What changed

**Phone page width** (`b0888ca`).
- **The bug:** the conjunction table already scrolled sideways inside its card. But the visually
  hidden "Replay" labels in its rows were absolutely positioned with no positioned ancestor inside
  the scroll box, so they escaped its clipping. That stretched the whole page to about 691 px at a
  390 px viewport, and mobile browsers zoomed the page out to fit.
- **The fix:** the card is now positioned, so the labels are clipped with the table. The page is
  exactly 390 px and 360 px wide at those viewports, and the table scrolls inside its card.

**Full-screen state machine** (`dbea6df`, `src/globe/fullscreen.ts`, pure and tested).
- **Entering** pushes one history entry, locks page scroll, and requests native full screen where
  the Fullscreen API exists.
- **Leaving:** four ways out, each with the right clean-up (drop the history entry unless Back
  already did; exit native full screen unless the browser already did; restore the page's scroll
  position and focus):
  - the Exit button;
  - Esc, when there's no Fullscreen API (the CSS-only mode);
  - the browser leaving native full screen by itself;
  - the browser's back button.
- **Phone rule:** a viewport up to 640 px wide, or up to 500 px tall (a phone in landscape).

**UI** (`3224927`).
- **Embedded on a phone:** a clean map with no panels over it, plus a compact "Full screen" button
  on the map. The view toggle and time bar stay reachable below. Selecting a satellite shows a
  small box with its name, "Enter full screen to see details and controls" and a Full screen
  button.
- **Full screen:**
  - **Layout:** it fills the visible viewport (`100dvh`) with safe-area padding, over a locked
    page. Filters fold to a "Colours and filters" button. The info panel is a bottom sheet (a
    side sheet in landscape). "Exit full screen" is in the top-right corner, 44 px.
  - **Reachable:** the time bar, Live, Pause, the speeds, the imagery and orientation controls,
    and the "why Today's imagery" explanation, which the embedded phone view had to hide.
  - **Desktop** gets the same button, and its side panels stay as they are (moved down for Exit).
- **iPhone and elsewhere:** iPhone Safari has no Fullscreen API for arbitrary elements, so full
  screen there is a CSS full-viewport mode. Elsewhere (desktop, Android Chrome) it's the same mode
  plus native full screen.
- Transitions are skipped under `prefers-reduced-motion`, touch targets are at least 44 px, and
  pinch, double-tap and drag still work.

**A fix found in screenshots:** in landscape, the sheet's handle was drawn under the panel text. It
now stays on top.

## Numbers

Reported from the implementation session:
- **Tests:** 153 (7 new).
- **Bundle:** the globe chunk grew +3.6 kB (about 1 kB gzipped).

## Verification

- **Headless** (Chromium via Playwright, per the headless rule): 390x844, 360x740, 844x390
  (landscape) and desktop.
- **By hand after merge, on Max's phone:** full screen works, and Today's imagery works.
- **Not individually verified:**
  - iPhone Safari's toolbar and safe-area behaviour in detail (the toolbar showing and hiding, the
    notch and home indicator against the safe-area padding);
  - Android Chrome's native full screen;
  - rotation while in full screen on a real device.

## Known gap

The Globe | Sky | Satellite toggle isn't available inside full screen. Switching views still
works from the selection panel. A compact toggle inside full screen is a to-do item.

## Operational note

On the phone, the Vercel **preview** URL showed "couldn't load the latest run", while production
loaded fine. The likely cause is the bucket's cross-origin (CORS) rule not allowing the preview
address. That matches a gap already recorded on 2026-10-03 (`docs/sessions/2026-10-03-globe-phase-1.md`):
the rule allows only the production alias and localhost, not
`portfolio-site-<hash>-max-norris.vercel.app`, and whether Tigris accepts a `*` wildcard inside an
origin is unverified. **For this occurrence it's a likely cause, not confirmed:** the bucket's rule
and the preview's request weren't inspected. Confirming the rule, or documenting why previews can't
load data, is a to-do item.

## Next command

```bash
gh pr create --fill
```
