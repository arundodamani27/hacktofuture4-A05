import time
from kubernetes import client, config

# ---------------------------
# 🔧 KUBERNETES CONFIG
# ---------------------------
try:
    config.load_kube_config()
except:
    config.load_incluster_config()

v1 = client.CoreV1Api()

# ---------------------------
# 🔁 RESTART POD (SMART)
# ---------------------------
def restart_pod(pod_name, namespace="default"):
    try:
        # Check pod exists
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

        phase = pod.status.phase

        # 🔍 Skip if already healthy
        if phase == "Running":
            return {
                "status": "skipped",
                "message": f"{pod_name} already running"
            }

        # 🔥 Delete pod
        v1.delete_namespaced_pod(
            name=pod_name,
            namespace=namespace
        )

        # 🔍 Wait for new pod
        for _ in range(10):  # max ~10 seconds
            time.sleep(1)

            pods = v1.list_namespaced_pod(namespace=namespace).items

            new_pod = next(
                (p for p in pods if pod_name.split("-")[0] in p.metadata.name),
                None
            )

            if new_pod and new_pod.status.phase == "Running":
                return {
                    "status": "success",
                    "message": f"{pod_name} restarted successfully"
                }

        # ⏱ Timeout case
        return {
            "status": "timeout",
            "message": "Pod restart initiated but not yet running"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }