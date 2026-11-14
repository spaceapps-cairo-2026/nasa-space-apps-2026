"""Cross-check our NASA POWER numbers against NASA Giovanni (a challenge resource). Lane A.

Two questions, answered with files downloaded by hand from https://giovanni.gsfc.nasa.gov (needs a free
NASA Earthdata login, so the files are not in git; steps in docs/CROSSCHECK.md):

1. Temperature: does NASA's own tool give the same series and the same trend as our engine on POWER?
   POWER is built on MERRA-2, so MERRA-2 T2M from Giovanni should match closely.
2. Rain: the POWER rain record jumps around 2015 (Egypt about 3 times higher after 2015). Is that in
   - GPM IMERG (satellite rain, independent of MERRA-2)? If not, the jump is not real rain.
   - MERRA-2 PRECTOTCORR (the record POWER rain comes from)? If yes, POWER inherits it from MERRA-2.

Files go in data/raw/giovanni/ and are named <area>_<source>.csv:
    area:   cairo  (the POWER cell around Cairo)   or   egypt  (Giovanni country shape "Egypt")
    source: merra2_t2m   merra2_rain   imerg_rain
Any subset works; missing files are skipped.

Run:  python run.py crosscheck   -> ml/outputs/crosscheck.json, then python ml/validate.py adds it to the
Methods page as Check 5.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
import live  # noqa: E402
import trends as T  # noqa: E402

FOLDER = ROOT / "data" / "raw" / "giovanni"
OUT = ROOT / "ml" / "outputs" / "crosscheck.json"
YEARS = list(range(T.START_YEAR, T.END_YEAR + 1))
JUMP_YEAR = 2015                     # before: 2001 to 2014, after: 2016 to 2025

AREAS = {
    "cairo": {"label": "Cairo (one grid cell)", "point": (30.0, 31.25)},
    "egypt": {"label": "Egypt (whole country)", "country": "EGY", "box": (22.0, 31.586, 24.7, 36.866)},
}
SOURCES = {
    "merra2_t2m": {"label": "MERRA-2 air temperature (Giovanni)", "power": "T2M", "kind": "temperature"},
    "merra2_rain": {"label": "MERRA-2 corrected rain (Giovanni)", "power": "PRECTOTCORR", "kind": "rain"},
    "imerg_rain": {"label": "GPM IMERG satellite rain (Giovanni)", "power": "PRECTOTCORR", "kind": "rain"},
}


# ---------- reading Giovanni files ----------

_DATE = re.compile(r"^\s*(\d{4})-(\d{2})")


def read_giovanni_csv(path: Path) -> dict[str, float]:
    """Monthly values {"YYYY-MM": value} from a Giovanni area-averaged time series CSV.

    Giovanni puts a few metadata lines first (title, dates, fill value) and then one row per month:
    a date and the area average. Column names differ per variable, so rows are found by their date.
    """
    fill = None
    out: dict[str, float] = {}
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.reader(f):
            if not row:
                continue
            head = row[0].strip().lower()
            if "fill" in head and len(row) > 1:
                try:
                    fill = float(row[-1])
                except ValueError:
                    pass
                continue
            m = _DATE.match(row[0])
            if not m or len(row) < 2:
                continue
            try:
                v = float(row[1])
            except ValueError:
                continue
            if not np.isfinite(v) or (fill is not None and np.isclose(v, fill)) or v <= -9000 or abs(v) >= 1e14:
                continue
            out[f"{m.group(1)}-{m.group(2)}"] = v
    if not out:
        raise ValueError(f"{path.name}: no monthly rows found. Download the CSV of an area-averaged time series.")
    return out


def to_units(source: str, monthly: dict[str, float]) -> dict[str, float]:
    """Giovanni units -> the units of our POWER data (°C, mm per day)."""
    vals = np.array(list(monthly.values()))
    if source == "merra2_t2m":
        k = 273.15 if np.nanmedian(vals) > 150 else 0.0              # Kelvin -> °C
        return {t: v - k for t, v in monthly.items()}
    if source == "merra2_rain":
        f = 86400.0 if np.nanmax(np.abs(vals)) < 0.01 else 1.0       # kg m-2 s-1 -> mm per day
        return {t: v * f for t, v in monthly.items()}
    if source == "imerg_rain":
        return {t: v * 24.0 for t, v in monthly.items()}             # IMERG monthly is mm per hour
    raise ValueError(source)


def monthly_array(monthly: dict[str, float]) -> np.ndarray:
    return np.array([monthly.get(f"{y}-{m:02d}", np.nan) for y in YEARS for m in range(1, 13)], dtype=float)


# ---------- our POWER data for the same area ----------

def power_monthly(area: str, var: str) -> np.ndarray:
    a = AREAS[area]
    if "point" in a:
        return np.asarray(live.point_data(var, *a["point"])["values"], dtype=float)
    d = live.region_data(var, *a["box"])
    _, mask = live._country_mask(a["country"], d["lats"], d["lons"])
    v = np.where(mask[:, :, None], np.asarray(d["values"], dtype=float), np.nan)
    w = np.cos(np.radians(d["lats"]))[:, None, None] * np.isfinite(v)   # same weighting as Giovanni
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.nansum(np.nan_to_num(v) * w, axis=(0, 1)) / w.sum(axis=(0, 1))


# ---------- comparing ----------

def describe(annual: np.ndarray) -> dict:
    """Our engine on one yearly series, plus the 2015 jump (after / before)."""
    r = T.trend_one(annual)
    level = int(T.confidence_levels(np.array([np.nan if r["p"] is None else r["p"]]))[0])
    before = np.nanmean(annual[: JUMP_YEAR - T.START_YEAR])
    after = np.nanmean(annual[JUMP_YEAR - T.START_YEAR + 1:])
    cp = T.change_point(annual, YEARS)
    rnd = lambda v, nd=4: None if v is None or not np.isfinite(v) else round(float(v), nd)  # noqa: E731
    return {
        "per_decade": rnd(r["slope"]), "ci_low": rnd(r["slope_lo"]), "ci_high": rnd(r["slope_hi"]),
        "p": rnd(r["p"], 5), "level": level, "level_name": "no data" if level < 0 else T.LEVEL_NAMES[level],
        "mean_before": rnd(before), "mean_after": rnd(after),
        "jump_ratio": rnd(after / before, 3) if before and np.isfinite(before) and before > 0 else None,
        "change_year": cp["year"] if cp else None,
        "annual": [rnd(v) for v in annual],
    }


def compare(area: str, source: str, path: Path) -> dict:
    s = SOURCES[source]
    theirs = T.annual_means(monthly_array(to_units(source, read_giovanni_csv(path))))
    ours = T.annual_means(power_monthly(area, s["power"]))
    ok = np.isfinite(theirs) & np.isfinite(ours)
    corr = float(np.corrcoef(ours[ok], theirs[ok])[0, 1]) if ok.sum() >= 5 else None
    return {
        "area": area, "area_label": AREAS[area]["label"], "source": source, "source_label": s["label"],
        "kind": s["kind"], "years_compared": int(ok.sum()),
        "ours": describe(ours), "giovanni": describe(theirs),
        "year_to_year_correlation": None if corr is None else round(corr, 3),
        "mean_difference": round(float(np.mean(ours[ok] - theirs[ok])), 4) if ok.any() else None,
    }


def _rate(d: dict, unit: str) -> str:
    return f"{d['per_decade']:+.3g} {unit} per decade ({d['level_name']})"


def summary(rows: list[dict]) -> str:
    """Plain sentences built only from the numbers, for the Methods page."""
    by = {(r["area"], r["source"]): r for r in rows}
    out = []
    for area in AREAS:
        t = by.get((area, "merra2_t2m"))
        if t:
            out.append(f"{AREAS[area]['label']}: NASA Giovanni's MERRA-2 air temperature gives {_rate(t['giovanni'], '°C')}, "
                       f"our engine on POWER gives {_rate(t['ours'], '°C')}; the yearly values move together "
                       f"(correlation {t['year_to_year_correlation']:.2f}).")
        ours = (by.get((area, "imerg_rain")) or by.get((area, "merra2_rain")) or {}).get("ours")
        im, mr = by.get((area, "imerg_rain")), by.get((area, "merra2_rain"))
        if ours and ours["jump_ratio"]:
            parts = [f"{AREAS[area]['label']}: after 2015, POWER rain is {ours['jump_ratio']:.1f} times its 2001 to 2014 level"]
            if im and im["giovanni"]["jump_ratio"]:
                parts.append(f"GPM IMERG satellite rain {im['giovanni']['jump_ratio']:.1f} times")
            if mr and mr["giovanni"]["jump_ratio"]:
                parts.append(f"MERRA-2 corrected rain {mr['giovanni']['jump_ratio']:.1f} times")
            out.append(", ".join(parts) + ".")
    return " ".join(out)


def verdict(rows: list[dict]) -> str | None:
    """Where the rain jump comes from, only when the numbers say so clearly."""
    for area in AREAS:
        im = next((r for r in rows if r["area"] == area and r["source"] == "imerg_rain"), None)
        mr = next((r for r in rows if r["area"] == area and r["source"] == "merra2_rain"), None)
        if not im or not im["ours"]["jump_ratio"] or not im["giovanni"]["jump_ratio"]:
            continue
        ours, sat = im["ours"]["jump_ratio"], im["giovanni"]["jump_ratio"]
        if ours >= 1.5 and sat < 1.25:
            src = (" MERRA-2 shows the same jump, so POWER inherits it from MERRA-2."
                   if mr and mr["giovanni"]["jump_ratio"] and mr["giovanni"]["jump_ratio"] >= 1.5 else "")
            return (f"The satellite record does not show the 2015 rain jump ({AREAS[area]['label'].split(' (')[0]}: "
                    f"{sat:.1f} times vs {ours:.1f} in POWER), so the jump is in the data, not in real rain.{src}")
        if ours >= 1.5 and sat >= 1.5:
            return (f"The satellite record shows a similar rise ({sat:.1f} times vs {ours:.1f} in POWER), "
                    "so the 2015 rain jump may be real.")
    return None


def run() -> dict:
    rows = []
    found = sorted(FOLDER.glob("*.csv")) if FOLDER.exists() else []
    for path in found:
        name = path.stem.lower()
        area = next((a for a in AREAS if name.startswith(a + "_")), None)
        source = name[len(area) + 1:] if area else None
        if source not in SOURCES:
            print(f"skip {path.name}: name it <area>_<source>.csv, area in {list(AREAS)}, source in {list(SOURCES)}")
            continue
        rows.append(compare(area, source, path))
    return {"title": "Same answer in NASA Giovanni", "period": [T.START_YEAR, T.END_YEAR],
            "rows": rows, "plain": summary(rows), "rain_verdict": verdict(rows)}


def main() -> int:
    res = run()
    if not res["rows"]:
        print(f"No Giovanni files in {FOLDER}. Steps: docs/CROSSCHECK.md")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for r in res["rows"]:
        o, g = r["ours"], r["giovanni"]
        print(f"{r['area']:6s} {r['source']:12s} ours {o['per_decade']:+.4f}/dec ({o['level_name']}, jump x{o['jump_ratio']}) | "
              f"Giovanni {g['per_decade']:+.4f}/dec ({g['level_name']}, jump x{g['jump_ratio']}) | "
              f"r = {r['year_to_year_correlation']}, {r['years_compared']} years")
    print("\n" + res["plain"])
    if res["rain_verdict"]:
        print(res["rain_verdict"])
    print(f"\nSaved {OUT.relative_to(ROOT)}. Run python ml/validate.py to show it on the Methods page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
