// "How we know" panel (F5): the method in plain words and the real validation numbers.

function esc(s) { const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; }
const pct = (x) => `${(x * 100).toFixed(1)}%`;
const sign = (x) => (x > 0 ? '+' : '') + x.toFixed(2);

/** Horizontal rate chart with 95% whiskers, drawn to one scale. */
function rateChart(rows) {
  const W = 340, rowH = 30, L = 150, R = 14, top = 8;
  const lo = Math.min(-0.3, ...rows.map((r) => r.ci_low)), hi = Math.max(0.6, ...rows.map((r) => r.ci_high));
  const X = (v) => L + ((v - lo) / (hi - lo)) * (W - L - R);
  const H = top + rows.length * rowH + 22;
  // A tick step that leaves room for the labels, whatever the widest range is.
  const step = hi - lo > 2 ? 1 : hi - lo > 1 ? 0.5 : 0.25;
  const ticks = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) ticks.push(Math.round(t * 100) / 100);
  const bars = rows.map((r, i) => {
    const y = top + i * rowH + rowH / 2;
    const color = r.ref ? '#6fd3ff' : r.per_decade >= 0 ? '#e0605a' : '#5b8fd6';
    return `<text x="${L - 8}" y="${y + 4}" text-anchor="end" fill="#c9d4e4" font-size="11">${esc(r.short)}</text>
      <line x1="${X(r.ci_low)}" y1="${y}" x2="${X(r.ci_high)}" y2="${y}" stroke="${color}" stroke-width="2" opacity=".55"/>
      <line x1="${X(r.ci_low)}" y1="${y - 5}" x2="${X(r.ci_low)}" y2="${y + 5}" stroke="${color}" stroke-width="2" opacity=".55"/>
      <line x1="${X(r.ci_high)}" y1="${y - 5}" x2="${X(r.ci_high)}" y2="${y + 5}" stroke="${color}" stroke-width="2" opacity=".55"/>
      <circle cx="${X(r.per_decade)}" cy="${y}" r="5" fill="${color}"/>
      <text x="${X(r.per_decade)}" y="${y - 9}" text-anchor="middle" fill="#eaf0f8" font-size="10.5">${sign(r.per_decade)}</text>`;
  }).join('');
  const axis = ticks.map((t) => `<line x1="${X(t)}" y1="${top}" x2="${X(t)}" y2="${H - 20}" stroke="rgba(255,255,255,${t === 0 ? 0.3 : 0.08})"/>
      <text x="${X(t)}" y="${H - 6}" text-anchor="middle" fill="#9aabc2" font-size="10">${sign(t)}</text>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Warming rates per decade with 95% ranges">${axis}${bars}</svg>
    <p class="note" style="text-align:center">°C per decade, 2001 to 2025. Dot = best estimate, line = 95% range.</p>`;
}

/** One bar split into parts that share a total, with labels. */
function splitBar(parts, total) {
  return `<div style="display:flex;height:14px;border-radius:7px;overflow:hidden;background:rgba(255,255,255,.06);margin:8px 0 4px">
    ${parts.map((p) => `<span title="${esc(p.label)}" style="width:${(100 * p.n) / total}%;background:${p.color}"></span>`).join('')}</div>
    <div class="note" style="display:flex;flex-wrap:wrap;gap:4px 14px">${parts.map((p) => `<span><i class="sw" style="background:${p.color}"></i>${esc(p.label)}</span>`).join('')}</div>`;
}

