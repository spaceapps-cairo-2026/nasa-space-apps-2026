"""Lane C: crop climate requirements from FAO ECOCROP, for F3 crops (and F2, F4). Task C3.

ECOCROP is the UN FAO database of what each plant needs to grow: an OPTIMAL range (grows
best) and an ABSOLUTE range (survives at all) for temperature and yearly rainfall.

Source of the numbers: the full ECOCROP export (2,568 plants) published by the OpenCLIM
project (github.com/OpenCLIM/ecocrop). Spot checked against FAO's own data sheets
(date palm, wheat): identical. Every row links to its FAO data sheet.

Output: data/crops/crops.csv            (one row per crop, the table the engine uses)
Raw:    data/cache/ecocrop/EcoCrop_DB.csv (full database, committed to git)

Run:  python run.py crops           (uses the committed raw file)
      python run.py crops --force   (re-download first)

To add a crop: add a line to CROPS (scientific name exactly as in EcoCrop_DB.csv), rerun.
"""
from __future__ import annotations

import csv
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://raw.githubusercontent.com/OpenCLIM/ecocrop/main/EcoCrop_DB.csv"
RAW = ROOT / "data" / "cache" / "ecocrop" / "EcoCrop_DB.csv"
OUT = ROOT / "data" / "crops" / "crops.csv"
SHEET = "https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id={id}"

# (common name, scientific name in ECOCROP, group)
# group "plan" = the 13 candidates in PROJECT_PLAN.md F3; "egypt" = extra major Egyptian crops.
# The final 8 to 12 are chosen in decision D6.
CROPS = [
    ("wheat", "Triticum aestivum", "plan"),
    ("maize", "Zea mays", "plan"),
    ("rice", "Oryza sativa", "plan"),
    ("cotton", "Gossypium hirsutum", "plan"),
    ("potato", "Solanum tuberosum", "plan"),
    ("tomato", "Lycopersicon esculentum", "plan"),
    ("orange (citrus)", "Citrus sinensis", "plan"),
    ("mango", "Mangifera indica", "plan"),
    ("date palm", "Phoenix dactylifera", "plan"),
    ("olive", "Olea europaea", "plan"),
    ("grape", "Vitis vinifera", "plan"),
    ("avocado", "Persea americana", "plan"),
    ("apple", "Malus domestica", "plan"),
    ("sugarcane", "Saccharum officinarum", "egypt"),
    ("sugar beet", "Beta vulgaris", "egypt"),
    ("onion", "Allium cepa", "egypt"),
    ("faba bean", "Vicia faba", "egypt"),
    ("berseem clover", "Trifolium alexandrinum", "egypt"),
    ("barley", "Hordeum vulgare", "egypt"),
    ("sorghum", "Sorghum bicolor", "egypt"),
]

# output column -> ECOCROP column
FIELDS = {
    "temp_opt_min_c": "TOPMN", "temp_opt_max_c": "TOPMX",
    "temp_abs_min_c": "TMIN", "temp_abs_max_c": "TMAX",
    "rain_opt_min_mm": "ROPMN", "rain_opt_max_mm": "ROPMX",
    "rain_abs_min_mm": "RMIN", "rain_abs_max_mm": "RMAX",
    "killing_temp_c": "KTMP",
    "cycle_min_days": "GMIN", "cycle_max_days": "GMAX",
    "life_span": "LISPA",
    "salinity_opt": "SAL", "salinity_abs": "SALR",
}


def download() -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=90) as r:
        RAW.write_bytes(r.read())
    print(f"downloaded {URL}")


def clean(col: str, value: str) -> str:
    value = (value or "").strip()
    if value.upper() in ("NA", "NAN"):
        return ""
    if col in ("GMIN", "GMAX") and value in ("0", "0.0"):
        return ""  # 0 days means "not recorded" in ECOCROP
    if value.endswith(".0"):
        value = value[:-2]
    return value


def main() -> None:
    if "--force" in sys.argv or not RAW.exists():
        download()
    with RAW.open(encoding="latin-1", newline="") as f:
        db = {row["ScientificName"].strip().lower(): row for row in csv.DictReader(f)}

    out_rows, missing = [], []
    for name, sci, group in CROPS:
        row = db.get(sci.lower())
        if row is None:
            missing.append(sci)
            continue
        out = {"crop": name, "scientific_name": sci, "group": group}
        out.update({k: clean(v, row.get(v, "")) for k, v in FIELDS.items()})
        out["source_url"] = SHEET.format(id=row["EcoPortCode"])
        out_rows.append(out)
    if missing:
        raise SystemExit(f"not found in ECOCROP: {missing}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {OUT}: {len(out_rows)} crops "
          f"({sum(r['group'] == 'plan' for r in out_rows)} plan candidates, "
          f"{sum(r['group'] == 'egypt' for r in out_rows)} extra Egyptian crops)")


if __name__ == "__main__":
    main()
