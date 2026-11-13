// Guided tour (F6): one button plays the story end to end, with captions large enough for a video.
// Every caption that states a number takes it from the live answer, never from a hard-coded value.

const STOP = Symbol('stop');

export function createTour(ctx) {
  let token = 0;
  const el = document.createElement('div');
  el.id = 'tour';
  el.className = 'glass';
  el.hidden = true;
  el.setAttribute('role', 'status');
  el.innerHTML = `<div class="tour-top"><span class="tour-step"></span><button class="btn" id="tour-stop">Stop tour</button></div>
    <p class="tour-text"></p><div class="tour-dots"></div>`;
  document.body.appendChild(el);
  el.querySelector('#tour-stop').onclick = () => stop();
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !el.hidden) stop(); });

  const steps = [
    {
      run: async () => { await ctx.reset(); ctx.home(); },
      text: () => 'Since 2001, NASA has measured every place on Earth, every month. Colored = warming or cooling that is statistically proven. Clear = not proven.',
      dwell: 6500,
    },
    {
      run: async () => ctx.selectCountry('EGY'),
      text: (c) => (c ? `Egypt: ${c.increasing} places are proven to be warming. Grey tiles are not proven: normal ups and downs could explain them.`
        : 'Egypt, cell by cell: raised columns are proven changes, grey tiles are not proven.'),
      dwell: 7000,
    },
    {
      run: async () => ctx.selectPoint(24.09, 32.9),
      text: () => 'Click any place: 25 years of NASA data, how fast it changes per decade, and how strong the evidence is.',
      dwell: 7000,
    },
    {
      run: async () => ctx.selectCountry('KEN'),
      text: (c) => (c ? `Any country, live from NASA. Kenya: ${c.increasing} places warming, ${c.decreasing} cooling. One planet, opposite trends.`
        : 'Any country, live from NASA: the same test, everywhere on Earth.'),
      dwell: 7000,
    },
    {
      run: async () => { await ctx.setTab('crops'); ctx.setCrop('apple', 'score'); },
      text: () => 'What does it mean for food? Apples fit Egypt\'s cooler north, but the south is already too hot for them.',
      dwell: 6500,
    },
    {
      run: async () => ctx.setCrop('apple', 'heat'),
      text: () => 'Years until each crop reaches its heat limit, if the measured warming continues. Taller and redder = sooner.',
      dwell: 6500,
    },
    {
      run: async () => ctx.setTab('decisions'),
      text: () => 'Planning signals for farmers and governments: where potential is rising or falling, each with its evidence level.',
      dwell: 7000,
    },
    {
      run: async () => { await ctx.setTab('trends'); await ctx.reset(); return ctx.showMethods(); },
      text: (v) => (v ? `And we test ourselves: our engine raises false alarms only ${(v.checks.false_alarms.false_alarm_rate['Egypt-like noise'] * 100).toFixed(1)}% of the time, and our world trend agrees with NASA's independent GISTEMP record.`
        : 'And we test ourselves against NASA\'s independent records.'),
      dwell: 8000,
    },
    {
      run: async () => { ctx.closePanel(); ctx.home(); },
      text: () => 'CropShift Earth: NASA data, honest statistics. Now explore any place yourself.',
      dwell: 4500,
    },
  ];

  const wait = (ms, t) => new Promise((r) => setTimeout(r, ms)).then(() => { if (t !== token) throw STOP; });

  function caption(i, text) {
    el.querySelector('.tour-step').textContent = `Tour ${i + 1} of ${steps.length}`;
    el.querySelector('.tour-text').textContent = text;
    el.querySelector('.tour-dots').innerHTML = steps.map((_, k) => `<i class="${k <= i ? 'on' : ''}"></i>`).join('');
  }

  async function start() {
    const t = ++token;
    el.hidden = false;
    document.body.classList.add('touring');
    try {
      for (let i = 0; i < steps.length; i++) {
        caption(i, 'Loading…');
        let result = null;
        try { result = await steps[i].run(); } catch (e) { if (e === STOP) throw e; result = null; }
        if (t !== token) throw STOP;
        caption(i, steps[i].text(result));
        await wait(steps[i].dwell, t);
      }
    } catch (e) {
      if (e !== STOP) console.error(e);
    } finally {
      if (t === token) stop();
    }
  }

  function stop() {
    token += 1;
    el.hidden = true;
    document.body.classList.remove('touring');
  }

  return { start, stop };
}
