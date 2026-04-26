document.addEventListener('DOMContentLoaded', () => {

    // ── AMBULANCE FLEET COUNT ──────────────────────────────────────
    const AMB_COLORS = ['#00f2fe','#ff007f','#7fff00','#ffd700','#ff6b35','#a855f7'];
    const DEFAULT_COORDS = [
        { start: '12.87, 74.84', end: '12.88, 74.85' },
        { start: '12.86, 74.83', end: '12.89, 74.86' },
        { start: '12.85, 74.82', end: '12.90, 74.87' },
        { start: '12.83, 74.84', end: '12.87, 74.88' },
        { start: '12.84, 74.85', end: '12.91, 74.85' },
        { start: '12.82, 74.83', end: '12.89, 74.90' },
    ];

    let ambCount = 2;

    window.updateAmbCount = function(val) {
        ambCount = parseInt(val);
        document.getElementById('amb-count-label').textContent = `${ambCount} Unit${ambCount > 1 ? 's' : ''}`;
        renderAmbInputs();
    };

    function renderAmbInputs() {
        const container = document.getElementById('custom-inputs');
        container.innerHTML = '';
        const mode = document.querySelector('input[name="feed-mode"]:checked').value;
        if (mode !== 'custom') return;

        for (let i = 0; i < ambCount; i++) {
            const color = AMB_COLORS[i % AMB_COLORS.length];
            const def = DEFAULT_COORDS[i] || { start: '12.87, 74.84', end: '12.88, 74.85' };
            const label = `AMB-0${i + 1}`;
            container.insertAdjacentHTML('beforeend', `
                <div class="amb-input-group" style="border-left: 3px solid ${color}; padding-left: 10px; margin-bottom: 16px;">
                    <p class="desc" style="color:${color}; margin-bottom: 6px; font-weight: 600;">${label}</p>
                    <div style="display:flex; gap:5px; align-items:center; margin-bottom:5px;">
                        <input type="text" id="amb${i+1}-start" placeholder="Start lat, lon" class="input-glass" value="${def.start}">
                        <span style="color:#666;">→</span>
                        <input type="text" id="amb${i+1}-end" placeholder="End lat, lon" class="input-glass" value="${def.end}">
                    </div>
                </div>
            `);
        }
    }

    window.toggleInputs = function() {
        const mode = document.querySelector('input[name="feed-mode"]:checked').value;
        document.getElementById('custom-inputs').style.display = (mode === 'custom') ? 'block' : 'none';
        renderAmbInputs();
    };

    // Initialize with default count
    renderAmbInputs();

    // ── LIVE STATS ─────────────────────────────────────────────────
    async function fetchLiveStats() {
        try {
            const resp = await fetch('http://localhost:3000/live-stats');
            const stats = await resp.json();
            document.getElementById('live-rain').textContent = `${stats.rain_mm} mm`;
            document.getElementById('live-sea').textContent  = `${stats.sea_level_m} m`;
            document.getElementById('live-river').textContent = `${stats.river_discharge_m3s} m³/s`;

            const d = new Date(stats.timestamp);
            document.getElementById('time-display').innerHTML =
                `Last Update: <span style="color:var(--accent-1)">${d.toLocaleTimeString()}</span>`;

            ['live-rain', 'live-sea', 'live-river'].forEach(id => {
                const el = document.getElementById(id);
                el.style.color = '#00f2fe';
                setTimeout(() => el.style.color = '#f2f5f8', 1000);
            });
        } catch(e) {
            console.error('Could not load live stats');
        }
    }

    setInterval(fetchLiveStats, 5000);
    fetchLiveStats();

    // ── RUN PIPELINE ───────────────────────────────────────────────
    const runBtn = document.getElementById('run-pipeline-btn');
    const loader  = document.getElementById('loader');
    const iframe  = document.getElementById('map-frame');

    const resetBtn = (label = 'Run QUBO Optimizer') => {
        runBtn.disabled = false;
        runBtn.innerHTML = `<span class="run-icon">▶</span> ${label}`;
        loader.classList.remove('active');
        iframe.style.opacity = '1';
    };

    runBtn.addEventListener('click', async () => {
        runBtn.disabled = true;
        runBtn.innerHTML = '<span class="run-icon">⏳</span> Optimizing Routes...';
        loader.classList.add('active');
        iframe.style.opacity = '0.3';

        const mode = document.querySelector('input[name="feed-mode"]:checked').value;
        const payload = { mode, amb_count: ambCount };

        if (mode === 'custom') {
            payload.ambulances = [];
            for (let i = 0; i < ambCount; i++) {
                const parse = id => document.getElementById(id).value.split(',').map(s => s.trim());
                const s = parse(`amb${i+1}-start`);
                const e = parse(`amb${i+1}-end`);
                payload.ambulances.push({
                    id: `AMB-0${i+1}`,
                    start_lat: s[0], start_lon: s[1],
                    end_lat:   e[0], end_lon:   e[1]
                });
            }
        }

        try {
            const response = await fetch('http://localhost:3000/run-pipeline', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();

            if (data.status === 'success') {
                iframe.src = '/map?t=' + new Date().getTime();
                setTimeout(() => {
                    resetBtn('Re-Run QUBO Optimizer');
                    document.querySelectorAll('.metric-list strong').forEach(m => {
                        m.style.color = '#fff';
                        m.style.textShadow = '0 0 10px #fff';
                        setTimeout(() => { m.style.color = ''; m.style.textShadow = ''; }, 600);
                    });
                    fetchLiveStats();
                }, 1200);
            } else {
                alert('Pipeline failed: ' + data.message);
                resetBtn();
            }
        } catch (err) {
            console.error(err);
            alert('Could not connect to backend server.');
            resetBtn();
        }
    });
});
