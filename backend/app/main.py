import threading
<<<<<<< HEAD
from threading import Lock
=======
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d

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

<<<<<<< HEAD
v1 = client.CoreV1Api()
metrics_api = CustomObjectsApi()

# ---------------------------
# 🧠 SHARED INCIDENT CONTEXT
# ---------------------------
incident_context = {
    "pod": None,
    "anomaly": None,
    "logs": None,
    "rca": None,
    "confidence": None,
    "action": None,
    "status": None,
    "outcome": None,
    "manual_restart": False,
    "auto_healed": False,
}

context_lock = Lock()

=======
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

>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
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
<<<<<<< HEAD
).start()

=======
    name="auto-heal-loop",
).start()


>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
# ---------------------------
# 🏠 HOME
# ---------------------------
@app.get("/")
def home():
    return {
        "message": "KubeHeal backend running",
<<<<<<< HEAD
        "mode": "Autonomous" if config.AUTO_MODE else "Manual",
    }

=======
        "mode":    "Autonomous" if config.AUTO_MODE else "Manual",
    }
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
# ---------------------------
# 📦 GET PODS
# ---------------------------
@app.get("/pods")
def list_pods():
<<<<<<< HEAD
    return get_pods()

=======
    """
    Returns all non-system pods with an enriched 'status' field that reflects
    container-level failures (CrashLoopBackOff, ImagePullBackOff, etc.)
    rather than just pod phase.
    """
    return get_pods()


>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
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

<<<<<<< HEAD
=======

>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
# ---------------------------
# 🧠 ANALYZE POD
# ---------------------------
@app.get("/analyze/{pod_name}")
def analyze_pod(pod_name: str):
<<<<<<< HEAD
    container_reason = None

=======
    """
    On-demand analysis triggered by the user.
    Inspects container_statuses first for precise detection, then falls back
    to log-keyword scanning.
    """
    # 1. Fetch pod object to check container statuses
    container_reason: str | None = None
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace="default")
        container_reason = _container_failure_reason(pod)
    except Exception:
<<<<<<< HEAD
        pass

=======
        pass  # pod may not exist yet; proceed to log scan

    # 2. Fetch logs
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
    logs = ""
    try:
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace="default",
            tail_lines=30,
        )
<<<<<<< HEAD
    except Exception:
        logs = ""

    # 🔥 Always show something
    if container_reason:
        logs = f"⚠ {container_reason}"

    # RCA logic
=======
    except Exception as e:
        logs = f"Could not fetch logs: {e}"

    # 3. Determine analysis
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
    if container_reason:
        analysis = _reason_to_analysis(container_reason)
    else:
        analysis = _scan_logs(logs)

<<<<<<< HEAD
    # 🔥 Confidence logic
    confidence_map = {
        "CrashLoopBackOff": 0.85,
        "ImagePullBackOff": 0.9,
        "ErrImagePull": 0.9,
        "OOMKilled": 0.95,
    }

    confidence = confidence_map.get(container_reason, 0.6)

    with context_lock:
        incident_context.update(
            pod=pod_name,
            rca=analysis,
            logs=logs or "No logs, but system detected issue",
            confidence=confidence,
        )

    return {
        "analysis": analysis,
        "logs": logs or "No logs, but system detected issue",
        "confidence": confidence,
    }

# ---------------------------
# 🔍 FAILURE REASON
# ---------------------------
def _container_failure_reason(pod):
=======
    incident_context.update(
        pod=pod_name,
        rca=analysis,
        logs=logs or "(empty logs)",
    )

    return {"analysis": analysis, "logs": logs}


def _container_failure_reason(pod) -> str | None:
    """Mirror of monitor.py helper — avoids importing across packages."""
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
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
<<<<<<< HEAD

=======
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
    for cs in pod.status.container_statuses:
        state = cs.state
        if state is None:
            continue
        if state.waiting and state.waiting.reason in failure_reasons:
            return state.waiting.reason
        if state.terminated and state.terminated.reason in failure_reasons:
            return state.terminated.reason
<<<<<<< HEAD

    return None

# ---------------------------
# 🧠 RCA MAPPING
# ---------------------------
def _reason_to_analysis(reason: str) -> str:
    mapping = {
        "CrashLoopBackOff": "Application crash loop detected",
        "ImagePullBackOff": "Invalid or missing container image",
        "ErrImagePull": "Error pulling container image",
        "OOMKilled": "Container exceeded memory limits",
    }
    return mapping.get(reason, f"Container failure: {reason}")

# ---------------------------
# 📜 LOG SCAN
# ---------------------------
def _scan_logs(logs: str) -> str:
    logs_lower = logs.lower()

    if "oomkilled" in logs_lower:
        return "Memory limit exceeded"
    if "crash" in logs_lower:
        return "Application crash detected"
    if "imagepull" in logs_lower:
        return "Image pull failure"
    if "error" in logs_lower:
        return "Application error detected"

    return "Potential issue detected but insufficient data"

# ---------------------------
# 💥 INJECT FAILURE
# ---------------------------
@app.post("/inject-failure/{pod_name}")
def inject_failure(pod_name: str):
    try:
        v1.delete_namespaced_pod(name=pod_name, namespace="default")

        with context_lock:
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

        return {"message": f"Failure injected: {pod_name}"}

    except Exception as e:
        return {"error": str(e)}

=======
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


>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
# ---------------------------
# 🔁 MANUAL RESTART
# ---------------------------
@app.post("/restart/{pod_name}")
def restart_pod(pod_name: str):
<<<<<<< HEAD
    if config.AUTO_MODE:
        return {"error": "Disabled in auto mode"}

    try:
        v1.delete_namespaced_pod(name=pod_name, namespace="default")

        with context_lock:
            incident_context.update(
                pod=pod_name,
                action="Manual restart",
                status="Restarting",
                manual_restart=True,
            )

        return {"message": "Restart triggered"}

=======
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
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
    except Exception as e:
        return {"error": str(e)}

# ---------------------------
<<<<<<< HEAD
# 🤖 MODE SWITCH
# ---------------------------
@app.post("/mode/{mode}")
def set_mode(mode: str):
    config.AUTO_MODE = (mode == "auto")

    with context_lock:
        incident_context.clear()

    return {"mode": "Autonomous" if config.AUTO_MODE else "Manual"}

# ---------------------------
# 📋 CONTEXT
=======
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
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
# ---------------------------
@app.get("/context")
def get_context():
    return incident_context

<<<<<<< HEAD
# ---------------------------
# ✅ APPROVAL
# ---------------------------
@app.post("/approve/{pod_name}")
def approve_heal(pod_name: str):
    try:
        v1.delete_namespaced_pod(name=pod_name, namespace="default")

        with context_lock:
            incident_context.update(
                pod=pod_name,
                action="Approved restart",
                status="Healing",
                outcome="Human-approved",
            )

        return {"message": "Approved"}

    except Exception as e:
        return {"error": str(e)}
=======

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
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
