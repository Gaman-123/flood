// Cinematic camera moves for the map — "aerial drone" flights and vehicle chase.
//
// Two behaviours:
//   droneFlyTo(map, target)  — pull up, arc across, descend into the target with a
//                              slow orbit. Reads like a drone shot rather than a cut.
//   followRoute(map, coords) — chase an ambulance along its route, camera trailing
//                              slightly behind and looking down the direction of travel.
//
// Smoothness notes: the follow loop drives the camera with jumpTo() on every frame
// from internally-smoothed values, rather than issuing overlapping easeTo() calls
// (which fight each other and produce visible stutter). Bearing is interpolated on
// the shortest angular path so the camera never spins the wrong way through 0/360.

export const easeInOutCubic = (t) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

/** Shortest signed angular difference a->b, in degrees (-180, 180]. */
export function angleDelta(a, b) {
  let d = ((b - a + 180) % 360) - 180;
  return d <= -180 ? d + 360 : d;
}

/** Bearing in degrees from [lon,lat] a to b. */
export function bearingBetween(a, b) {
  const toRad = Math.PI / 180, toDeg = 180 / Math.PI;
  const φ1 = a[1] * toRad, φ2 = b[1] * toRad, Δλ = (b[0] - a[0]) * toRad;
  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  return (Math.atan2(y, x) * toDeg + 360) % 360;
}

/** Cumulative segment lengths for a coordinate path (planar; fine at city scale). */
function cumulative(coords) {
  const cum = [0];
  for (let i = 1; i < coords.length; i++) {
    cum.push(cum[i - 1] + Math.hypot(coords[i][0] - coords[i - 1][0],
                                     coords[i][1] - coords[i - 1][1]));
  }
  return cum;
}

/** Position along a path at normalized t (0..1). */
export function pointAt(coords, cum, t) {
  const total = cum[cum.length - 1] || 1e-9;
  const target = Math.max(0, Math.min(1, t)) * total;
  let i = 1;
  while (i < cum.length - 1 && cum[i] < target) i++;
  const seg = cum[i] - cum[i - 1] || 1e-9;
  const f = (target - cum[i - 1]) / seg;
  return [
    coords[i - 1][0] + (coords[i][0] - coords[i - 1][0]) * f,
    coords[i - 1][1] + (coords[i][1] - coords[i - 1][1]) * f,
  ];
}

/**
 * Drone-style approach: rise, arc across, then descend into the target with a
 * gentle orbit. Returns a promise that resolves when the move finishes.
 */
export function droneFlyTo(map, { lat, lon }, opts = {}) {
  const {
    zoom = 15.6, pitch = 66, bearing = null,
    travelMs = 2600, descendMs = 1900, orbit = 28,
  } = opts;

  return new Promise((resolve) => {
    if (!map) return resolve();
    const startBearing = map.getBearing();
    const finalBearing = bearing == null ? startBearing + orbit : bearing;

    // Stage 1 — arc across at altitude. flyTo's curve already reads as a fly-over;
    // easing keeps the acceleration gentle at both ends.
    map.flyTo({
      center: [lon, lat],
      zoom: Math.max(11.2, zoom - 3.2),
      pitch: Math.min(55, pitch - 14),
      bearing: startBearing + orbit * 0.45,
      duration: travelMs,
      curve: 1.5,
      speed: 0.85,
      easing: easeInOutCubic,
      essential: true,
    });

    const t1 = setTimeout(() => {
      // Stage 2 — descend onto the target, settling into the final framing.
      map.easeTo({
        center: [lon, lat],
        zoom, pitch, bearing: finalBearing,
        duration: descendMs,
        easing: easeInOutCubic,
        essential: true,
      });
      const t2 = setTimeout(resolve, descendMs + 60);
      map.__cinematicTimers.push(t2);
    }, travelMs + 40);

    map.__cinematicTimers = (map.__cinematicTimers || []).concat(t1);
  });
}

/**
 * Chase an ambulance along a route.
 *
 * The camera trails the vehicle and looks down the direction of travel. Position
 * and bearing are smoothed with an exponential filter so corners don't snap, and
 * the whole thing is driven from a single rAF loop.
 *
 * @returns {{stop: Function, promise: Promise}} stop() cancels the chase.
 */
export function followRoute(map, coords, opts = {}) {
  const {
    durationMs = 14000, zoom = 16.2, pitch = 68,
    trail = 0.10,          // how far behind the vehicle the camera sits (0..1 of lookahead)
    smoothing = 0.12,      // EMA factor for position/bearing (lower = smoother, laggier)
    onProgress = null,     // (t, position) => void, for moving the vehicle marker
    onDone = null,
  } = opts;

  let raf = null, stopped = false;
  const cum = cumulative(coords);

  const promise = new Promise((resolve) => {
    if (!map || coords.length < 2) { resolve(); return; }

    let camLon = null, camLat = null, camBearing = map.getBearing();
    const start = performance.now();

    const step = (now) => {
      if (stopped) return resolve();
      const t = Math.min(1, (now - start) / durationMs);

      const pos = pointAt(coords, cum, t);
      // Look a little ahead so the camera anticipates the corner instead of reacting.
      const ahead = pointAt(coords, cum, Math.min(1, t + 0.035));
      const targetBearing = bearingBetween(pos, ahead);

      // Camera sits slightly behind the vehicle along its own heading.
      const behind = pointAt(coords, cum, Math.max(0, t - trail * 0.35));

      if (camLon == null) { camLon = behind[0]; camLat = behind[1]; camBearing = targetBearing; }
      camLon += (behind[0] - camLon) * smoothing;
      camLat += (behind[1] - camLat) * smoothing;
      // shortest-path angular smoothing, so it never unwinds the long way round
      camBearing = (camBearing + angleDelta(camBearing, targetBearing) * smoothing + 360) % 360;

      map.jumpTo({ center: [camLon, camLat], zoom, pitch, bearing: camBearing });
      onProgress && onProgress(t, pos);

      if (t >= 1) { onDone && onDone(); return resolve(); }
      raf = requestAnimationFrame(step);
    };

    // Ease into the chase from wherever the camera currently is, then hand over
    // to the follow loop — avoids a jarring cut at the start.
    const first = coords[0];
    map.easeTo({
      center: first, zoom, pitch,
      bearing: bearingBetween(first, coords[Math.min(3, coords.length - 1)]),
      duration: 1400, easing: easeInOutCubic, essential: true,
    });
    const t0 = setTimeout(() => { if (!stopped) raf = requestAnimationFrame(step); }, 1420);
    map.__cinematicTimers = (map.__cinematicTimers || []).concat(t0);
  });

  return {
    promise,
    stop() {
      stopped = true;
      if (raf) cancelAnimationFrame(raf);
    },
  };
}

/** Cancel any in-flight cinematic move (stage timers + map animations). */
export function cancelCinematic(map) {
  if (!map) return;
  (map.__cinematicTimers || []).forEach(clearTimeout);
  map.__cinematicTimers = [];
  map.stop();
}
