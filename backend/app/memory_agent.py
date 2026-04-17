memory_store = {}


def record_failure(pod_name):
    memory_store[pod_name] = memory_store.get(pod_name, 0) + 1
    return memory_store[pod_name]


def reset_failure(pod_name):
    if pod_name in memory_store:
        del memory_store[pod_name]


def get_failure_count(pod_name):
    return memory_store.get(pod_name, 0)