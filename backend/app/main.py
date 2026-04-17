import threading
from threading import Lock

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
).start()

# ---------------------------
# 🏠 HOME
# ---------------------------
@app.get("/")
def home():
    return {
        "message": "KubeHeal backend running",
        "mode": "Autonomous" if config.AUTO_MODE else "Manual",
    }

# ---------------------------
# 📦 GET PODS
# ---------------------------
@app.get("/pods")
def list_pods():
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
    container_reason = None

    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace="default")
        container_reason = _container_failure_reason(pod)
    except Exception:
        pass

    logs = ""
    try:
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace="default",
            tail_lines=30,
        )
    except Exception:
        logs = ""

    # 🔥 Always show something
    if container_reason:
        logs = f"⚠ {container_reason}"

    # RCA logic
    if container_reason:
        analysis = _reason_to_analysis(container_reason)
    else:
        analysis = _scan_logs(logs)

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

# ---------------------------
# 🔁 MANUAL RESTART
# ---------------------------
@app.post("/restart/{pod_name}")
def restart_pod(pod_name: str):
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

    except Exception as e:
        return {"error": str(e)}

# ---------------------------
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
# ---------------------------
@app.get("/context")
def get_context():
    return incident_context

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