def decide_action(rca, confidence, cpu_usage=0, failure_count=0):
    """
    Strong SRE-level decision engine
    """

    rca = (rca or "").lower()

    # 🚨 PRIORITY 1: High CPU → SCALE immediately
    if cpu_usage > 80:
        return {
            "action": "SCALE",
            "reason": "High CPU usage detected"
        }

    # 🚨 PRIORITY 2: Repeated failures → ESCALATE
    if failure_count >= 3:
        return {
            "action": "ESCALATE",
            "reason": "Repeated failures detected"
        }

    # 🚨 PRIORITY 3: Critical failures → RESTART
    if any(keyword in rca for keyword in [
        "crashloopbackoff",
        "crash",
        "error",
        "failed",
        "backoff"
    ]):
        return {
            "action": "RESTART",
            "reason": "Pod failure detected"
        }

    # 🚨 PRIORITY 4: Memory issues
    if "memory" in rca or "oom" in rca:
        return {
            "action": "RESTART",
            "reason": "Memory issue detected"
        }

    # ⚠ PRIORITY 5: Low confidence → HUMAN
    if confidence < 0.6:
        return {
            "action": "HUMAN_APPROVAL",
            "reason": "Low confidence RCA"
        }

    # ✅ SAFE DEFAULT → RESTART (self-healing mindset)
    return {
        "action": "RESTART",
        "reason": "Fallback recovery action"
    }