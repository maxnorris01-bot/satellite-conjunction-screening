# Session 2026-10-04: project page redesign (portfolio-site)

Implements the 2026-10-04 "Project page redesign: stats beside risk, globe with a side column,
conjunction dropdown" working-notes entry.

- **Code:** in `portfolio-site`, on branch `feat/satellite-page-redesign`. One commit, local only
  and not pushed, easy to revert.
- **Scope:** layout and presentation only; no data, propagation or globe-behaviour changes.

**The mockup image itself wasn't available to this session.** It isn't in either repo (the scoping
commit touched only the two docs files) or anywhere on this machine. Everything was built from the
entry's written description, so the visual comparison against the actual mockup is still Max's to
make. Screenshots taken this session: desktop at 1440 and 1100 px, phone at 390 px.

## What changed

- **Header:** the tech chips sit beside the eyebrow on one row, and "View on GitHub" sits on the
  right of the title row. The lede wraps to two lines.
- **Overview row:**
  - **Left, "Latest run":** three tiles. "Faster screening after the KD-tree swap" is dropped,
    along with the unused `kdTreeSpeedup` field.
  - **Closest approach tile:** short label as in the mockup, but the value is still
    `closest_active_approach_km`. The note under the tiles now says "Closest approach is the
    nearest pass involving an active satellite".
  - **Right, "Risk breakdown":** the existing card.
- **Globe:** shown without its heading. The legend and filters stay top-left in the canvas.
- **Side column** (about 21rem, beside the globe):
  - **"Top conjunctions":** a native `<select>`. Each option is "rank. OBJECT A × OBJECT B · miss km
    · tier", and the placeholder is "Select to show on Globe".
  - **Note** under it: "Top N of X, ranked by risk tier, then miss distance". The label gets the
    "· YYYY-MM-DD snapshot" suffix when the slider is in the past.
  - **Below it, one panel at a time:** selected object, closest approach, station, or the
    collision history by default.
  - **Panels left the canvas.** In the column they re-point the globe theme's CSS variables to the
    page's light tokens. The white ring key gets an outline so it's visible on white.
- **Under the globe:** time controls, then the imagery caption, then the "Showing N of M" bar.
  That's the entry's listed order; before this the bar sat between the canvas and the time
  controls.
- **Pipeline:** unchanged.
- **Below 960 px**, everything stacks in the entry's order: header, stats, risk, globe, controls,
  dropdown and panel, pipeline.
- **Dropdown behaviour:** choosing an option calls the same `replay` the table did (fly-in, frozen
  clock, dimming). The current replay shows as selected. Back, an empty click, picking an object or
  starting a station view returns it to the placeholder.

## Verification

All in `portfolio-site`, headed Chromium on the M5, live data.

- **Structure:** exactly three tiles. Headings are "Latest run", "Risk breakdown" and "Pipeline"
  only. The chips share the eyebrow row and the GitHub button shares the title row.
- **Layout:** stats sit beside risk, and the side column is beside the globe (684 px and 336 px).
  The canvas matches its stage size.
- **Panels:** every type rendered in the side column (collision history, closest approach,
  selected object, station; screenshots). Inside the canvas, only the legend, the hint and the
  on-globe miss label remain.
- **Dropdown:**
  - Selecting an option replays it, with rings drawn and the select showing it.
  - ArrowDown on the focused select moves to the next conjunction and replays it.
  - Back, an empty click and picking an object all return it to the placeholder.
  - Choosing a conjunction while an object is inspected replaces the inspect panel.
- **Resize path:** at 1100 px the canvas follows (664 px), and the miss label stays at its projected
  position next to the pair.
- **Phone (390 px):** stacked in the specified order, globe 540 px tall, no horizontal overflow.
- **Frame time** with a pair shown: 16.7 ms mean, p95 17.6, at both 1x and 4x CPU throttling.
- **Errors:** none on the page.
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. `npm test` passes 30/30.
  The main bundle shrank slightly (265.3 KB); the globe chunk is 158.6 KB gzipped.

## Where it may not match the mockup

These are flagged rather than improvised.
- **Side column taller than the globe.** With collision history showing (the default), the column
  is about 920 px against about 650 px for the globe and its controls, leaving empty space under
  the controls. Its text is already slightly tightened. Fully closing the gap would mean cutting
  copy, collapsing the two event cards, or capping the column with its own scroll.