/** Check 5 (python run.py nasa-check): our trends against NASA's station (GISTEMP) and rain (GPCP) records. */
function nasaRecordsHTML(n) {
  if (!n || !n.egypt_temperature) return '';
  const t = n.egypt_temperature, w = n.world_temperature, r = n.egypt_rain && n.egypt_rain.egypt;
  const tile = (label, value, sub) => `<div style="flex:1;min-width:120px;background:rgba(255,255,255,.05);border-radius:8px;padding:8px 10px">
      <div class="note">${esc(label)}</div><div style="font-size:18px;font-weight:700">${value}</div><div class="note">${esc(sub)}</div></div>`;
  const row = (items) => `<div style="display:flex;flex-wrap:wrap;gap:8px;margin:8px 0">${items.join('')}</div>`;
  const plus = (x) => `${x > 0 ? '+' : ''}${x.toFixed(2)}`;
  return `<h3>Check 5: ${esc(n.title)}</h3>
    <p class="note"><strong>Temperature over Egypt, ${n.period[0]} to ${n.period[1]}, °C per decade</strong></p>
    ${row([tile('NASA GISTEMP (weather stations)', plus(t.gistemp_per_decade), `proven in ${t.gistemp_proven} of ${t.boxes} areas`),
           tile('NASA POWER (our data)', plus(t.power_per_decade), `proven in ${t.power_proven} of ${t.boxes} areas`)])}
    <p class="note">${esc(n.plain_temperature)}</p>
    ${w ? `<p class="note">Whole world, ${w.boxes.toLocaleString('en-US')} areas with stations: same direction in ${Math.round(100 * w.same_direction_share)}% of the area, never proven in opposite directions (${w.opposite_proven} areas). Average ${plus(w.gistemp_mean_per_decade)} (stations) vs ${plus(w.power_mean_per_decade)} (POWER).</p>` : ''}
    ${r ? `<p class="note"><strong>Rain over Egypt, mm per year, 2001 to 2014 vs 2016 to 2025</strong></p>
    ${row([tile('NASA POWER (our data)', `x${r.power_jump.toFixed(1)}`, `${Math.round(r.power_before)} to ${Math.round(r.power_after)} mm`),
           tile('GPCP (satellites and gauges)', `x${r.gpcp_jump.toFixed(2)}`, `${Math.round(r.gpcp_before)} to ${Math.round(r.gpcp_after)} mm`)])}
    <div class="callout info">${esc(n.plain_rain)}</div>` : ''}`;
}

/** Check 6 (only after python run.py crosscheck): the same numbers from NASA Giovanni, a challenge resource. */
function giovanniHTML(g) {
  if (!g || !g.rows || !g.rows.length) return '';
  const unit = (r) => (r.kind === 'rain' ? 'mm/day' : '°C');
  const rate = (d, r) => (d.per_decade === null ? 'n/a' : `${d.per_decade > 0 ? '+' : ''}${d.per_decade.toPrecision(2)} ${unit(r)}`);
  const jump = (d, r) => (r.kind === 'rain' && d.jump_ratio ? ` · x${d.jump_ratio.toFixed(1)} after 2015` : '');
  const rows = g.rows.map((r) => `<tr><td>${esc(r.area_label)}</td><td>${esc(r.source_label.replace(' (Giovanni)', ''))}</td>
      <td>${rate(r.giovanni, r)}${jump(r.giovanni, r)}<br><span class="note">${esc(r.giovanni.level_name)}</span></td>
      <td>${rate(r.ours, r)}${jump(r.ours, r)}<br><span class="note">${esc(r.ours.level_name)}</span></td></tr>`).join('');
  return `<h3>Check 6: ${esc(g.title)}</h3>
    <table class="crop-table"><thead><tr><th>Area</th><th>Giovanni record</th><th>Giovanni, per decade</th><th>Ours (POWER)</th></tr></thead>
      <tbody>${rows}</tbody></table>
    <p class="note">${esc(g.plain)}</p>
    ${g.rain_verdict ? `<div class="callout info">${esc(g.rain_verdict)}</div>` : ''}`;
}

