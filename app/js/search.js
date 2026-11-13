// Search box: countries (Natural Earth borders) and about 1,250 cities, all offline.

export function setupSearch({ input, list, countries, places, onPick }) {
  const items = [
    ...countries.features.map((f) => ({ kind: 'country', name: f.properties.name, iso: f.properties.iso, bbox: f.properties.bbox, sub: 'Country' })),
    ...places.places.map(([name, country, lat, lon, pop]) => ({ kind: 'city', name, country, lat, lon, pop, sub: country })),
  ];
  let results = [];
  let active = -1;

  function close() { list.hidden = true; input.setAttribute('aria-expanded', 'false'); active = -1; }

  function render() {
    list.innerHTML = '';
    results.forEach((r, i) => {
      const li = document.createElement('li');
      li.id = `opt-${i}`;
      li.setAttribute('role', 'option');
      li.setAttribute('aria-selected', String(i === active));
      li.innerHTML = `<span></span><span class="kind"></span>`;
      li.firstChild.textContent = r.name;
      li.lastChild.textContent = r.sub;
      li.addEventListener('mousedown', (e) => { e.preventDefault(); pick(i); });
      list.appendChild(li);
    });
    list.hidden = results.length === 0;
    input.setAttribute('aria-expanded', String(!list.hidden));
    input.setAttribute('aria-activedescendant', active >= 0 ? `opt-${active}` : '');
  }

  function search(q) {
    q = q.trim().toLowerCase();
    if (q.length < 2) { results = []; return render(); }
    const scored = [];
    for (const it of items) {
      const n = it.name.toLowerCase();
      const idx = n.indexOf(q);
      if (idx < 0) continue;
      const score = (idx === 0 ? 0 : 10) + (it.kind === 'country' ? 0 : 1) - (it.pop ? Math.log10(it.pop + 1) / 10 : 0);
      scored.push([score, it]);
    }
    scored.sort((a, b) => a[0] - b[0]);
    results = scored.slice(0, 8).map((s) => s[1]);
    active = results.length ? 0 : -1;
    render();
  }

  function pick(i) {
    const r = results[i];
    if (!r) return;
    input.value = r.kind === 'city' ? `${r.name}, ${r.country}` : r.name;
    close();
    onPick(r);
  }

  input.addEventListener('input', () => search(input.value));
  input.addEventListener('keydown', (e) => {
    if (list.hidden) return;
    if (e.key === 'ArrowDown') { active = Math.min(results.length - 1, active + 1); render(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { active = Math.max(0, active - 1); render(); e.preventDefault(); }
    else if (e.key === 'Enter') { pick(active); e.preventDefault(); }
    else if (e.key === 'Escape') close();
  });
  input.addEventListener('blur', () => setTimeout(close, 100));
}
