"""Stitch NASA GIBS tiles into equirectangular (plate carree) Earth textures for Blender.

GIBS EPSG:4326 '500m' tile set, zoom level 4: 512 px tiles of 18 degrees,
20 columns x 10 rows cover the world -> 10240 x 5120 px.

Run from D:\\College\\NasaSpaceApp\\video:   python -I make_textures.py
"""
from __future__ import annotations

import io
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

BASE = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best"
LAYERS = {
    "earth_day_bluemarble_10k.jpg": f"{BASE}/BlueMarble_NextGeneration/default/500m/4/{{r}}/{{c}}.jpeg",
    "earth_night_blackmarble2016_10k.jpg": f"{BASE}/VIIRS_Black_Marble/default/2016-01-01/500m/4/{{r}}/{{c}}.png",
}
COLS, ROWS, TILE = 20, 10, 512
OUT = Path(__file__).resolve().parent / "textures"


def fetch(url: str) -> Image.Image:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return Image.open(io.BytesIO(r.read())).convert("RGB")
        except Exception as e:  # retry flaky tiles
            if attempt == 3:
                raise RuntimeError(f"{url}: {e}") from e
            time.sleep(2)


def build(name: str, pattern: str) -> None:
    canvas = Image.new("RGB", (COLS * TILE, ROWS * TILE))
    jobs = [(r, c) for r in range(ROWS) for c in range(COLS)]
    with ThreadPoolExecutor(8) as pool:
        for (r, c), img in zip(jobs, pool.map(lambda rc: fetch(pattern.format(r=rc[0], c=rc[1])), jobs)):
            canvas.paste(img, (c * TILE, r * TILE))
    OUT.mkdir(exist_ok=True)
    canvas.save(OUT / name, quality=92)
    print("wrote", OUT / name, canvas.size)


if __name__ == "__main__":
    for name, pattern in LAYERS.items():
        build(name, pattern)
    sys.exit(0)
