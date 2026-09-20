import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

// Plays the intro/logo video every time the app is loaded, then fades it out to
// reveal the dashboard underneath (which mounts immediately, hidden behind the
// video, so there's no blank gap or late data-load stutter once the fade starts).
//
// Skippable by click/tap/Escape/Space so it never blocks a user in a hurry, and
// it never blocks the app if the video fails to load (network hiccup, codec
// issue) or plays unusually long — both fall back to onDone after a timeout.

const SRC = "/media/intro.mp4";
const FADE_MS = 900;
const MAX_WAIT_MS = 12000; // safety net if the video never fires 'ended'/'error'

export default function IntroSplash({ onDone }) {
  const [fading, setFading] = useState(false);
  const [gone, setGone] = useState(false);
  const videoRef = useRef(null);
  const doneRef = useRef(false);

  const finish = () => {
    if (doneRef.current) return;
    doneRef.current = true;
    setFading(true);
    setTimeout(() => { setGone(true); onDone?.(); }, FADE_MS);
  };

  useEffect(() => {
    const v = videoRef.current;
    v?.play().catch(() => finish()); // autoplay blocked (rare with muted) -> skip straight through
    const safety = setTimeout(finish, MAX_WAIT_MS);

    const onKey = (e) => { if (e.key === "Escape" || e.key === " ") finish(); };
    window.addEventListener("keydown", onKey);
    return () => { clearTimeout(safety); window.removeEventListener("keydown", onKey); };
  }, []); // eslint-disable-line

  if (gone) return null;

  return (
    <AnimatePresence>
      {!gone && (
        <motion.div
          data-testid="intro-splash"
          onClick={finish}
          initial={{ opacity: 1 }}
          animate={{ opacity: fading ? 0 : 1 }}
          transition={{ duration: FADE_MS / 1000, ease: [0.22, 1, 0.36, 1] }}
          style={{
            position: "fixed", inset: 0, zIndex: 9999,
            background: "#070b10",
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <video
            ref={videoRef}
            src={SRC}
            muted
            playsInline
            autoPlay
            onEnded={finish}
            onError={finish}
            style={{ width: "100%", height: "100%", objectFit: "contain" }}
          />
          <div
            style={{
              position: "absolute", bottom: 22, right: 26,
              fontSize: 11, color: "#9fb0c8", letterSpacing: 0.4,
              opacity: 0.75, userSelect: "none",
            }}
          >
            click to skip
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
