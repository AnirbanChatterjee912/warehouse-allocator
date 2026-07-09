"""
optimizer.py
------------
Bonus "AI Recommendation" module. Uses rule-based heuristics over the
uploaded dataset's statistical profile (size variance, weight variance,
priority mix, fragile/cold ratio) to recommend:
    - The best-suited allocation strategy
    - An expected utilization estimate
    - Likely bottlenecks
    - A simple future storage growth prediction

This is deliberately transparent/rule-based (no external ML dependency)
so it runs instantly and deterministically, while still being adaptive
to the shape of the uploaded data.
"""

import numpy as np


def _safe_std(values):
    if len(values) < 2:
        return 0.0
    return float(np.std(values))


def _safe_mean(values):
    if not values:
        return 0.0
    return float(np.mean(values))


def recommend_strategy(products, racks):
    """
    Analyze the product dataset and return an AI recommendation dict.
    """
    if not products:
        return {
            "recommended_algorithm": None,
            "reason": "No valid products to analyze.",
            "expected_utilization": 0,
            "bottlenecks": [],
            "future_prediction": "Upload a dataset to generate a prediction.",
        }

    volumes = [p["length"] * p["width"] * p["height"] for p in products]
    weights = [p["weight"] for p in products]
    quantities = [p["quantity"] for p in products]

    volume_std = _safe_std(volumes)
    volume_mean = _safe_mean(volumes)
    weight_std = _safe_std(weights)
    weight_mean = _safe_mean(weights)

    volume_cv = (volume_std / volume_mean) if volume_mean else 0  # coefficient of variation
    weight_cv = (weight_std / weight_mean) if weight_mean else 0

    high_priority_ratio = sum(1 for p in products if p["priority"] == "High") / len(products)
    special_storage_ratio = sum(
        1 for p in products if p["storage_type"] != "Normal"
    ) / len(products)

    # --- Decide best algorithm using simple weighted rules ---
    scores = {
        "first_fit": 0.4,          # baseline / fallback
        "best_fit": 0.5,
        "worst_fit": 0.2,
        "priority_based": 0.4,
        "space_optimized": 0.4,
        "weight_balanced": 0.4,
    }

    if volume_cv > 0.5:
        scores["space_optimized"] += 0.4  # highly varied item sizes -> pack largest first
        scores["best_fit"] += 0.15
    else:
        scores["first_fit"] += 0.15

    if weight_cv > 0.5:
        scores["weight_balanced"] += 0.45  # highly varied weights -> balance load
    else:
        scores["weight_balanced"] += 0.05

    if high_priority_ratio > 0.35:
        scores["priority_based"] += 0.4  # many urgent items -> prioritize placement

    if special_storage_ratio > 0.4:
        scores["best_fit"] += 0.15  # lots of special racks needed -> use space tightly

    best_algorithm = max(scores, key=scores.get)

    reason_parts = []
    if volume_cv > 0.5:
        reason_parts.append("high variation in product sizes")
    if weight_cv > 0.5:
        reason_parts.append("high variation in product weights")
    if high_priority_ratio > 0.35:
        reason_parts.append(f"{high_priority_ratio*100:.0f}% of products are High priority")
    if special_storage_ratio > 0.4:
        reason_parts.append(f"{special_storage_ratio*100:.0f}% require special storage")
    if not reason_parts:
        reason_parts.append("a fairly uniform, low-variance dataset")

    reason = "Recommended based on: " + "; ".join(reason_parts) + "."

    # --- Expected utilization estimate (heuristic, not a guarantee) ---
    total_capacity = sum(r.length * r.width * r.height for r in racks) if racks else 0
    total_demand = sum(v * q for v, q in zip(volumes, quantities))
    expected_utilization = min(100.0, (total_demand / total_capacity * 100) if total_capacity else 0)

    # --- Bottleneck detection ---
    bottlenecks = []
    type_counts = {}
    for p in products:
        type_counts[p["storage_type"]] = type_counts.get(p["storage_type"], 0) + p["quantity"]

    rack_type_capacity = {}
    for r in racks:
        rack_type_capacity[r.rack_type] = rack_type_capacity.get(r.rack_type, 0) + (r.length * r.width * r.height)

    for storage_type, qty in type_counts.items():
        avg_vol = _safe_mean(
            [p["length"] * p["width"] * p["height"] for p in products if p["storage_type"] == storage_type]
        )
        demand_vol = avg_vol * qty
        capacity = rack_type_capacity.get(storage_type, 0)
        if capacity == 0 and demand_vol > 0:
            bottlenecks.append(f"No active rack of type '{storage_type}' exists, but products require it.")
        elif capacity and demand_vol / capacity > 0.85:
            bottlenecks.append(
                f"'{storage_type}' racks are projected to exceed 85% capacity ({demand_vol/capacity*100:.0f}%)."
            )

    if expected_utilization > 90:
        bottlenecks.append("Overall warehouse space is projected to exceed 90% utilization.")

    if not bottlenecks:
        bottlenecks.append("No significant bottlenecks detected for this dataset.")

    # --- Future storage growth prediction (simple linear heuristic) ---
    if expected_utilization >= 85:
        future_prediction = (
            "At current growth, the warehouse may run out of space soon. "
            "Consider adding racks or increasing capacity within the next cycle."
        )
    elif expected_utilization >= 60:
        future_prediction = (
            "Utilization is moderate. Space should remain sufficient for the next "
            "few incoming shipments if volumes stay similar."
        )
    else:
        future_prediction = (
            "Utilization is low. The warehouse has ample room for growth in "
            "upcoming shipments."
        )

    return {
        "recommended_algorithm": best_algorithm,
        "reason": reason,
        "expected_utilization": round(expected_utilization, 2),
        "bottlenecks": bottlenecks,
        "future_prediction": future_prediction,
        "volume_cv": round(volume_cv, 3),
        "weight_cv": round(weight_cv, 3),
        "high_priority_ratio": round(high_priority_ratio * 100, 1),
        "special_storage_ratio": round(special_storage_ratio * 100, 1),
    }
