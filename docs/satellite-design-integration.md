# Satellite design integration — 2026-09-14

The Mission CONOPS work from `d4f8adb` is integrated with shared design inputs and responsive lab layouts.

- Global and Constellation altitude fields are bidirectionally synchronized. Semiconductor, Coverage and Payload minimum elevation fields share one value (initially 20°). RF power and processor TOPS also mirror their dependent controls.
- Coverage, pass timeline and RF geometry use the same altitude, elevation, inclination, plane count, satellites per plane and Walker F. Both backend integrated paths preserve the requested inclination instead of replacing it with 42°.
- The SVG previews altitude, constellation parameters, requested beams, beamforming architecture, regenerative stack and ISL offload. After a successful calculation, body, solar-panel and radiator sizes change relative to mass, payload power and radiator-area proxies. These are schematic indicators, not mechanical dimensions or a solar-array sizing model.
- The diagram distinguishes an input preview from current computed results. Invalid mission inputs show an explanation. Stale responses do not replace results after the design changes; failures keep the last successful KPIs and show a message and calculation time.
- Hidden charts are queued until their tab has a measurable size. Resizing redraws visible charts; asynchronous Plotly errors are handled. Lab grids, run buttons, mission controls and Poisson plots remain within mobile and tablet viewports. The SVG scrolls inside its own panel to keep labels readable.
- Scenario restoration runs before startup API calls and restores all form fields. SYNC refreshes integrated results, orbit sweep, coverage, Monte Carlo and pass timeline. Optimizer, Poisson and rain analysis retain their own run controls.

Validation passed: Python geometry regression for both integrated paths; JavaScript syntax and Git whitespace checks; browser regression over all 30 view/width combinations; shared-input and SVG changes; invalid/stale/failed requests; persistence; Optimizer execution. No browser page errors occurred. See `tests/README.md` for reproduction.

Local review captures are in `artifacts/ui-integration-2026-09-14/`. Artifacts from the earlier review are retained separately. Deployment validation is outside this local integration check.

## Interactive mission illustration

The Mission Center includes a locally rendered isometric SVG illustration with three views: overall operations, spacecraft/payload detail, and coverage. Display buttons toggle link paths, labels, and flow animation; reduced-motion preferences disable animation. These view controls do not change or save engineering inputs.

- Altitude moves the primary satellite; altitude and minimum elevation change the illustrative coverage envelope. The displayed ground-arc radius uses `6371 * (acos(6371 / (6371 + altitude) * cos(elevation)) - elevation)` with angles in radians.
- Walker plane count, satellites per plane, inclination, and phasing change representative orbital tracks and satellites. Rendering is capped at 5 planes, 4 satellites per plane, and 12 beams, with actual input counts shown in labels.
- Beamforming architecture/elements, frequency/bandwidth, antenna diameter, payload architecture/stack, and ISL offload update the illustration immediately. The payload view distinguishes RF relay from digital processing paths.
- Body size, solar panel size, and radiator size use bounded relative proxies from the current calculated mass, payload power, and radiator area. Modified inputs show preview state until RUN/SYNC completes.

The illustration is not a freely rotatable 3D model or an orbit propagation result. Landforms, orbit positions, user terminals, beam centers and individual beam widths are schematic; the visibility envelope is not a link-qualified service area. The solar panels represent relative payload demand, not a complete solar-array sizing model.

Composition references: [ESA Ground segment](https://www.esa.int/ESA_Multimedia/Images/2012/12/Ground_segment) and [Copernicus Ground Segment overview](https://www.esa.int/Applications/Observing_the_Earth/Copernicus/Ground_Segment_overview). Artwork is generated locally from SVG geometry; source images are not embedded.
