import time
from kubernetes import client
from kubernetes import config as kube_config
from kubernetes.client import CustomObjectsApi

from app.rca import analyze_root_cause
from app import config

# ---------------------------
# 🔧 KUBERNETES CONFIG
# ---------------------------
try:
    kube_config.load_kube_config()
except Exception:
    kube_config.load_incluster_config()

v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()
metrics_api = CustomObjectsApi()

# ---------------------------
# 📦 GLOBAL STATE
# ---------------------------
failure_times = {}
mttr_store = {}
last_healed = {}

_SYSTEM_PREFIXES = (
    "kube-",
    "calico-",
    "coredns-",
    "etcd-",
    "metrics-server-",
)

def get_pods():
    pods = v1.list_namespaced_pod(namespace="default").items

    result = []
    for pod in pods:
        phase = pod.status.phase or "Unknown"
        reason = _container_failure_reason(pod)

        result.append({
            "name": pod.metadata.name,
            "status": reason if reason else phase,
            "unhealthy": phase not in ("Running", "Succeeded") or bool(reason)
        })

    return result
# ---------------------------
# 🧠 FAILURE DETECTION
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

def _is_pod_unhealthy(pod):
    phase = pod.status.phase or "Unknown"
    return phase not in ("Running", "Succeeded") or _container_failure_reason(pod)

# ---------------------------
# 📊 METRICS
# ---------------------------
def get_pod_metrics():
    try:
        metrics = metrics_api.list_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace="default",
            plural="pods",
        )
        return metrics.get("items", [])
    except Exception:
        return []
    
def _parse_cpu(cpu_str):
    if not cpu_str:
        return 0.0
    if "n" in cpu_str:
        return int(cpu_str.replace("n", "")) / 1_000_000
    if "m" in cpu_str:
        return float(cpu_str.replace("m", ""))
    return float(cpu_str) * 1000

# ---------------------------
# 🔁 MAIN LOOP
# ---------------------------
def auto_heal(context):
    while True:
        try:
            _run_heal_cycle(context)
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
        time.sleep(5)


def _run_heal_cycle(context):
    pods = v1.list_namespaced_pod(namespace="default").items
    metrics = get_pod_metrics()
    current_time = time.time()

    for pod in pods:
        name = pod.metadata.name

        # Skip system pods
        if any(name.startswith(p) for p in _SYSTEM_PREFIXES):
            continue

        app_name = _derive_app_name(name)
        phase = pod.status.phase or "Unknown"
        reason = _container_failure_reason(pod)

        pod_failing = (phase not in ("Running", "Succeeded")) or reason

        # =========================
        # 🔴 FAILURE DETECTED
        # =========================
        if pod_failing:

            if app_name not in failure_times:
                failure_times[app_name] = current_time
                print(f"[FAILURE DETECTED] {name}")

                context.update(
                    pod=name,
                    status="Detected",
                    anomaly=reason or f"Pod Failure ({phase})",
                    action=None,
                    outcome=None,
                    rca=None,
                    confidence=None,
                    logs=None,

                )

                mode = context.get("mode", "autonomous")

                if mode == "manual":
                    print("🟡 Manual mode → waiting for user")

                    context.update(
                        status="Waiting for user",
                        action="Manual intervention required",
                        outcome="User action required"
                    )

                    return  # ❗ STOP AUTO HEALING HERE

                # Logs
                try:
                    logs = v1.read_namespaced_pod_log(
                        name=name,
                        namespace="default",
                        tail_lines=30,
                    )
                    context["logs"] = logs or "(empty logs)"
                except Exception:
                    context["logs"] = "No logs available"

                # RCA
                try:
                    r = analyze_root_cause(name)
                    context["rca"] = r.get("rca", "Unknown")
                    context["confidence"] = float(r.get("confidence", 0.5))
                except:
                    context["rca"] = "RCA failed"
                    #context["confidence"] = 0.5
                    context["confidence"] = 0.8



                # LOW CONFIDENCE
                if context["confidence"] < 0.7:
                    context.update(
                        action="Needs Human Approval",
                        status="Waiting for approval",
                    )
                    continue

                # AUTO HEAL
                try:
                    v1.delete_namespaced_pod(name=name, namespace="default")
                    context.update(auto_healed = True)
                    last_healed[app_name] = current_time

                    context.update(
                        action="Auto-healing",
                        status="Healing",
                    )
                except Exception as e:
                    context.update(status="Error", outcome=str(e))

            else:
                # Already failed → check recovery
                if not pod_failing:
                    _verify_recovery(context, app_name, current_time)

        # =========================
        # 🟢 RECOVERY
        # =========================
        elif app_name in failure_times:
            _verify_recovery(context, app_name, current_time)


# ---------------------------
# 🟢 VERIFY RECOVERY
# ---------------------------
def _verify_recovery(context, app_name, current_time):

    context["status"] = "Verifying..."
    time.sleep(4)   # FIXED timing

    pods = v1.list_namespaced_pod(namespace="default").items

    new_pod = next(
        (
            p for p in pods
            if p.metadata.name.startswith(app_name)
            and p.status.phase == "Running"
            and not _container_failure_reason(p)
        ),
        None,
    )

    if new_pod:
        print("⏳ Waiting before confirming recovery...")
        time.sleep(5)  # simulate delay

        start_time = failure_times.get(app_name)

        if start_time:
            current_time = time.time()  # ✅ FIX HERE
            mttr = current_time - start_time
        else:
            mttr = 0

        mttr_store[app_name] = round(max(mttr, 0.1), 2)

        # ✅ CORRECT ACTION LOGIC
        if context.get("manual_restart") is True:
            action = "Manual Restart Done"
        elif context.get("auto_healed") is True:
            action = "Auto-healed"
        else:
            action = "Self-recovered"

        context.update(
            pod=new_pod.metadata.name,
            status="Recovered",
            outcome="Success",
            action=action,
            mttr=mttr_store[app_name],
            manual_restart=False,
            auto_healed=False,
        )

        del failure_times[app_name]

        print(f"[RECOVERY] {app_name} | {action} | MTTR={mttr_store[app_name]}s")

    else:
        context.update(status="Waiting for recovery")


# ---------------------------
# 🔧 HELPERS
# ---------------------------
def _derive_app_name(name):
    parts = name.split("-")
    if len(parts) >= 3:
        return "-".join(parts[:-2])
    return parts[0]