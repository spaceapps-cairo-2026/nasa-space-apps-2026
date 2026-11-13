"""Lane C: NASA GISTEMP v4 global mean temperature, for validation (F5, task C5).

GISTEMP is NASA GISS's official global surface temperature record (land + ocean).
Values are anomalies: degrees C above or below the 1951 to 1980 average.

Output: data/processed/gistemp_global_annual.csv   columns: year, anomaly_c
Raw:    data/cache/gistemp/GLB.Ts+dSST.csv          (exact NASA file, committed to git)

Run:  python run.py gistemp           (uses the committed raw file)
      python run.py gistemp --force   (re-download from NASA first)
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
RAW = ROOT / "data" / "cache" / "gistemp" / "GLB.Ts+dSST.csv"
OUT = ROOT / "data" / "processed" / "gistemp_global_annual.csv"


def download() -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    # NASA GISS stalls on Python's default User-Agent, so send a normal one.
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        RAW.write_bytes(r.read())
    print(f"downloaded {URL}")


def annual_rows(text: str) -> list[tuple[int, float]]:
    """Keep complete years only: the J-D (January to December) column, '***' means not complete yet."""
    lines = text.splitlines()
    header = lines[1].split(",")
    jd = header.index("J-D")
    rows = []
    for line in lines[2:]:
        cells = line.split(",")
        if cells[0].isdigit() and cells[jd] != "***":
            rows.append((int(cells[0]), float(cells[jd])))
    return rows


def sen_slope_per_decade(rows: list[tuple[int, float]], start: int, end: int) -> float:
    """Median of all pairwise slopes (Sen's slope), times 10. A quick check, not the team's engine."""
    pts = [(y, v) for y, v in rows if start <= y <= end]
    slopes = sorted((v2 - v1) / (y2 - y1) for i, (y1, v1) in enumerate(pts) for y2, v2 in pts[i + 1:])
    n = len(slopes)
    mid = slopes[n // 2] if n % 2 else (slopes[n // 2 - 1] + slopes[n // 2]) / 2
    return mid * 10


def main() -> None:
    if "--force" in sys.argv or not RAW.exists():
        download()
    rows = annual_rows(RAW.read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("year,anomaly_c\n" + "".join(f"{y},{v:.2f}\n" for y, v in rows), encoding="utf-8")
    print(f"wrote {OUT}: {len(rows)} years, {rows[0][0]} to {rows[-1][0]}")
    print(f"check: Sen slope 2003 to 2025 = {sen_slope_per_decade(rows, 2003, 2025):+.3f} C per decade")


if __name__ == "__main__":
    main()
