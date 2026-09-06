document.addEventListener('DOMContentLoaded', () => {
    // ── Global Variables ──
    let map, chart;
    let ws;
    let markers = {};
    let routeLayers = [];
    let floodLayers = [];
    let hospitalMarkers = [];
    let currentMode = 'auto'; // 'auto' or 'manual'

    const elements = {
        loader: document.getElementById('loader-overlay'),
        loaderText: document.getElementById('loader-text'),
        loaderProgress: document.getElementById('loader-progress'),
        ambCountBadge: document.getElementById('amb-count-badge'),
        ambSlider: document.getElementById('amb-slider'),
        runBtn: document.getElementById('run-btn'),
        modeAuto: document.getElementById('mode-auto'),
        modeManual: document.getElementById('mode-manual'),
        coordsContainer: document.getElementById('custom-coords-container'),
        lastRefresh: document.getElementById('last-refresh'),
        banner: document.getElementById('alert-banner'),
        routePanel: document.getElementById('route-panel'),
        closePanel: document.getElementById('close-panel'),
        routeCards: document.getElementById('route-cards-container'),
        statRain: document.getElementById('stat-rain'),
        statSea: document.getElementById('stat-sea'),
        // Benchmarks
        benchDijkstra: document.getElementById('bench-dijkstra'),
        benchAstar: document.getElementById('bench-astar'),
        benchSv2: document.getElementById('bench-sv2'),
        benchGa: document.getElementById('bench-ga')
    };

    // ── Initialization ──
    async function init() {
        initMap();
        initChart();
        setupWebsocket();
        updateAmbCountUI(elements.ambSlider.value);
        await fetchStats();
        
        // Hide loader after initial fetch if no job is currently running
        try {
            const resp = await fetch('/api/status');
            const data = await resp.json();
            if (data.status !== 'running') {
                elements.loader.classList.add('hidden');
                fetchResults();
            } else {
                updatePipelineStatus(data);
            }
        } catch (e) {
            elements.loader.classList.add('hidden');
            fetchResults();
        }
    }

    function initMap() {
        map = L.map('map', {
            zoomControl: false,
            attributionControl: false
        }).setView([12.8698, 74.8431], 13);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 20
        }).addTo(map);

        L.control.zoom({ position: 'topright' }).addTo(map);
    }

    function initChart() {
        const ctx = document.getElementById('weather-chart').getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 150);
        gradient.addColorStop(0, 'rgba(0, 242, 254, 0.4)');
        gradient.addColorStop(1, 'rgba(0, 242, 254, 0)');

        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['-6h', '-4h', '-2h', 'Now', '+2h', '+4h', '+6h'],
                datasets: [{
                    label: 'Risk Forecast',
                    data: [0.2, 0.35, 0.5, 0.45, 0.6, 0.8, 0.75], // Mock initial
                    borderColor: '#00f2fe',
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: { 
                        display: false,
                        min: 0,
                        max: 1
                    }
                },
                maintainAspectRatio: false
            }
        });
    }

    // ── WebSocket Logic ──
    function setupWebsocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        ws = new WebSocket(`${protocol}//${host}/ws`);

        ws.onopen = () => console.log('WebSocket Connected');
        
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            handleWsMessage(msg);
        };

        ws.onclose = () => {
            console.log('WS Closed. Retrying...');
            setTimeout(setupWebsocket, 2000);
        };
    }

    function handleWsMessage(msg) {
        switch (msg.type) {
            case 'status':
                updatePipelineStatus(msg.data);
                break;
            case 'stats':
                updateLiveStatsUI(msg.data);
                break;
            case 'error':
                alert(`Pipeline Error: ${msg.message}`);
                elements.runBtn.disabled = false;
                elements.loader.classList.add('hidden');
                break;
        }
    }

    function updatePipelineStatus(data) {
        if (data.status === 'running') {
            elements.runBtn.disabled = true;
            elements.loader.classList.remove('hidden');
            elements.loaderText.textContent = `Processing Pipeline... ${data.progress}%`;
            elements.loaderProgress.style.width = `${data.progress}%`;
        } else if (data.status === 'completed') {
            elements.runBtn.disabled = false;
            elements.loader.classList.add('hidden');
            fetchResults(); // Fetch final mapping data
        }
    }

    // ── API Fetchers ──
    async function fetchStats() {
        try {
            const resp = await fetch('/api/stats');
            const data = await resp.json();
            updateLiveStatsUI(data);
        } catch (e) {
            console.warn('Could not fetch stats');
        }
    }

    function updateLiveStatsUI(data) {
        if (data.error) return;
        elements.statRain.textContent = data.rain_mm.toFixed(1);
        elements.statSea.textContent = data.sea_level_m.toFixed(1);
        
        const date = new Date(data.timestamp);
        elements.lastRefresh.textContent = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // Show banner if rain is high
        if (data.rain_mm > 10) {
            elements.banner.classList.remove('hidden');
        } else {
            elements.banner.classList.add('hidden');
        }
    }

    async function fetchResults() {
        try {
            const resp = await fetch('/static/results.json'); 
            const data = await resp.json();
            renderResultsOnMap(data);
            updateRoutePanel(data);
            updateBenchmarks(data.benchmarks);
        } catch (e) {
            console.error('Failed to fetch results.json', e);
        }
    }

    function updateBenchmarks(bench) {
        if (!bench) return;
        if (elements.benchDijkstra) elements.benchDijkstra.textContent = bench.dijkstra_ms !== undefined ? `${bench.dijkstra_ms} ms` : '--';
        if (elements.benchAstar) elements.benchAstar.textContent = bench.astar_ms !== undefined ? `${bench.astar_ms} ms` : '--';
        if (elements.benchSv2) elements.benchSv2.textContent = bench.tsinghua_v2_ms !== undefined ? `${bench.tsinghua_v2_ms} ms` : '--';
        if (elements.benchGa) elements.benchGa.textContent = bench.ga_optimization_ms !== undefined ? `${bench.ga_optimization_ms} ms` : '--';
    }

    // ── Map Rendering ──
    function renderResultsOnMap(data) {
        // Clear old
        routeLayers.forEach(l => map.removeLayer(l));
        floodLayers.forEach(l => map.removeLayer(l));
        hospitalMarkers.forEach(l => map.removeLayer(l));
        routeLayers = [];
        floodLayers = [];
        hospitalMarkers = [];

        // 1. Render Flood Zones
        data.flood_zones.forEach(zone => {
            const color = zone.category === 'High' ? '#ff4d4d' : '#ffa500';
            const circle = L.circle([zone.lat, zone.lon], {
                radius: 120,
                color: color,
                fillColor: color,
                fillOpacity: 0.3,
                weight: 1
            }).addTo(map);
            floodLayers.push(circle);
        });

        // 2. Render Hospitals
        const hospIcon = L.divIcon({
            html: '<div style="background:#fff; border:2px solid red; width:12px; height:12px; border-radius:3px;"></div>',
            className: 'hospital-icon'
        });
        
        data.hospitals.forEach(h => {
            const m = L.marker([h.lat, h.lon], { icon: hospIcon })
                .bindPopup(`<b>${h.name}</b>`)
                .addTo(map);
            hospitalMarkers.push(m);
        });

        // 3. Render Routes and Animate Markers
        data.ambulances.forEach(amb => {
            if (amb.status === 'ready' && amb.path.length > 0) {
                const poly = L.polyline(amb.path, {
                    color: amb.color,
                    weight: 5,
                    opacity: 0.8,
                    dashArray: '10, 10'
                }).addTo(map);
                routeLayers.push(poly);

                // Start Marker (Square)
                const startMarker = L.circleMarker(amb.path[0], {
                    radius: 6,
                    color: '#00ff00',
                    fillOpacity: 1
                }).addTo(map);
                routeLayers.push(startMarker);

                // Animated Ambulance Marker
                const ambIcon = L.divIcon({
                    className: 'animated-ambulance',
                    html: `<div style="width:14px; height:24px; background:${amb.color}; border:2px solid #fff; border-radius:3px; box-shadow:0 0 10px ${amb.color}"></div>`,
                    iconSize: [14, 24]
                });

                const movingMarker = L.marker(amb.path[0], { icon: ambIcon }).addTo(map);
                routeLayers.push(movingMarker);
                animateMarker(movingMarker, amb.path);
            }
        });

        // Fit map to routes
        if (routeLayers.length > 0) {
            const group = new L.featureGroup(routeLayers);
            map.fitBounds(group.getBounds(), { padding: [50, 50] });
        }
    }

    function animateMarker(marker, path) {
        let i = 0;
        const speed = 100; // ms per hop

        function move() {
            if (i < path.length) {
                marker.setLatLng(path[i]);
                i++;
                setTimeout(move, speed);
            }
        }
        move();
    }

    function updateRoutePanel(data) {
        elements.routePanel.classList.remove('hidden');
        elements.routeCards.innerHTML = '';

        data.ambulances.forEach(amb => {
            const card = document.createElement('div');
            card.className = 'route-card';
            card.style.borderLeft = `4px solid ${amb.color || '#333'}`;

            if (amb.status === 'ready') {
                card.innerHTML = `
                    <div class="card-title">
                        <span>${amb.id}</span>
                        <span style="color: ${amb.color}">OPTIMIZED</span>
                    </div>
                    <div class="card-stats">
                        <span class="card-stat">Dist: <b>${amb.distance_km} km</b></span>
                        <span class="card-stat">Hops: <b>${amb.hops}</b></span>
                        <span class="card-stat">Avg Risk: <b>${amb.avg_risk}</b></span>
                        <span class="card-stat">ETA: <b>${Math.round(amb.distance_km * 2)} min</b></span>
                    </div>
                `;
            } else {
                card.innerHTML = `<div class="card-title"><span>${amb.id}</span><span style="color:#666">FAILED</span></div>`;
            }
            elements.routeCards.appendChild(card);
        });
    }

    // ── Input Listeners ──
    elements.ambSlider.addEventListener('input', (e) => {
        const val = e.target.value;
        updateAmbCountUI(val);
    });

    function updateAmbCountUI(count) {
        elements.ambCountBadge.textContent = count;
        if (currentMode === 'manual') {
            renderManualInputs(count);
        }
    }

    elements.modeAuto.addEventListener('click', () => {
        currentMode = 'auto';
        elements.modeAuto.classList.add('active');
        elements.modeManual.classList.remove('active');
        elements.coordsContainer.classList.add('hidden');
    });

    elements.modeManual.addEventListener('click', () => {
        currentMode = 'manual';
        elements.modeManual.classList.add('active');
        elements.modeAuto.classList.remove('active');
        elements.coordsContainer.classList.remove('hidden');
        renderManualInputs(elements.ambSlider.value);
    });

    function renderManualInputs(n) {
        elements.coordsContainer.innerHTML = '';
        for (let i = 1; i <= n; i++) {
            const row = document.createElement('div');
            row.className = 'coord-row';
            row.innerHTML = `
                <span class="coord-label">AMB-${i.toString().padStart(2, '0')} (Lat, Lon) x2</span>
                <div class="coord-inputs">
                    <input type="text" placeholder="Start (e.g. 12.87,74.84)" class="amb-input" id="amb-${i}-start">
                    <input type="text" placeholder="End (e.g. 12.89,74.85)" class="amb-input" id="amb-${i}-target">
                </div>
            `;
            elements.coordsContainer.appendChild(row);
        }
    }

    elements.runBtn.addEventListener('click', () => {
        const payload = {
            amb_count: parseInt(elements.ambSlider.value),
            ambulances: []
        };

        if (currentMode === 'manual') {
            for (let i = 1; i <= payload.amb_count; i++) {
                const start = document.getElementById(`amb-${i}-start`).value.split(',');
                const target = document.getElementById(`amb-${i}-target`).value.split(',');
                if (start.length === 2 && target.length === 2) {
                    payload.ambulances.push({
                        lat: parseFloat(start[0]),
                        lon: parseFloat(start[1]),
                        target_lat: parseFloat(target[0]),
                        target_lon: parseFloat(target[1])
                    });
                }
            }
        }

        // Send to API
        fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    });

    elements.closePanel.addEventListener('click', () => elements.routePanel.classList.add('hidden'));

    init();
});
