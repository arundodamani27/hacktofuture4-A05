import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kubernetes import client
from kubernetes import config as kube_config
from kubernetes.client import CustomObjectsApi

from app import config
from app.monitor import auto_heal, get_pods, get_pod_metrics, mttr_store

# ---------------------------
# 🔧 KUBERNETES SETUP
# ---------------------------
try:
    kube_config.load_kube_config()
except Exception:
    kube_config.load_incluster_config()

v1          = client.CoreV1Api()
metrics_api = CustomObjectsApi()
# ---------------------------
# 🧠 SHARED INCIDENT CONTEXT
# ---------------------------
# All monitor and API logic mutates this dict in-place.
# Fields:
#   pod           – name of the affected pod (or None)
#   anomaly       – short failure label
#   logs          – last N log lines
#   rca           – root cause string
#   confidence    – float 0.0–1.0
#   action        – what the system / user did
#   status        – current lifecycle status
#   outcome       – final outcome text
#   manual_restart – True when /restart was called; cleared after recovery
#   auto_healed   – True when monitor auto-deleted the pod; cleared after recovery
incident_context: dict = {
    "pod":           None,
    "anomaly":       None,
    "logs":          None,
    "rca":           None,
    "confidence":    None,
    "action":        None,
    "status":        None,
    "outcome":       None,
    "manual_restart": False,
    "auto_healed":   False,
}

# ---------------------------
# 🚀 FASTAPI APP
# ---------------------------
app = FastAPI(title="KubeHeal", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# 🔁 START MONITOR THREAD
# ---------------------------
threading.Thread(
    target=auto_heal,
    args=(incident_context,),
    daemon=True,
    name="auto-heal-loop",
).start()


# ---------------------------
# 🏠 HOME
# ---------------------------
@app.get("/")
def home():
    return {
        "message": "KubeHeal backend running",
        "mode":    "Autonomous" if config.AUTO_MODE else "Manual",
    }
# ---------------------------
# 📦 GET PODS
# ---------------------------
@app.get("/pods")
def list_pods():
    """
    Returns all non-system pods with an enriched 'status' field that reflects
    container-level failures (CrashLoopBackOff, ImagePullBackOff, etc.)
    rather than just pod phase.
    """
    return get_pods()


# ---------------------------
# 📊 METRICS
# ---------------------------
@app.get("/metrics")
def list_metrics():
    return get_pod_metrics()

# ---------------------------
# 📊 MTTR
# ---------------------------
@app.get("/mttr")
def get_mttr():
    return mttr_store


# ---------------------------
# 🧠 ANALYZE POD
# ---------------------------
@app.get("/analyze/{pod_name}")
def analyze_pod(pod_name: str):
    """
    On-demand analysis triggered by the user.
    Inspects container_statuses first for precise detection, then falls back
    to log-keyword scanning.
    """
    # 1. Fetch pod object to check container statuses
    container_reason: str | None = None
    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace="default")
        container_reason = _container_failure_reason(pod)
    except Exception:
        pass  # pod may not exist yet; proceed to log scan

    # 2. Fetch logs
    logs = ""
    try:
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace="default",
            tail_lines=30,
        )
    except Exception as e:
        logs = f"Could not fetch logs: {e}"

    # 3. Determine analysis
    if container_reason:
        analysis = _reason_to_analysis(container_reason)
    else:
        analysis = _scan_logs(logs)

    incident_context.update(
        pod=pod_name,
        rca=analysis,
        logs=logs or "(empty logs)",
    )

    return {"analysis": analysis, "logs": logs}


def _container_failure_reason(pod) -> str | None:
    """Mirror of monitor.py helper — avoids importing across packages."""
    if not pod.status or not pod.status.container_statuses:
        return None

    failure_reasons = {
        "CrashLoopBackOff",
        "RunContainerError",
        "ImagePullBackOff",
        "ErrImagePull",
        "OOMKilled",
        "Error",
        "CreateContainerConfigError",
        "InvalidImageName",
        "ContainerCannotRun",
    }
    for cs in pod.status.container_statuses:
        state = cs.state
        if state is None:
            continue
        if state.waiting and state.waiting.reason in failure_reasons:
            return state.waiting.reason
        if state.terminated and state.terminated.reason in failure_reasons:
            return state.terminated.reason
    return None

