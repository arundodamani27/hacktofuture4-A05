<<<<<<< HEAD
monitor
import time
import requests
import threading
=======
import time
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
from kubernetes import client
from kubernetes import config as kube_config
from kubernetes.client import CustomObjectsApi

<<<<<<< HEAD
from app.orchestrator import handle_incident
from app.decision_agent import decide_action
from app.rca import analyze_root_cause
from app import config


# ---------------------------
# 📱 TELEGRAM CONFIG
# ---------------------------
TELEGRAM_TOKEN = "YOUR_TELEGRAM_API"
CHAT_ID = "YOUR_CHAT_ID"


def send_telegram_alert(context):
    message = f"""
🚨 KubeHeal Alert

Pod: {context.get('pod')}
Issue: {context.get('anomaly')}
Action Needed: HUMAN APPROVAL

Status: {context.get('status')}
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message
        })
    except Exception as e:
        print("Telegram alert failed:", e)


# 🔁 REPEAT ALERT (NEW - NON BLOCKING)
def repeat_alert(context, retries=3, delay=30):
    def alert_loop():
        for _ in range(retries):
            send_telegram_alert(context)
            time.sleep(delay)

    threading.Thread(target=alert_loop).start()


=======
from app.rca import analyze_root_cause
from app import config

>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
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
<<<<<<< HEAD
failure_counts = {}
mttr_store = {}
last_healed = {}
last_scaled = {}
memory_store = []
=======
mttr_store = {}
last_healed = {}
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d

_SYSTEM_PREFIXES = (
    "kube-",
    "calico-",
    "coredns-",
    "etcd-",
    "metrics-server-",
)

<<<<<<< HEAD
# ---------------------------
# 📦 HELPERS
# ---------------------------
def _derive_app_name(name):
    parts = name.split("-")
    if len(parts) >= 3:
        return "-".join(parts[:-2])
    return parts[0]


# ---------------------------
# 📦 GET PODS
# ---------------------------
def get_pods():
    pods = v1.list_namespaced_pod(namespace="default").items
    result = []

=======
def get_pods():
    pods = v1.list_namespaced_pod(namespace="default").items

    result = []
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
    for pod in pods:
        phase = pod.status.phase or "Unknown"
        reason = _container_failure_reason(pod)

        result.append({
            "name": pod.metadata.name,
            "status": reason if reason else phase,
            "unhealthy": phase not in ("Running", "Succeeded") or bool(reason)
        })

    return result
<<<<<<< HEAD

def get_pod_metrics():
    try:
        metrics = metrics_api.list_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace="default",
            plural="pods",
        )
        return metrics.get("items", [])
    except Exception as e:
        print("Metrics fetch error:", e)
        return []
    

def get_pod_cpu_usage(pod_name, namespace="default"):
    try:
        metrics = metrics_api.list_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace=namespace,
            plural="pods"
        )

        for item in metrics["items"]:
            if item["metadata"]["name"] == pod_name:
                cpu = item["containers"][0]["usage"]["cpu"]

                if "n" in cpu:
                    return int(cpu.replace("n", "")) / 1_000_000
                elif "m" in cpu:
                    return float(cpu.replace("m", ""))
                else:
                    return float(cpu) * 1000

        return 0

    except Exception as e:
        print("CPU fetch error:", e)
        return 0


=======
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
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
<<<<<<< HEAD
=======
        "CreateContainerConfigError",
        "InvalidImageName",
        "ContainerCannotRun",
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
    }

    for cs in pod.status.container_statuses:
        state = cs.state
<<<<<<< HEAD

=======
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
        if state is None:
            continue

        if state.waiting and state.waiting.reason in failure_reasons:
            return state.waiting.reason

        if state.terminated and state.terminated.reason in failure_reasons:
            return state.terminated.reason

    return None

<<<<<<< HEAD
=======
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
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d

# ---------------------------
# 🔁 MAIN LOOP
# ---------------------------
def auto_heal(context):
    while True:
        try:
            _run_heal_cycle(context)
        except Exception as e:
<<<<<<< HEAD
            print("[LOOP ERROR]", e)
        time.sleep(2)


# ---------------------------
# 🔁 HEAL CYCLE
# ---------------------------
def _run_heal_cycle(context):
    pods = v1.list_namespaced_pod(namespace="default").items
=======
            print(f"[LOOP ERROR] {e}")
        time.sleep(5)


def _run_heal_cycle(context):
    pods = v1.list_namespaced_pod(namespace="default").items
    metrics = get_pod_metrics()
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
    current_time = time.time()

    for pod in pods:
        name = pod.metadata.name

<<<<<<< HEAD
=======
        # Skip system pods
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
        if any(name.startswith(p) for p in _SYSTEM_PREFIXES):
            continue

        app_name = _derive_app_name(name)
<<<<<<< HEAD

        phase = pod.status.phase or "Unknown"
        reason = _container_failure_reason(pod)

        cpu_usage = get_pod_cpu_usage(name)
        print("CPU:", cpu_usage)

        high_cpu = cpu_usage > 800
        pod_failing = (phase not in ("Running", "Succeeded")) or reason

        # ---------------------------
        # 🚨 ISSUE DETECTED
        # ---------------------------
        if pod_failing or high_cpu:

            failure_counts[app_name] = failure_counts.get(app_name, 0) + 1

            if app_name not in failure_times:
                failure_times[app_name] = current_time

                context.update(
                    pod=name,
                    status="Issue Detected",
                    anomaly=reason or f"High CPU Usage ({cpu_usage}m)",
                )

                # MANUAL MODE
                if not config.AUTO_MODE:
                    context.update(
                        status="Waiting for user",
                        action="Manual intervention required"
                    )
                    return

                ##decision = decide_action("", 1.0, cpu_usage, failure_counts[app_name])
                decision ={ 
                    "action": "HUMAN APPROVAL",
                    "reason": "Testing human alert"
                }
                context["action"] = decision["action"]

                # ---------------------------
                # 🔁 SCALE
                # ---------------------------
                if decision["action"] == "SCALE":
                    context["status"] = "Scaling in progress"

                    try:
                        deployment = apps_v1.read_namespaced_deployment(
                            app_name,
                            "default"
                        )

                        current_replicas = deployment.spec.replicas or 1
                        new_replicas = current_replicas + 1

                        apps_v1.patch_namespaced_deployment_scale(
                            app_name,
                            "default",
                            {"spec": {"replicas": new_replicas}}
                        )

                        context["action"] = f"Scaled to {new_replicas} replicas"
                        context["status"] = "Scaled successfully"
                        context["outcome"] = "Success"

                    except Exception as e:
                        context["status"] = "Scaling failed"
                        context["outcome"] = str(e)

                # ---------------------------
                # 🔁 RESTART
                # ---------------------------
                elif decision["action"] == "RESTART":
                    context["status"] = "Restarting pod"

                    v1.delete_namespaced_pod(name, "default")

                    last_healed[app_name] = current_time
                    failure_counts.pop(app_name, None)

                # ---------------------------
                # 👤 HUMAN APPROVAL (UPDATED)
                # ---------------------------
                elif decision["action"] == "HUMAN_APPROVAL":
                    context["status"] = "Waiting for approval"

                    print("🚨 HUMAN INTERVENTION REQUIRED")

                    send_telegram_alert(context)   # immediate alert
                    repeat_alert(context)          # repeated alerts

                # ---------------------------
                # 🚨 ESCALATE
                # ---------------------------
                elif decision["action"] == "ESCALATE":
                    context["status"] = "Escalating to SRE"

        # ---------------------------
        # ✅ RECOVERY
        # ---------------------------
        elif app_name in failure_times:
            _verify_recovery(context, app_name)
=======
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
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d


# ---------------------------
# 🟢 VERIFY RECOVERY
# ---------------------------
<<<<<<< HEAD
def _verify_recovery(context, app_name):
    pods = v1.list_namespaced_pod(namespace="default").items

    for pod in pods:
        if pod.metadata.name.startswith(app_name) and pod.status.phase == "Running":
            context.update(
                pod=pod.metadata.name,
                status="Recovered",
                outcome="Success",
                action="Auto-healed"
            )

            failure_times.pop(app_name, None)
            break
=======
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
>>>>>>> f2279b37b579959bef7f9d50481c3f79d48bc51d
