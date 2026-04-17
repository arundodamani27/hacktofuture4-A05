from kubernetes import client, config
from dotenv import load_dotenv
import google.generativeai as genai
import os, json, re

# ---------------------------
# 🔧 LOAD CONFIG
# ---------------------------
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

try:
    config.load_kube_config() 
except:
    config.load_incluster_config()

v1 = client.CoreV1Api()
client_ai = genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ---------------------------
# 📜 GET POD LOGS
# ---------------------------
def get_pod_logs(pod_name, namespace="default"):
    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

        phase = pod.status.phase

        if phase != "Running":
            statuses = pod.status.container_statuses
            if statuses:
                state = statuses[0].state
                if state.waiting:
                    return f"Waiting: {state.waiting.reason}"
                if state.terminated:
                    return f"Terminated: {state.terminated.reason}"

            return f"Pod not running ({phase})"

        return v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=20
        )

    except Exception as e:
        return f"Log error: {str(e)}"

# ---------------------------
# ⚡ QUICK DETECTION
# ---------------------------
def quick_detect(logs):
    logs_lower = logs.lower()

    if "oomkilled" in logs_lower:
        return {"rca": "Memory limit exceeded", "confidence": 0.9}
    if "imagepullbackoff" in logs_lower:
        return {"rca": "Image pull failed", "confidence": 0.9}
    if "crashloopbackoff" in logs_lower:
        return {"rca": "Application crash loop", "confidence": 0.85}

    return None




def rule_based_rca(logs):
    logs = logs.lower()

    if "oomkilled" in logs:
        return "OOMKilled", 0.9

    if "crashloopbackoff" in logs:
        return "CrashLoopBackOff", 0.85

    if "imagepullbackoff" in logs:
        return "ImagePullError", 0.9

    return None, None
# ---------------------------
# 🧠 RCA ANALYSIS
# ---------------------------
def analyze_root_cause(pod_name, namespace="default"):

    logs = get_pod_logs(pod_name, namespace)

    # 🔥 FAST PATH
    quick = quick_detect(logs)
    if quick:
        return quick

    try:
        prompt = f"""
You are a Kubernetes SRE.

Return ONLY JSON:
{{"rca": "<max 10 words>", "confidence": <0-1>}}

If unclear:
{{"rca": "Possible configuration or resource issue", "confidence": 0.5}}

LOGS:
{logs}
"""

        response = client_ai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = re.sub(r"```json|```", "", response.text).strip()

        try:
            data = json.loads(text)
            return {
                "rca": data.get("rca", "Unknown issue"),
                "confidence": float(data.get("confidence", 0.5))
            }
        except:
            return {"rca": text[:80], "confidence": 0.5}

    except Exception as e:
        return {
            "rca": "AI unavailable — fallback used",
            "confidence": 0.4
        }