import { useEffect, useRef, useState } from "react";
import { HandLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";

// Hologram-style two-hand map control (runs 100% locally; no video leaves device).
//   1. "Gesture mode" button -> camera on, ARMED (tracking, not yet controlling).
//   2. Thumbs-up 👍 -> LOCK IN (gestures now drive the map). 👍 again -> pause.
//   3. ZOOM hand (right): open the pinch to zoom IN, close to zoom OUT. Velocity-
//      based, so holding open keeps zooming further.
//      PAN hand (left): move it like a joystick — the map flies left/right/up/down.
// Velocity + EMA smoothing = fluid, drift-free motion.

const WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
const MODEL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";

const NEUTRAL_PINCH = 0.11, PINCH_DEAD = 0.03, ZOOM_SPEED = 4.0;   // zoom levels/sec
const PAN_SPEED = 2200;                                            // drag gain: hand travel -> map px
const ZMIN = 9, ZMAX = 17;

function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }

const folded = (lm, tip, pip) => lm[tip].y > lm[pip].y;             // tip below pip = curled

function isThumbsUp(lm) {
  const [wrist, , tMcp, tIp, tTip] = [lm[0], lm[1], lm[2], lm[3], lm[4]];
  const thumbUp = tTip.y < tIp.y && tIp.y < tMcp.y && tTip.y < wrist.y - 0.12;
  return thumbUp && folded(lm, 8, 6) && folded(lm, 12, 10) && folded(lm, 16, 14) && folded(lm, 20, 18);
}

// Fist = all four fingers curled and thumb NOT raised (distinct from thumbs-up).
function isFist(lm) {
  const allCurled = folded(lm, 8, 6) && folded(lm, 12, 10) && folded(lm, 16, 14) && folded(lm, 20, 18);
  return allCurled && !isThumbsUp(lm);
}