def _reason_to_analysis(reason: str) -> str:
    mapping = {
        "CrashLoopBackOff":          "CrashLoopBackOff — application crash loop detected",
        "RunContainerError":         "RunContainerError — container could not start",
        "ImagePullBackOff":          "ImagePullBackOff — container image pull failed",
        "ErrImagePull":              "ErrImagePull — container image pull error",
        "OOMKilled":                 "OOMKilled — memory limit exceeded",
        "Error":                     "Container exited with a non-zero error code",
        "CreateContainerConfigError":"CreateContainerConfigError — bad container config (missing Secret/ConfigMap?)",
        "InvalidImageName":          "InvalidImageName — container image name is invalid",
        "ContainerCannotRun":        "ContainerCannotRun — runtime rejected the container",
    }
    return mapping.get(reason, f"Container failure: {reason}")

def _scan_logs(logs: str) -> str:
    logs_lower = logs.lower()
    if "oomkilled" in logs_lower or "out of memory" in logs_lower:
        return "OOMKilled — memory limit exceeded"
    if "crashloopbackoff" in logs_lower or "crash" in logs_lower:
        return "CrashLoopBackOff — application crash loop"
    if "imagepullbackoff" in logs_lower:
        return "ImagePullBackOff — container image pull failed"
    if "timeout" in logs_lower:
        return "Network or readiness timeout detected"
    if "error" in logs_lower:
        return "Application error detected in logs"
    return "No critical issue detected"

# ---------------------------
# 💥 INJECT FAILURE (demo)
# ---------------------------
@app.post("/inject-failure/{pod_name}")
def inject_failure(pod_name: str):
    """
    Deletes the named pod to simulate a failure.
    Resets the incident context so the monitor can detect it fresh.
    """
    try:
        v1.delete_namespaced_pod(name=pod_name, namespace="default")
        # Full reset — no stale "Recovered" leaking through
        incident_context.update(
            pod=pod_name,
            anomaly=None,
            logs=None,
            rca=None,
            confidence=None,
            action=None,
            status="Failure injected",
            outcome=None,
            manual_restart=False,
            auto_healed=False,
        )
        return {"message": f"Failure injected: {pod_name} deleted"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------
# 🔁 MANUAL RESTART
# ---------------------------
@app.post("/restart/{pod_name}")
def restart_pod(pod_name: str):
    """
    Manual restart — MANUAL MODE only.
    Sets manual_restart=True so the monitor labels recovery as 'Manual Restart Done'.
    """
    if config.AUTO_MODE:
        return {"error": "Manual restart is not available in Autonomous mode"}

    try:
        v1.delete_namespaced_pod(name=pod_name, namespace="default")
        incident_context.update(
            pod=pod_name,
            action="Manual Restart Triggered",
            status="Restarting",
            outcome=None,
            manual_restart=True,   # monitor reads this to label recovery
            auto_healed=False,
        )
        return {"message": f"{pod_name} manual restart triggered"}
    except Exception as e:
        return {"error": str(e)}

# ---------------------------
# 🤖 MODE CONTROL
# ---------------------------
@app.post("/mode/{mode}")
def set_mode(mode: str):
    if mode not in ("auto", "manual"):
        return {"error": "Mode must be 'auto' or 'manual'"}

    config.AUTO_MODE = (mode == "auto")
    label = "Autonomous" if config.AUTO_MODE else "Manual"
    print(f"[MODE] Switched to {label}")

    # Full context reset on mode switch
    incident_context.update(
        pod=None,
        anomaly=None,
        logs=None,
        rca=None,
        confidence=None,
        action=None,
        status=None,
        outcome=None,
        manual_restart=False,
        auto_healed=False,
    )

    return {"mode": label}

# ---------------------------
# 📋 INCIDENT CONTEXT
# ---------------------------
@app.get("/context")
def get_context():
    return incident_context


# ---------------------------
# ✅ HUMAN APPROVAL ENDPOINT
# ---------------------------
@app.post("/approve/{pod_name}")
def approve_heal(pod_name: str):
    """
    Human approval for low-confidence cases in AUTO MODE.
    Deletes the pod; monitor detects recovery and labels it 'Human-approved restart'.
    """
    try:
        v1.delete_namespaced_pod(name=pod_name, namespace="default")
        incident_context.update(
            pod=pod_name,
            action="Approved by human — restarting",
            status="Healing",
            outcome="Human-approved restart",
            manual_restart=False,   # not a /restart call
            auto_healed=False,      # not autonomous either; monitor will label correctly
        )
        return {"message": f"{pod_name} restart approved and triggered"}
    except Exception as e:
        return {"error": str(e)}
