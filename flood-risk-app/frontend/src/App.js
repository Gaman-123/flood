import { useEffect, useState } from "react";
import "./App.css";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, ChevronLeft } from "lucide-react";
import { useAppStore } from "./lib/store";
import TopBar from "./components/TopBar";
import LeftRail from "./components/LeftRail";
import MapCanvas from "./components/MapCanvas";
import RiskTab from "./components/tabs/RiskTab";
import LiveTab from "./components/tabs/LiveTab";
import SimulateTab from "./components/tabs/SimulateTab";
import ResultsTab from "./components/tabs/ResultsTab";
import AboutTab from "./components/tabs/AboutTab";
import EmergencyTab from "./components/tabs/EmergencyTab";
import IntroSplash from "./components/IntroSplash";
import { Toaster } from "sonner";

const PANEL_W = 380;

export default function App() {
  const activeTab = useAppStore((s) => s.activeTab);
  const tick = useAppStore((s) => s.tick);
  const panelOpen = useAppStore((s) => s.panelOpen);
  const togglePanel = useAppStore((s) => s.togglePanel);
  const [introDone, setIntroDone] = useState(false);

  // Global 60fps sim clock — every tab that uses simTime reads from the store.
  useEffect(() => {
    let last = performance.now();
    let raf;
    const loop = (now) => {
      const dt = (now - last) / 1000;
      last = now;
      tick(dt);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [tick]);

  const TabPanel = (
    { risk: RiskTab, live: LiveTab, simulate: SimulateTab, emergency: EmergencyTab, results: ResultsTab, about: AboutTab }[activeTab]
  );

  return (
    <div className="App" data-testid="app-root">
      {/* Dashboard mounts immediately underneath so the map/data are already
          loading while the intro plays — no stutter or blank frame at the fade. */}
      <div aria-hidden={!introDone} style={{ height: "100%" }}>
      <TopBar />
      <div style={{ display: "flex", height: "calc(100vh - 56px)" }}>
        <LeftRail />
        <div style={{ position: "relative", flex: 1, minWidth: 0 }}>
          <MapCanvas />

          {/* panel collapse/expand toggle — rides the panel edge */}
          <button
            data-testid="toggle-panel"
            onClick={togglePanel}
            title={panelOpen ? "Hide panel (map only)" : "Show panel"}
            style={{
              position: "absolute", top: "50%", right: 12, zIndex: 7,
              transform: "translateY(-50%)",
              width: 30, height: 52, borderRadius: 10,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: "var(--surface)", border: "none", color: "var(--text-dim)",
              boxShadow: "var(--neo-out-sm)",
              cursor: "pointer", backdropFilter: "blur(8px)", boxShadow: "0 4px 16px #0007",
            }}
            className="panel-toggle"
          >
            {panelOpen ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>

        <motion.aside
          data-testid="right-panel"
          initial={false}
          animate={{ width: panelOpen ? PANEL_W : 0, opacity: panelOpen ? 1 : 0 }}
          transition={{ type: "spring", stiffness: 260, damping: 32 }}
          style={{
            borderLeft: "none",
            background: "var(--surface)",
            boxShadow: panelOpen ? "-6px 0 16px -10px var(--shadow-dark)" : "none",
            overflow: "hidden",
            flexShrink: 0,
          }}
        >
          <div style={{ width: PANEL_W, height: "100%", overflowY: "auto", padding: 16, boxSizing: "border-box" }}>
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              >
                <TabPanel />
              </motion.div>
            </AnimatePresence>
          </div>
        </motion.aside>
      </div>
      <Toaster theme="dark" richColors position="bottom-right" />
      </div>
      {!introDone && <IntroSplash onDone={() => setIntroDone(true)} />}
    </div>
  );
}
