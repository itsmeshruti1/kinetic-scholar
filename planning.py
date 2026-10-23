"""Bounded, deterministic scheduling rules; no machine-learning claims."""

from math import ceil


def allocate(total, weights):
    """Largest-remainder allocation: nonnegative integers summing exactly to total."""
    if not weights:
        return []
    denominator = sum(weights)
    result = [total * weight // denominator for weight in weights]
    order = sorted(range(len(weights)), key=lambda i: (-(total * weights[i] % denominator), i))
    for i in order[: total - sum(result)]:
        result[i] += 1
    return result


def suggest_distribution(subjects):
    values = allocate(100, [s["importance"] for s in subjects])
    return [{"subject_id": s["id"], "percent": value} for s, value in zip(subjects, values)]


def build_plan(subjects, total_minutes, mode="balanced"):
    """Recovery is included in the budget; rotate subjects between bounded blocks."""
    if not subjects:
        raise ValueError("Add an active subject before creating a plan.")
    block_size = 40 if mode == "exam" else 25
    block_count = ceil((total_minutes + 5) / (block_size + 5))
    study_minutes = total_minutes - (block_count - 1) * 5
    durations = allocate(study_minutes, [1] * block_count)
    weights = [s["importance"] ** (2 if mode == "exam" else 1) for s in subjects]
    credits = [0] * len(subjects)
    blocks = []
    previous = None
    offset = 0
    for index, duration in enumerate(durations):
        credits = [credit + weight for credit, weight in zip(credits, weights)]
        candidates = [i for i in range(len(subjects)) if i != previous] or [0]
        chosen = max(candidates, key=lambda i: credits[i])
        credits[chosen] -= sum(weights)
        subject = subjects[chosen]
        blocks.append(
            {
                "type": "study",
                "subject_id": subject["id"],
                "subject": subject["name"],
                "minutes": duration,
                "offset_minutes": offset,
            }
        )
        offset += duration
        previous = chosen
        if index < block_count - 1:
            blocks.append({"type": "break", "subject": "Step away & recharge", "minutes": 5, "offset_minutes": offset})
            offset += 5
    return {
        "mode": mode,
        "total_minutes": total_minutes,
        "study_minutes": study_minutes,
        "break_minutes": total_minutes - study_minutes,
        "blocks": blocks,
    }