- **Closed dropdown truncates long options.** A native select can't wrap, so a long option is cut
  off when closed (the risk tier first, e.g. "3. STARLINK-5371 × DUTHSAT-2 · 0.074 km ·…"). The
  open list shows every option in full. A custom listbox would fix it if this matters.
- **Shorter time slider.** It shares the globe column's width with Live, the speed buttons and the
  readout (about 200-290 px at 1100-1440 px). The readout could move to its own line if the mockup
  shows a full-width slider.
- **Phone stats:** the tiles stack one per row below 420 px. The phone order otherwise matches.
- **Reduced motion:** the page had no reduced-motion handling before (only focus-visible styles),
  so there was none to keep, and none was added.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..feat/satellite-page-redesign && npm run dev
# compare against the mockup; after review: git push && gh pr create --fill
```

## Follow-up after review: keep the top, revert the rest

Max reviewed the branch and kept only the top portion (header, Latest run and Risk breakdown), with
tweaks. A second commit on the same branch (`feat/satellite-page-redesign`, now 2 commits, still
local) does that.

**Kept, with tweaks:**
- **Title row:** "View on GitHub" follows the title with a normal gap (24 px), not pushed to the
  right edge. It wraps below the title on narrower screens (it does at 820 px and on a phone).
- **Lede:** it uses the full page width instead of the old 48rem header cap, one sentence per line.
  On desktop (1440 px and 1024 px) the first sentence sits on one row.
- **Tiles:** three, labelled "objects screened", "conjunctions" (was "conjunctions flagged") and
  "closest approach". Every value and label fits one line at 1440, 1024, 820 and 390 px.
- **Note under the tiles:** kept, including "Closest approach is the nearest pass involving an
  active satellite".
- **Risk breakdown:** the card holds only the three bars. The caveat ("N high-risk conjunctions in
  this run. Risk tiers are a stated heuristic, not a true probability of collision.", same
  wording) is now a plain muted note below the card.

**Reverted to the pre-redesign page.** These files were restored from `main` rather than
re-implementing the old layout:
- **Globe component and its CSS:** restored whole. The panels (selected object, closest approach,
  station, collision history) are back inside the canvas with their dark styling. The time
  controls and the "Showing N of M" bar are back in their original places.
- **Page files:** restored as the base, with only the kept top portion re-applied. The globe
  section, with its "Every tracked object" heading, sits below the overview row. The Top
  conjunctions table is back, with its "Show on globe" buttons, note and past-snapshot suffix.
  There's no dropdown or side column, and Pipeline is unchanged.
- **Still dropped:** the `kdTreeSpeedup` data field, since the tiles stay at three.
- **README:** keeps the separate correction of the playback speeds to 1/10/50x.
- **Proof the globe revert is exact:** against `main`, the globe component files have no diff, and
  the built globe chunk has the same content hash as the pre-redesign build
  (`SatelliteGlobe-DAZLrNFJ.js`).

**Verified** in headed Chromium:
- **Page:** headings run Latest run, Risk breakdown, Every tracked object, Top conjunctions,
  Pipeline. The overview row sits above the globe section. No horizontal overflow at any width.
- **Table replay:** replaying a conjunction from the table, on desktop and phone, scrolls the globe
  into view, flies to the pair with the rings and line drawn, and shows the closest-approach panel
  inside the canvas, with the table row selected.
- **Errors:** none on the page.
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. `npm test` passes 30/30.
- **Screenshots:** desktop, two tablet widths and phone.

**Alignment tweak, before merge (third commit):**
- **Shared rows.** The Risk breakdown card now matches the Latest run tiles' height, and the two
  notes start at the same vertical level. This is done structurally: the overview row is a
  four-row subgrid (title, error, tiles/card, note) that both columns share. No pixel heights are
  hard-coded.
- **Card condensed.** Tighter padding, bar gaps and row line-height, with the bars centred, so
  there's no dead space under them. Tile height is unchanged.
- **Measured equal heights and note tops** at 1440 (114.6 px), 1024 (108.7 px), 900, 820 and
  801 px (105.8 px). Equal space sits above and below the bars, and nothing overflows.
- **Tablet fit.** To stay side by side down to 801 px, the tiles get more of the row below
  1000 px, with slightly tighter horizontal spacing and a smaller label (same line box, so the
  same height). The columns stack only below 800 px, where no alignment is needed.

The open mockup-fit questions above (tall side column, truncated dropdown, short slider) no longer
apply, since that part of the redesign is reverted.
