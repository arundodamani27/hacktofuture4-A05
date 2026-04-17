from app.rca import analyze_root_cause
from app.remediation import restart_pod
from app.decision_agent import decide_action
from app.memory_agent import record_failure, get_failure_count


def handle_incident(pod_name: str):
    
    # 1. Record failure
    count = record_failure(pod_name)

    # 2. Get RCA
    result = analyze_root_cause(pod_name)
    rca = result.get("rca", "Unknown")
    confidence = result.get("confidence", 0.5)

    # 3. Decide action
    action = decide_action(rca, confidence, count)

    # 4. Execute action
    success = False

    if action == "RESTART":
        success = restart_pod(pod_name)

    elif action == "SCALE":
        print(f"[ACTION] Suggest scaling for {pod_name}")

    elif action == "HUMAN_APPROVAL":
        print(f"[ACTION] Waiting for human approval")

    # 5. Return full decision
    return {
        "pod": pod_name,
        "rca": rca,
        "confidence": confidence,
        "action": action,
        "failure_count": count,
        "success": success,
    }