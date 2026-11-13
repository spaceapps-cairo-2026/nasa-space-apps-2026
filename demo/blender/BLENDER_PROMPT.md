# Blender prompt: CropShift Earth, 30 second video

Give everything below the line to Claude (or another AI) on the Blender laptop, together with this folder.
It asks for ONE Python script that builds the whole scene automatically. The Blender person then
only checks the shots, adjusts the camera if needed, and renders.

Get the folder: it is in the team repo at `demo/blender/` (branch `lane/b-app` until it is merged into `main`).
On GitHub: open the repo, switch to that branch, open `demo/blender`, or clone the repo and copy the folder.

Folder contents:

| File | What it is |
|---|---|
| `textures/earth_day_bluemarble_10k.jpg` | NASA Blue Marble, daytime Earth, 10240 x 5120, equirectangular |
| `textures/earth_night_blackmarble2016_10k.jpg` | NASA Black Marble 2016, city lights at night, 10240 x 5120, equirectangular |
| `data/egypt_cells.geojson` | Egypt's real trend cells (about 316), already cut to Egypt's border |
| `data/egypt_border.geojson` | Egypt's detailed border (Natural Earth 1:10m) |
| `data/summary.json` | The numbers for the on-screen text (counts, fastest cell) |
| `export_for_blender.cjs` | Re-creates the `data/` files when the backend numbers are final (run from the repo root: `node demo/blender/export_for_blender.cjs`) |
| `make_textures.py` | How the two textures were made from NASA GIBS (only needed to rebuild them) |

---

## PROMPT (copy from here)

You are a senior technical artist and Blender Python developer. Write ONE complete, well commented
Blender Python script, `build_cropshift_scene.py`, that builds a cinematic, photoreal, data driven
Earth scene from the files described below. Running it inside Blender (Scripting tab, Run Script)
must build everything from an empty scene with no manual steps. Target Blender 4.2 or newer
(EEVEE Next). It must render comfortably on a laptop GPU with **8 GB VRAM**.

### Context
This is for NASA Space Apps 2026, challenge "Be An Earth System Trend Detective!". Our web app,
CropShift Earth, finds which changes in NASA climate data are statistically real. The video must
look premium AND show our real numbers. Every column you build is a real 55 x 60 km grid cell of
Egypt with a real air temperature trend (2001 to 2025, NASA POWER / MERRA-2). Do not invent data,
do not add decorative fake columns.

### Inputs (paths relative to the script's own folder: use `os.path.dirname(bpy.data.filepath)`
if the .blend is saved there, otherwise a `ROOT` constant at the top that the user can edit)
1. `textures/earth_day_bluemarble_10k.jpg`: equirectangular day texture (longitude -180 at the
   left edge, +180 at the right, latitude +90 at the top).
2. `textures/earth_night_blackmarble2016_10k.jpg`: equirectangular night lights, same layout.
3. `data/egypt_cells.geojson`: FeatureCollection. Geometry is Polygon or MultiPolygon in
   longitude/latitude degrees. Properties: `id`, `lat`, `lon`, `slope_per_decade` (degrees C per
   decade), `q`, `confidence` (`strong`, `moderate`, `not_proven`), `direction`, `strength`
   (0 to 1, already normalized: use it for height and color).
4. `data/egypt_border.geojson`: one Feature, MultiPolygon, Egypt's border.
5. `data/summary.json`: `counts.rising`, `counts.not_proven`, `counts.total`,
   `fastest_cell.slope_per_decade`, `period`. Print these at the end of the script so the editor
   can copy them into the on-screen text.

### Scene requirements
**Units and scale.** Earth radius = 10 Blender units. Convert longitude/latitude to a point on the
sphere with a helper `lonlat_to_xyz(lon, lat, r)` that matches the UV mapping of the texture
exactly (test: Cairo 31.24 E, 30.04 N must sit on Cairo in the texture). Put all code that touches
geography in small, clearly named functions.

**Earth.** UV sphere (or a subdivided quad sphere with correct equirectangular UVs), smooth
shaded, enough resolution that the limb is perfectly round at 1080p (about 256 x 128 segments).
Material, in one node tree:
- Day color from the Blue Marble texture, with a subtle ocean specular (use the blue dominance of
  the day texture as an ocean mask, roughness about 0.35 on water, 0.8 on land).
- A real sun: one Sun light. The day side is lit, the night side is dark.
- Night side: Black Marble as **emission only where the surface faces away from the sun**. Use a
  smooth day/night transition about 6 to 8 degrees wide (dot product between the surface normal
  and the sun direction, through a Map Range or Color Ramp). City lights strength about 3 to 5,
  warm color. The mask must update automatically when the sun light rotates (drive the sun vector
  from the light's rotation, or use the light object's direction through a driver).