export function methodsHTML(v) {
  const c = v.checks;
  const x = c.cross_check, fa = c.false_alarms, mp = c.many_places, fm = c.farming;
  const rows = [
    { short: 'NASA GISTEMP', ref: true, ...x.reference },
    { short: 'Our data, whole Earth', ...x.ours },
    { short: 'Ours, without Antarctica', ...x.ours_no_antarctica },
    { short: 'Ours, Arctic only', ...x.arctic },
    { short: 'Ours, Antarctica only', ...x.antarctica },
  ];
  const faRate = fa.false_alarm_rate['Egypt-like noise'];
  const faStrong = fa.false_alarm_rate['strong year-to-year resemblance (0.5)'];
  const names = { plain_mk: 'Plain Mann-Kendall', hamed_rao_mk: 'Mann-Kendall, Hamed-Rao', prewhitened_mk: 'Mann-Kendall, pre-whitening',
    tfpw_mk: 'Mann-Kendall, trend-free pre-whitening', linear_t_test: 'Straight line + t-test (in use now)' };
  const d1 = fa.d1_candidates ? `<details><summary>All methods compared for decision D1</summary>
      <table class="crop-table"><thead><tr><th>Method</th><th>False alarms</th><th>Strong resemblance</th><th>Finds +0.2/decade</th></tr></thead><tbody>
      ${Object.entries(fa.d1_candidates).map(([k, r]) => `<tr><td>${esc(names[k] || k)}</td><td>${pct(r.false_alarm)}</td><td>${pct(r.false_alarm_strong)}</td><td>${pct(r.finds_0_2_per_decade)}</td></tr>`).join('')}
      </tbody></table></details>` : '';
  return `
    <h2>How we know</h2>
    <div class="where">The method in plain words, and the checks we ran on our own numbers.</div>

    <h3>What we do</h3>
    <ol class="steps">
      <li><strong>Collect.</strong> NASA POWER monthly climate (built on NASA's MERRA-2) for every 55 km grid cell on Earth, 2001 to 2025.</li>
      <li><strong>Remove the seasons.</strong> Average each year's 12 months, so summer and winter cannot look like a trend.</li>
      <li><strong>Measure.</strong> Sen's slope: the median of the slopes between every pair of years, so one extreme year cannot drag it. Reported per 10 years, with a 95% range.</li>
      <li><strong>Test.</strong> Mann-Kendall test: do later years beat earlier years more often than chance? Corrected for year-to-year resemblance (a wet year often follows a wet year). Gives the p-value: how likely a trend this strong would be if nothing were changing.</li>
      <li><strong>When.</strong> Pettitt test finds the year a proven change seems to start.</li>
      <li><strong>Correct for many places.</strong> Testing thousands of cells at once creates lucky "trends", so we raise the bar (false discovery rate, q-value).</li>
      <li><strong>Label honestly.</strong> Strong evidence, moderate evidence, or not proven. Never "no change", never "87% true".</li>
    </ol>

    <h3>Check 1: ${esc(x.title)}</h3>
    ${rateChart(rows)}
    <p class="note">${esc(x.plain)}</p>

    <h3>Check 2: ${esc(fa.title)}</h3>
    ${splitBar([{ n: faRate, color: '#2fbf71', label: `Our engine on Egypt-like noise: ${pct(faRate)}` }, { n: Math.max(0, 0.05 - faRate), color: 'rgba(255,255,255,.18)', label: 'Target: about 5%' }], 0.25)}
    ${splitBar([{ n: Math.min(faStrong, 0.25), color: faStrong <= 0.075 ? '#2fbf71' : '#e0b23a', label: `With strong year-to-year resemblance: ${pct(faStrong)}` }], 0.25)}
    <p class="note">${esc(fa.plain)}</p>
    ${d1}

    <h3>Check 3: ${esc(mp.title)}</h3>
    ${splitBar([
      { n: mp.q_below_0_05, color: '#2fbf71', label: `Proven after correction: ${mp.q_below_0_05}` },
      { n: mp.p_below_0_05 - mp.q_below_0_05, color: '#e0b23a', label: `Looked significant, removed: ${mp.p_below_0_05 - mp.q_below_0_05}` },
      { n: mp.cells - mp.p_below_0_05, color: '#7d838c', label: `Not significant: ${mp.cells - mp.p_below_0_05}` }], mp.cells)}
    <p class="note">${esc(mp.plain)}</p>

    <h3>Check 4: ${esc(fm.title)}</h3>
    <ul class="checks">${fm.checks.map((k) => `<li><span class="${k.passed ? 'ok' : 'bad'}">${k.passed ? '✓' : '✗'}</span> ${esc(k.check)} <span class="note">(${esc(k.detail)})</span></li>`).join('')}</ul>

    ${nasaRecordsHTML(c.nasa_records)}

    ${giovanniHTML(c.giovanni)}

    <h3>Limits we are honest about</h3>
    <ul class="limits">${v.limitations.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>

    <h3>Data</h3>
    <p class="note">NASA POWER (MERRA-2) · NASA GISTEMP v4${c.nasa_records ? ' (global and 250 km station grid) · GPCP v2.3 rain' : ''}${c.giovanni ? ' · NASA Giovanni (MERRA-2, GPM IMERG)' : ''} · NASA GIBS imagery (Blue Marble, VIIRS) · IFPRI MapSPAM 2020 crop maps
      (crop model training) · FAOSTAT (crop model check) · Natural Earth borders. Analysis code is open in our repository.</p>
    <p class="note">This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no responsibility
      for the analyses or interpretations of the data presented here.</p>`;
}
