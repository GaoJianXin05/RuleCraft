"""Bootstrap interval for paired differences, which may be negative."""
from analyze import cluster_ci


def shift_ci(d):
    """CI for values that may be negative (paired differences)."""
    ci = cluster_ci({k: [x + 1 for x in v] for k, v in d.items()})
    return None if ci is None else (ci[0] - 1, ci[1] - 1, ci[2] - 1)