export default function GestureControl({ mapRef }) {
  const [phase, setPhase] = useState("off");   // off | armed | active
  const [status, setStatus] = useState("");
  const [hud, setHud] = useState({ zoom: null, zHand: false, pHand: false });
  const videoRef = useRef(null), canvasRef = useRef(null);
  const lmRef = useRef(null), rafRef = useRef(null), streamRef = useRef(null);
  const phaseRef = useRef("off");
  const s = useRef({ pinchEMA: null, panPrev: null, panVel: { x: 0, y: 0 }, lastT: 0, tuCooldown: 0, lastHud: 0 });

  useEffect(() => { phaseRef.current = phase; }, [phase]);
  useEffect(() => () => stop(), []); // cleanup

  async function start() {
    try {
      if (!window.isSecureContext) setStatus("needs HTTPS/localhost for camera");
      setStatus("loading hand model…");
      const fileset = await FilesetResolver.forVisionTasks(WASM);
      let maker;
      try {
        maker = await HandLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL, delegate: "GPU" },
          numHands: 2, runningMode: "VIDEO",
        });
      } catch {
        maker = await HandLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL, delegate: "CPU" },
          numHands: 2, runningMode: "VIDEO",
        });
      }
      lmRef.current = maker;
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 320, height: 240 }, audio: false });
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) throw new Error("video not ready — click again");
      video.srcObject = stream;
      await video.play();
      setPhase("armed");
      setStatus("👍 to lock · ✊ fist=drag · 🤏 pinch=zoom");
      s.current.lastT = performance.now();
      loop();
    } catch (e) {
      setStatus("camera error: " + (e?.message || e));
      setPhase("off");
    }
  }

  function stop() {
    cancelAnimationFrame(rafRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    lmRef.current?.close?.(); lmRef.current = null;
    setPhase("off"); phaseRef.current = "off";
  }

  function loop() {
    const video = videoRef.current, lm = lmRef.current, map = mapRef?.current;
    rafRef.current = requestAnimationFrame(loop);
    if (!video || !lm || video.readyState < 2) return;
    const now = performance.now();
    const dt = Math.min(0.05, (now - (s.current.lastT || now)) / 1000);
    s.current.lastT = now;

    let res;
    try { res = lm.detectForVideo(video, now); } catch { return; }
    const hands = res?.landmarks || [];
    drawOverlay(hands);

    // thumbs-up toggles armed <-> active
    const anyThumbsUp = hands.some(isThumbsUp);
    if (anyThumbsUp && now > s.current.tuCooldown) {
      s.current.tuCooldown = now + 1200;
      setPhase((p) => (p === "active" ? "armed" : "active"));
    }

    let zHand = false, pHand = false;
    if (phaseRef.current === "active" && map && hands.length) {
      // Deterministic roles (handedness is unreliable in a mirrored view):
      //   • 2 hands  -> leftmost-on-screen pans, rightmost zooms
      //   • 1 hand   -> FIST = drag-to-pan (swipe), OPEN = pinch-to-zoom
      let zoomHand = null, panHand = null;
      const screenX = (h) => 1 - h[9].x;                 // mirror x to match the view
      if (hands.length >= 2) {
        const sorted = [...hands].sort((a, b) => screenX(a) - screenX(b));
        panHand = sorted[0];                             // left on screen
        zoomHand = sorted[sorted.length - 1];            // right on screen
      } else {
        const h = hands[0];
        if (isFist(h)) panHand = h; else zoomHand = h;
      }

      // ZOOM — velocity from pinch openness vs neutral (hold open = keep zooming)
      if (zoomHand && !isThumbsUp(zoomHand) && !isFist(zoomHand)) {
        zHand = true;
        const pinch = dist(zoomHand[4], zoomHand[8]);
        s.current.pinchEMA = s.current.pinchEMA == null ? pinch : s.current.pinchEMA + (pinch - s.current.pinchEMA) * 0.4;
        const off = s.current.pinchEMA - NEUTRAL_PINCH;
        if (Math.abs(off) > PINCH_DEAD) {
          const rate = Math.sign(off) * (Math.abs(off) - PINCH_DEAD) * ZOOM_SPEED * 12;
          const z = Math.max(ZMIN, Math.min(ZMAX, map.getZoom() + rate * dt));
          map.setZoom(z);
        }
      }
      // PAN — DRAG/SWIPE: the map follows the hand's motion frame-to-frame
      if (panHand) {
        pHand = true;
        const palm = panHand[0];                         // wrist = stable drag anchor
        const cx = 1 - palm.x, cy = palm.y;              // mirror x to match view
        if (s.current.panPrev) {
          let dx = cx - s.current.panPrev.x, dy = cy - s.current.panPrev.y;
          if (Math.abs(dx) < 0.004) dx = 0;              // jitter deadzone
          if (Math.abs(dy) < 0.004) dy = 0;
          s.current.panVel.x += (dx - s.current.panVel.x) * 0.5;   // smooth
          s.current.panVel.y += (dy - s.current.panVel.y) * 0.5;
          // grab-and-drag: hand right -> map content right (reveal west)
          if (s.current.panVel.x || s.current.panVel.y)
            map.panBy([-s.current.panVel.x * PAN_SPEED, -s.current.panVel.y * PAN_SPEED], { duration: 0 });
        }
        s.current.panPrev = { x: cx, y: cy };
      } else {
        s.current.panPrev = null; s.current.panVel.x = 0; s.current.panVel.y = 0;
      }
      if (now - s.current.lastHud > 100) { s.current.lastHud = now; setHud({ zoom: map.getZoom().toFixed(1), zHand, pHand }); }
    } else if (phaseRef.current === "armed" && now - s.current.lastHud > 200) {
      s.current.lastHud = now;
      setHud({ zoom: map?.getZoom?.().toFixed(1) ?? null, zHand: false, pHand: false });
    }
  }

  function drawOverlay(hands) {
    const c = canvasRef.current; if (!c) return;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    const px = (p) => [(1 - p.x) * c.width, p.y * c.height];
    hands.forEach((h) => {
      const tu = isThumbsUp(h);
      ctx.fillStyle = tu ? "var(--watch)" : "var(--accent)";
      h.forEach((p) => { const [x, y] = px(p); ctx.beginPath(); ctx.arc(x, y, 2.5, 0, 7); ctx.fill(); });
      ctx.strokeStyle = "var(--safe)"; ctx.lineWidth = 2;
      const [ax, ay] = px(h[4]), [bx, by] = px(h[8]);
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
    });
  }

  const active = phase === "active";
  const on = phase !== "off";            // gesture feature enabled (armed or locked)
  return (
    <div style={{ position: "absolute", right: 16, bottom: 16, zIndex: 6, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
      <div className="card-panel" style={{ padding: 6, borderRadius: 12, position: "relative", display: phase === "off" ? "none" : "block",
        outline: active ? "2px solid var(--safe)" : "1px solid transparent" }}>
        <video ref={videoRef} width={168} height={126} muted playsInline
          style={{ borderRadius: 8, transform: "scaleX(-1)", display: "block", background: "#000" }} />
        <canvas ref={canvasRef} width={168} height={126}
          style={{ position: "absolute", left: 6, top: 6, borderRadius: 8, pointerEvents: "none" }} />
        <div style={{ position: "absolute", left: 10, top: 8, display: "flex", gap: 4 }}>
          <span className="mono" style={{ fontSize: 9, padding: "1px 5px", borderRadius: 5,
            background: active ? "rgba(42,169,107,0.14)" : "rgba(207,143,28,0.16)", color: active ? "var(--safe)" : "var(--watch)" }}>
            {active ? "LOCKED" : "ARMED · 👍 to lock"}</span>
        </div>
        {hud.zoom && <div className="mono" style={{ position: "absolute", right: 10, top: 8, fontSize: 9, color: "var(--accent)", background: "rgba(237,240,245,0.86)", padding: "1px 5px", borderRadius: 5 }}>z{hud.zoom}</div>}
        {active && (
          <div style={{ position: "absolute", left: 6, bottom: 6, right: 6, display: "flex", justifyContent: "space-between", fontSize: 9 }}>
            <span style={{ color: hud.pHand ? "var(--safe)" : "var(--text-mute)", opacity: hud.pHand ? 1 : 0.5 }}>✊ drag-pan</span>
            <span style={{ color: hud.zHand ? "var(--accent)" : "var(--text-mute)", opacity: hud.zHand ? 1 : 0.5 }}>🤏 zoom</span>
          </div>
        )}
        <div style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 4, textAlign: "center", maxWidth: 168 }}>{status}</div>
      </div>
      {/* on/off toggle switch for the whole gesture feature */}
      <button
        role="switch"
        aria-checked={on}
        aria-label="Gesture control"
        onClick={on ? stop : start}
        className="card-panel"
        style={{
          cursor: "pointer", display: "flex", alignItems: "center", gap: 9,
          padding: "7px 11px 7px 13px", border: "none",
          background: on ? "rgba(63,116,201,0.12)" : "var(--surface-raised)",
        }}>
        <span style={{ fontSize: 14 }}>✋</span>
        <span style={{ fontSize: 11.5, fontWeight: 500, color: on ? "var(--accent)" : "var(--text-dim)" }}>
          Gesture control
        </span>
        {/* track */}
        <span style={{
          position: "relative", width: 34, height: 19, borderRadius: 999,
          background: on ? "var(--accent)" : "var(--surface-sunken)",
          boxShadow: on ? "none" : "var(--neo-in-sm)",
          transition: "background .2s cubic-bezier(.22,1,.36,1)", flexShrink: 0,
        }}>
          {/* knob */}
          <span style={{
            position: "absolute", top: 2.5, left: on ? 17.5 : 2.5, width: 14, height: 14,
            borderRadius: "50%", background: "#ffffff",
            boxShadow: "0 1px 3px rgba(44,54,72,0.4)",
            transition: "left .2s cubic-bezier(.22,1,.36,1)",
          }} />
        </span>
      </button>
      {phase === "off" && status && <div style={{ fontSize: 10, color: "var(--text-dim)", maxWidth: 200, textAlign: "right" }}>{status}</div>}
    </div>
  );
}