- A thin bright **terminator glow** and a soft **blue atmosphere rim**: a second sphere at radius
  10.18 with a Fresnel/Layer Weight based emission (blue, about #6fb6ff), only visible near the
  edge, additive, and slightly brighter on the sunlit side. No volumetrics (too heavy for 8 GB).

**Space.** World background almost black (#02040a). Add a subtle star field: a large sphere
(radius about 800) with emission noise thresholded into small stars, or a few thousand tiny
emissive points made with geometry nodes. Keep it subtle, no colorful nebula.

**Egypt border.** Build curves from `egypt_border.geojson`, lifted to radius 10.004, bevel depth
about 0.006, white emission strength about 2, so the border reads clearly from close and far.

**Data cells (the hero).** For every feature in `egypt_cells.geojson`:
- Project the polygon onto the sphere (radius 10.003) and build a mesh. For proven cells
  (`confidence` is `strong` or `moderate`) **extrude radially outward** into a column of height
  `0.02 + 0.28 * strength` Blender units (heights are exaggerated on purpose, say so in a comment).
  Extrude along each vertex's own radial direction so the column walls point away from the center
  of the Earth.
- Not proven cells: a **flat tile** only (no extrusion), grey #7d838c, alpha about 0.35, so the
  desert shows through. These must never stand up.
- Color of proven columns: interpolate from #f2f2f2 (strength 0) to #b2182b (strength 1). Use a
  slight vertical gradient (darker at the base) and a soft emission of about 0.3 so they read on
  the day side. Use ONE shared material that reads the color from a mesh attribute or object
  color, not 300 materials.
- Join all proven columns into one object and all flat tiles into another object (performance).
  Store per face the cell's `strength` and a `delay` attribute (see animation).

**Animation of the columns (Geometry Nodes, preferred).** Columns grow out of the ground. Each
column starts growing at `delay = 1 - strength` (so the fastest warming places rise LAST, as the
climax) scaled into the shot's time window, takes about 0.6 s, with an ease-out (slight
overshoot of 3% then settle). Implement as a radial scale from each column's own base, driven by
the scene frame, so it is fully procedural and re-timeable from one place. Flat tiles fade in
(alpha 0 to 0.35) during the first 1 s of the same shot.

### Storyboard (30 fps, 1920 x 1080). Render each shot as its own frame range and output folder.
The finished 30 s video is: Shot 1, Shot 2, then a 12 s screen recording of our web app
(not made in Blender), then Shot 3. Leave clean space in the frame for text (top third) because
text is added in the video editor, not in Blender.

| Shot | Frames | Duration | Camera and action | Text the editor will add |
|---|---|---|---|---|
| 1. Living planet | 1 to 180 | 6 s | Wide view, whole Earth fills about 70% of frame height, slightly off center. Terminator visible: Africa and Egypt on the day side, Asia on the night side with city lights. Earth rotates very slowly (about 4 degrees over the shot), camera drifts sideways. | "Our planet is always changing. But which changes are real?" |
| 2. Dive to Egypt | 181 to 360 | 6 s | Smooth dive (ease in-out) from space to a 3/4 view of Egypt from the south-west, about 35 degrees tilt, Nile visible. Border draws on during frames 181 to 230 (animate the curve bevel factor). Tiles fade in, then columns rise with the delay rule. Hold the last 1 s still. | "N places in Egypt are proven to be warming." (N = `counts.rising` from `summary.json`) |
| 3. Pull back and title | 361 to 540 | 6 s | Reverse: pull back from Egypt to the whole Earth, columns stay visible as a red glow on the planet. End frame is clean and centered with space for the title. | "CropShift Earth. NASA data, honest statistics." + "NASA Space Apps 2026, Cairo" |

Camera: one camera, animated with keyframes on an Empty it tracks (Track To), Bezier ease in-out,
focal length 35 to 50 mm, very slight depth of field only in Shot 2 (focus on Egypt), no shake.

### Render settings (8 GB VRAM safe)
- EEVEE Next. 1920 x 1080, 30 fps. Raytracing on with low resolution if available, otherwise
  screen space reflections. Bloom/glare on (Glare node in the compositor, Fog Glow, small) for the
  city lights and atmosphere.
- Color management: AgX, look "Medium High Contrast", exposure tuned so the day side is not
  clipped.
- Output: PNG image sequences into `renders/shot1/`, `renders/shot2/`, `renders/shot3/`
  (one folder per shot) so a crash never loses finished frames.
- Add a function `set_shot(n)` that sets the frame range and output path for shot n, and a
  `PREVIEW = True` constant that renders at 50% resolution with fewer samples for quick checks.
- Textures: if VRAM is tight, provide a `TEXTURE_SCALE` option that loads a half-size copy
  (resize once with Blender's image API and save next to the original).

### Code quality
- One file, no add-ons required, Python 3.11 (Blender's). Clear sections: config, helpers
  (geography, materials, meshes), build functions, animation, camera, render setup, `main()`.
- Idempotent: running it twice must not duplicate objects (clear the scene or a named
  collection `CropShift` first).
- Print a short summary at the end: number of cells built, proven vs not proven, the numbers from
  `summary.json`, and the frame ranges of each shot.

### Acceptance checks (do them and report)
1. Cairo (31.24 E, 30.04 N) and the Nile delta line up with the texture under the border curve.
2. No column stands in the sea; Sinai and the mainland are separated by the Gulf of Suez.
3. Night lights appear only on the night side and move with the sun.
4. Frame 360 (end of Shot 2): every proven column is fully grown (count = `counts.rising` +
   `counts.falling` in `summary.json`), the tallest one is at `fastest_cell` (currently near the
   Red Sea coast, about 25.5 N, 34.4 E).
5. A full 1080p frame renders in under about 20 s on an 8 GB laptop GPU in EEVEE.

## END OF PROMPT

---

## Notes for the team (not part of the prompt)
- **The numbers are not final yet.** The backend method (decision D1) may change the counts.
  When the backend is final, re-run the export (see the top of `export_for_blender.cjs`), re-run
  the Blender script, and re-render Shot 2. Example: the placeholder method gave 92 rising cells,
  the next one 66: never hard-code the number. Always copy the on-screen numbers from
  `data/summary.json`, never type them from memory.
- **Text and music go in the video editor** (CapCut, DaVinci Resolve or Clipchamp), not in
  Blender. Use English subtitles. Keep each text line on screen at least 2 seconds.
- **Credits** for the slide or the end card and `docs/REFERENCES.md`: NASA Blue Marble Next
  Generation and NASA Black Marble 2016 (via NASA GIBS), NASA POWER (MERRA-2), Natural Earth
  borders, Blender.
