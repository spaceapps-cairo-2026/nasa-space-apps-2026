"""Focus countries of the farming tabs (decision D7): the Middle East and North Africa, plus Sudan and Mauritania.

One list for the crop outlook (ml/crop_outlook.py, `python run.py crop-model <ISO>` or `all`) and the API
(/api/farming, /api/farming/countries). Names follow the app's map data (app/data/borders_50m.geojson), where the
country is named Palestine only (scripts/palestine_borders.js). Bahrain is not in that map data (smaller than its
detail level), so it has no outline and no outlook.
"""
COUNTRIES = {
    "EGY": "Egypt", "SAU": "Saudi Arabia",
    "MAR": "Morocco", "DZA": "Algeria", "TUN": "Tunisia", "LBY": "Libya", "SDN": "Sudan", "MRT": "Mauritania",
    "DJI": "Djibouti", "PSE": "Palestine", "JOR": "Jordan", "LBN": "Lebanon", "SYR": "Syria", "IRQ": "Iraq",
    "IRN": "Iran", "KWT": "Kuwait", "QAT": "Qatar", "ARE": "United Arab Emirates", "OMN": "Oman", "YEM": "Yemen",
}
