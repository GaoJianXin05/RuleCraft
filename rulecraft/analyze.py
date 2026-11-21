"""Two-level bootstrap used by every analysis: resample rules, then the questions within each drawn rule."""
import random

B = 2000


def cluster_ci(values_by_rule, seed=0):
    """values_by_rule: {rule: [0/1, ...]} -> (mean, lo, hi), resampling rules then items within rules."""
    rules = [r for r, v in values_by_rule.items() if v]
    if not rules:
        return None
    flat = [x for r in rules for x in values_by_rule[r]]
    mean = sum(flat) / len(flat)
    rng = random.Random(seed)
    stats = []
    for _ in range(B):
        sample = []
        for r in rng.choices(rules, k=len(rules)):
            v = values_by_rule[r]
            sample += rng.choices(v, k=len(v))
        stats.append(sum(sample) / len(sample))
    stats.sort()
    return mean, stats[int(0.025 * B)], stats[int(0.975 * B) - 1]


def fmt(ci):
    return "—" if ci is None else f"{100 * ci[0]:.1f} [{100 * ci[1]:.1f}, {100 * ci[2]:.1f}]"
