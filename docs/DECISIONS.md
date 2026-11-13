# Decisions (lane A keeps this current)

One line per decision: `time | decision | why | who`

- Fri | Contract-first, mock-first architecture with 3 lanes | lets 3 Claude accounts work in parallel without waiting on each other | team
- Fri | Plain HTML + Leaflet + Plotly frontend, FastAPI backend | no build step, nothing to debug at 3 AM | team
- Fri | PROJECT_PLAN.md (farming trend explorer, F0 to F6) replaces the earlier MODIS fingerprint concept; algorithms decided during the hackathon (D1 to D9) | plan agreed by the team | team
- Fri | The "Leaflet" frontend choice above is reopened by D3 (globe and map library) | the plan needs a 3D globe | team
- Fri | Trends (F1) cover the whole world as maps; farming features (F2 to F4) only for focus countries | the challenge is about Earth, and crops need per country care | Mohammed
- Fri | World trends use live fetch per region with a disk cache; the 4 hour bulk world download is optional | nobody waits for a download; demo regions are fetched beforehand | Mohammed
