<<<<<<< HEAD


import React, { useEffect, useRef, useState } from "react";
import "./App.css";
import {
  Chart as ChartJS,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Legend,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(LineElement, CategoryScale, LinearScale, PointElement, Tooltip, Legend);

const BASE = "http://127.0.0.1:8000";

// ── Styling helpers ──────────────────────────────────────────────────────────

const getEventClass = (msg) => {
  if (!msg) return "";
  const m = msg.toLowerCase();
  if (m.includes("recover") || m.includes("success")) return "success";
  if (m.includes("heal") || m.includes("restart") || m.includes("approv")) return "healing";
  if (m.includes("fail") || m.includes("error") || m.includes("crash")) return "warning";
  return "default";
};

const getHealClass = (msg) => {
  if (!msg) return "";
  const m = msg.toLowerCase();
  if (m.includes("recover") || m.includes("success")) return "recovered";
  if (m.includes("heal") || m.includes("restart") || m.includes("approv")) return "healing";
  return "critical";
};

const getConfidenceClass = (val) => {
  if (val === null || val === undefined) return "";
  const n = parseFloat(val);
  if (n > 0.8) return "high";
  if (n > 0.5) return "med";
  return "low";
};

// ── Main Component ────────────────────────────────────────────────────────────

function App() {
  const [pods,         setPods]         = useState([]);
  const [analysis,     setAnalysis]     = useState("");
  const [logs,         setLogs]         = useState("");
  const [mttr,         setMttr]         = useState({});
  const [mttrHistory,  setMttrHistory]  = useState([]);
  const [loadingPod,   setLoadingPod]   = useState(null);
  const [mode,         setMode]         = useState("manual");
  const [metrics,      setMetrics]      = useState([]);
  const [scalingStatus,setScalingStatus]= useState("");
  const [context,      setContext]      = useState({});
  const [actionMsg,    setActionMsg]    = useState(""); // transient user-facing feedback

  // Keep a ref to the last MTTR object to avoid duplicate history entries
  const lastMttrRef = useRef({});

  // ── API helpers ─────────────────────────────────────────────────────────────

  const apiFetch = async (path, options = {}) => {
    const res = await fetch(`${BASE}${path}`, options);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  };

  // ── Fetch functions ──────────────────────────────────────────────────────────

  const fetchPods = async () => {
    try { setPods(await apiFetch("/pods")); }
    catch (e) { console.error("[fetchPods]", e); }
  };

  const fetchMetrics = async () => {
    try {
      const data = await apiFetch("/metrics");
      setMetrics(data);
      const highCpuPod = data.find((m) => {
        const raw = m?.containers?.[0]?.usage?.cpu || "";
        return parseCPU(raw) > 500;
      });
      setScalingStatus(
        highCpuPod
          ? `📈 High CPU on ${highCpuPod.metadata?.name} — backend handling`
          : ""
      );
    } catch (e) { console.error("[fetchMetrics]", e); }
  };

  const fetchMTTR = async () => {
    try {
      const data = await apiFetch("/mttr");
      setMttr(data);
      // Only add to history when a new value appears that wasn't there before
      for (const [app, val] of Object.entries(data)) {
        if (lastMttrRef.current[app] !== val) {
          lastMttrRef.current[app] = val;
          setMttrHistory((prev) => [...prev.slice(-9), val]);
        }
      }
    } catch (e) { console.error("[fetchMTTR]", e); }
  };

  const fetchContext = async () => {
    try { setContext(await apiFetch("/context")); }
    catch (e) { console.error("[fetchContext]", e); }
  };

  // ── User actions ─────────────────────────────────────────────────────────────

  const changeMode = async (newMode) => {
    try {
      const data = await apiFetch(`/mode/${newMode}`, { method: "POST" });
      setMode(data.mode === "Autonomous" ? "auto" : "manual");
      setActionMsg(`Switched to ${data.mode} mode`);
    } catch (e) { console.error("[changeMode]", e); }
  };

  const injectFailure = async (name) => {
    try {
      await apiFetch(`/inject-failure/${name}`, { method: "POST" });
      setActionMsg(`⚡ Failure injected: ${name}`);
      setTimeout(fetchPods, 1200);
    } catch (e) { console.error("[injectFailure]", e); }
  };

  const analyzePod = async (name) => {
    if (loadingPod) return;
    try {
      setLoadingPod(name);
      const data = await apiFetch(`/analyze/${name}`);
      setAnalysis(data.analysis);
      setLogs(data.logs || "");
    } catch (e) {
      console.error("[analyzePod]", e);
      setAnalysis("Error analyzing pod");
      setLogs("");
    } finally {
      setLoadingPod(null);
    }
  };

  const restartPod = async (name) => {
    if (mode === "auto") return; // guard (backend also enforces this)
    try {
      await apiFetch(`/restart/${name}`, { method: "POST" });
      setActionMsg(`↺ Manual restart triggered: ${name}`);
      setTimeout(fetchPods, 1500);
    } catch (e) { console.error("[restartPod]", e); }
  };

  const approvePod = async (name) => {
    try {
      await apiFetch(`/approve/${name}`, { method: "POST" });
      setActionMsg(`✅ Approved restart: ${name}`);
      setTimeout(fetchPods, 1500);
    } catch (e) { console.error("[approvePod]", e); }
  };

  // ── Polling ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    // Initial load
    fetchPods();
    fetchMTTR();
    fetchContext();
    fetchMetrics();

    // Fast poll: pods + context + MTTR every 3 s
    const fastInterval = setInterval(() => {
      fetchPods();
      fetchContext();
      fetchMTTR();
    }, 3000);

    // Slower poll: metrics every 10 s (heavier API call)
    const slowInterval = setInterval(fetchMetrics, 10_000);

    return () => {
      clearInterval(fastInterval);
      clearInterval(slowInterval);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Clear transient action message after 4 s
  useEffect(() => {
    if (!actionMsg) return;
    const t = setTimeout(() => setActionMsg(""), 4000);
    return () => clearTimeout(t);
  }, [actionMsg]);

  // ── Pod card helpers ─────────────────────────────────────────────────────────

  const getStatusClass = (pod) => {
    if (pod.unhealthy)             return "red";
    if (pod.status === "Running")  return "green";
    return "yellow";
  };

  const getPodCardClass = (pod) => {
    if (pod.unhealthy)             return "pod-card pod-critical";
    if (pod.status === "Running")  return "pod-card pod-healthy";
    return "pod-card pod-warning";
  };

  // ── CPU helpers ──────────────────────────────────────────────────────────────

  /** Returns millicores as a float from Kubernetes CPU strings. */
  const parseCPU = (cpu) => {
    if (!cpu) return 0;
    if (cpu.includes("n")) return parseInt(cpu) / 1_000_000;
    if (cpu.includes("m")) return parseFloat(cpu);
    return parseFloat(cpu) * 1000;
  };

  const formatCPU = (cpu) => parseCPU(cpu).toFixed(1) + "m";

  /** Find the metric entry for a pod by name. */
  const getPodMetric = (podName) =>
    metrics.find((m) => m?.metadata?.name === podName);

  // ── Confidence display ───────────────────────────────────────────────────────

  const confValue   = context?.confidence;
  const confClass   = getConfidenceClass(confValue);
  const confPercent =
    confValue !== null && confValue !== undefined
      ? `${(parseFloat(confValue) * 100).toFixed(0)}%`
      : null;
  const confBarWidth =
    confValue !== null && confValue !== undefined
      ? `${(parseFloat(confValue) * 100).toFixed(0)}%`
      : "0%";

  // ── MTTR display ─────────────────────────────────────────────────────────────

  const mttrValue = Object.values(mttr)[0];
  const avgMttr   = mttrHistory.length
    ? (mttrHistory.reduce((a, b) => a + b, 0) / mttrHistory.length).toFixed(2)
    : null;

  // ── MTTR chart ───────────────────────────────────────────────────────────────

  const chartData = {
    labels: mttrHistory.map((_, i) => `#${i + 1}`),
    datasets: [
      {
        label: "MTTR (sec)",
        data: mttrHistory,
        tension: 0.4,
        borderColor: "#00e87a",
        backgroundColor: "rgba(0,232,122,0.06)",
        fill: true,
        pointBackgroundColor: "#00e87a",
        pointBorderColor: "#060a10",
        pointBorderWidth: 2,
        pointRadius: 4,
        borderWidth: 2,
      },
      {
        label: "Threshold (6s)",
        data: Array(mttrHistory.length).fill(6),
        borderColor: "#ff3d5a",
        borderDash: [4, 4],
        pointRadius: 0,
        borderWidth: 1.5,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        display: true,
        labels: {
          color: "#6888aa",
          font: { size: 11, family: "IBM Plex Mono" },
          boxWidth: 14,
          padding: 16,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        grid:  { color: "rgba(28,45,69,0.6)" },
        ticks: { color: "#334d6e", font: { size: 11, family: "IBM Plex Mono" } },
        title: { display: true, text: "Seconds", color: "#334d6e", font: { size: 11 } },
      },
      x: {
        grid:  { color: "rgba(28,45,69,0.6)" },
        ticks: { color: "#334d6e", font: { size: 11, family: "IBM Plex Mono" } },
      },
    },
  };

  // ── Derived display values ───────────────────────────────────────────────────

  const bannerLabel = context?.status || context?.action || null;

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="container">

      {/* ─── HEADER ─── */}
      <div className="header">

        {/* Top bar */}
        <div className="header-top">
          <h1>
            <span className="logo-icon">⎈</span>
            KubeHeal
            <span className="pulse-dot" />
          </h1>
          <span className="status-badge">Cluster Active</span>
        </div>

        {/* Agent pills */}
        <div className="agents">
          <div className="agent-pill">🟢 Monitor Agent</div>
          <div className="agent-pill">🟢 RCA Agent</div>
          <div className="agent-pill">🟢 Remediation</div>
        </div>

        <div className="divider" />

        {/* Row 2: mode / agent decision / stats */}
        <div className="header-row2">

          {/* LEFT: mode toggle */}
          <div>
            <div className="mode-toggle">
              <button
                className={mode === "manual" ? "active" : ""}
                onClick={() => changeMode("manual")}
              >
                Manual
              </button>
              <button
                className={mode === "auto" ? "active" : ""}
                onClick={() => changeMode("auto")}
              >
                Autonomous
              </button>
            </div>
            <p className="mode-label">
              MODE: {mode === "auto" ? "🤖 AUTONOMOUS" : "🧑 MANUAL"}
            </p>
          </div>

          {/* CENTER: Agent Decision Card — driven entirely by /context */}
          <div className="agent-decision-card">
            <div className="agent-card-title">Agent Decision</div>

            <div className="agent-kv-grid">
              <div className="agent-kv">
                <span className="kv-label">Pod</span>
                {!context?.pod ? (
                  <div style={{ color: "#6b7280", fontSize: "13px" }}>
                    🟢 System healthy (no issues detected)
                  </div>
                ) : (
                  <span className="kv-value">{context.pod}</span>
                )}
              </div>

              <div className="agent-kv">
                <span className="kv-label">Status</span>
                <span className={`kv-value ${
                  context?.status?.toLowerCase().includes("recov") ? "highlight-recovered"
                  : context?.status?.toLowerCase().includes("fail") ||
                    context?.status?.toLowerCase().includes("error")  ? "highlight-critical"
                  : ""
                }`}>
                  {context?.status || "—"}
                </span>
              </div>

              <div className="agent-kv">
                <span className="kv-label">Issue</span>
                <span className="kv-value highlight-issue">
                  {context?.anomaly || "—"}
                </span>
              </div>

              <div className="agent-kv">
                <span className="kv-label">Action</span>
                <span className="kv-value highlight-action">
                  {context?.action || "—"}
                </span>
              </div>

              <div className="agent-kv full-width">
                <span className="kv-label">RCA</span>
                <span className="kv-value">{context?.rca || "—"}</span>
              </div>
            </div>

            {/* Confidence bar */}
            <div className="confidence-row">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="kv-label">Confidence</span>
                {confPercent && (
                  <span className={`confidence-value ${confClass}`}>{confPercent}</span>
                )}
              </div>
              <div className="confidence-bar-track">
                <div
                  className={`confidence-bar-fill ${confClass}`}
                  style={{ width: confBarWidth }}
                />
              </div>
            </div>

            {/* Outcome */}
            {context?.outcome && (
              <div className="agent-kv" style={{ marginBottom: "12px" }}>
                <span className="kv-label">Outcome</span>
                <span className="kv-value">{context.outcome}</span>
              </div>
            )}

            {/* Human-approval button — only when backend requests it */}
            {context?.action === "Needs Human Approval" && context?.pod && (
              <div style={{ marginTop: "10px" }}>
                <button
                  className="btn restart"
                  onClick={() => approvePod(context.pod)}
                >
                  ✅ Approve Restart for {context.pod}
                </button>
              </div>
            )}

            {/* Log preview */}
            <div className="log-label">Recent Logs</div>
            <div className="agent-log-preview">
              {context?.logs
                ? context.logs.split("\n").slice(0, 3).join("\n")
                : "No logs yet"}
            </div>
          </div>

          {/* RIGHT: MTTR + event banner */}
          <div className="header-stats">
            {mttrValue !== undefined && mttrValue !== null && (
              <span className="mttr">⏱ MTTR {Number(mttrValue).toFixed(2)}s</span>
            )}
            {bannerLabel && (
              <span className={`event-banner ${getEventClass(bannerLabel)}`}>
                {bannerLabel}
              </span>
            )}
          </div>

        </div>

        {/* Auto-heal status banner */}
        {mode === "auto" && context?.action && (
          <div className={`auto-heal-status ${getHealClass(context.action)}`}>
            {context.action}
          </div>
        )}

        {/* Scaling notice */}
        {scalingStatus && (
          <div className="scaling-status">{scalingStatus}</div>
        )}

        {/* Transient user action feedback */}
        {actionMsg && (
          <div className="action-feedback">{actionMsg}</div>
        )}

      </div>{/* /header */}

      {/* ─── PODS ─── */}
      <p className="section-label">Pod Status</p>

      {pods.length === 0 ? (
        <div className="loading-pods">Fetching pods…</div>
      ) : (
        pods.map((pod) => {
          const podMetric = getPodMetric(pod.name);
          const cpuRaw    = podMetric?.containers?.[0]?.usage?.cpu;
          const cpuVal    = parseCPU(cpuRaw);
          const isHighCPU = cpuVal > 50;

          return (
            <div key={pod.name} className={getPodCardClass(pod)}>
              <div className="card-top">
                <span className="pod-name">{pod.name}</span>

                {cpuRaw && (
                  <span className={`cpu-chip ${isHighCPU ? "high" : "normal"}`}>
                    <span className="cpu-dot" />
                    CPU {formatCPU(cpuRaw)}
                    {isHighCPU && " ⚠"}
                  </span>
                )}

                {/*
                  pod.status is enriched by the backend to show container-level
                  failures (CrashLoopBackOff, ImagePullBackOff, etc.) rather than
                  just the pod phase.
                */}
                <span className={`status ${getStatusClass(pod)}`}>
                  {pod.status}
                </span>
              </div>

              <div className="card-actions">
                {/* Restart — manual mode only */}
                <button
                  className="btn restart"
                  onClick={() => restartPod(pod.name)}
                  disabled={mode === "auto"}
                  title={
                    mode === "auto"
                      ? "Disabled in Autonomous mode"
                      : "Manually restart pod"
                  }
                >
                  ↺ Restart
                </button>

                {/* Inject — available in both modes for demo */}
                <button
                  className="btn inject"
                  onClick={() => injectFailure(pod.name)}
                  title="Simulate a pod failure by deleting it"
                >
                  ⚡ Inject
                </button>

                {/* Analyze — manual mode only (auto mode does RCA automatically) */}
                <button
                  className="btn analyze"
                  onClick={() => analyzePod(pod.name)}
                  disabled={mode === "auto" || loadingPod === pod.name}
                  title={
                    mode === "auto"
                      ? "RCA runs automatically in Autonomous mode"
                      : "Run root cause analysis"
                  }
                >
                  {loadingPod === pod.name ? "…" : "🔍 Analyze"}
                </button>
              </div>
            </div>
          );
        })
      )}

      {/* ─── MTTR CHART ─── */}
      {mttrHistory.length > 0 && (
        <>
          <p className="section-label" style={{ marginTop: "26px" }}>Recovery Trend</p>
          <div className="card">
            <h3>MTTR Over Time</h3>
            <Line data={chartData} options={chartOptions} />
            {avgMttr && (
              <p className="mttr-avg">
                Avg MTTR: <span>{avgMttr}s</span>
              </p>
            )}
          </div>
        </>
      )}

      {/* ─── AI DIAGNOSIS (manual analyze result) ─── */}
      {analysis && (
        <>
          <p className="section-label" style={{ marginTop: "26px" }}>AI Diagnosis</p>
          <div className="ai-box">
            <h3>Root Cause Analysis</h3>
            <p>{analysis}</p>
            <h3 style={{ marginTop: "20px" }}>Raw Logs</h3>
            <pre className="log-block">{logs || "(no logs)"}</pre>
          </div>
        </>
      )}

=======
import logo from './logo.svg';
import './App.css';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <img src={logo} className="App-logo" alt="logo" />
        <p>
          Edit <code>src/App.js</code> and save to reload.
        </p>
        <a
          className="App-link"
          href="https://reactjs.org"
          target="_blank"
          rel="noopener noreferrer"
        >
          Learn React
        </a>
      </header>
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
    </div>
  );
}

export default App;
<<<<<<< HEAD

=======
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
