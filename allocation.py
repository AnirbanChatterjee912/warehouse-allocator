"""
allocation.py
-------------
Core warehouse allocation engine. Implements six allocation strategies that
assign incoming product quantities to warehouse racks subject to:
    - Remaining rack volume
    - Remaining rack weight capacity
    - Storage-type compatibility (Fragile/Cold/Hazardous items must go to a
      matching rack; 'Normal' items may go into 'Normal' racks)

Each strategy returns a list of allocation result dicts plus the mutated
list of rack "state" dicts (used volume / weight) so the caller can compute
warehouse-wide optimization statistics.
"""

PRIORITY_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}


class RackState:
    """Mutable runtime state for a rack during a single allocation run."""

    def __init__(self, rack):
        self.rack_id = rack.rack_id
        self.length = rack.length
        self.width = rack.width
        self.height = rack.height
        self.max_weight = rack.max_weight
        self.rack_type = rack.rack_type
        self.capacity_volume = rack.length * rack.width * rack.height
        self.used_volume = 0.0
        self.used_weight = 0.0

    @property
    def remaining_volume(self):
        return self.capacity_volume - self.used_volume

    @property
    def remaining_weight(self):
        return self.max_weight - self.used_weight

    @property
    def utilization_pct(self):
        if self.capacity_volume == 0:
            return 0.0
        return (self.used_volume / self.capacity_volume) * 100

    def fits_type(self, product):
        """Check storage-type compatibility between a product and this rack."""
        if product["storage_type"] == "Normal":
            return self.rack_type == "Normal"
        return self.rack_type == product["storage_type"]

    def to_dict(self):
        return {
            "rack_id": self.rack_id,
            "capacity_volume": round(self.capacity_volume, 2),
            "used_volume": round(self.used_volume, 2),
            "remaining_volume": round(self.remaining_volume, 2),
            "utilization_pct": round(self.utilization_pct, 2),
            "max_weight": self.max_weight,
            "used_weight": round(self.used_weight, 2),
            "remaining_weight": round(self.remaining_weight, 2),
            "rack_type": self.rack_type,
        }


def _max_units_that_fit(rack_state, product):
    """How many units of `product` can fit into rack_state given volume & weight limits."""
    unit_volume = product["length"] * product["width"] * product["height"]
    unit_weight = product["weight"]

    if unit_volume <= 0:
        return 0

    by_volume = int(rack_state.remaining_volume // unit_volume)
    by_weight = int(rack_state.remaining_weight // unit_weight) if unit_weight > 0 else by_volume
    return max(0, min(by_volume, by_weight))


def _allocate_product_across_racks(product, rack_states, rack_order_fn):
    """
    Try to allocate a product's full quantity, splitting across racks if needed.
    `rack_order_fn(remaining_qty)` returns the ordered list of candidate rack
    states to attempt for the current remaining quantity (algorithm-specific).

    Returns a result dict describing what happened to this product.
    """
    remaining_qty = product["quantity"]
    allocations = []  # list of (rack_id, qty)

    while remaining_qty > 0:
        candidates = [r for r in rack_order_fn(remaining_qty) if r.fits_type(product)]
        candidates = [r for r in candidates if _max_units_that_fit(r, product) > 0]

        if not candidates:
            break  # no rack can take any more of this product

        chosen = candidates[0]
        units = min(remaining_qty, _max_units_that_fit(chosen, product))
        if units <= 0:
            break

        unit_volume = product["length"] * product["width"] * product["height"]
        chosen.used_volume += units * unit_volume
        chosen.used_weight += units * product["weight"]

        allocations.append((chosen.rack_id, units))
        remaining_qty -= units

    allocated_qty = product["quantity"] - remaining_qty
    unit_volume = product["length"] * product["width"] * product["height"]

    if allocated_qty == 0:
        status = "Unallocated"
    elif remaining_qty == 0:
        status = "Allocated"
    else:
        status = "Partial"

    # Represent primary rack as the one holding the most units (for simple table display)
    primary_rack = None
    if allocations:
        primary_rack = max(allocations, key=lambda a: a[1])[0]

    return {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "rack_id": primary_rack,
        "rack_breakdown": allocations,  # full split, in case product spans multiple racks
        "allocated_quantity": allocated_qty,
        "total_quantity": product["quantity"],
        "allocated_volume": allocated_qty * unit_volume,
        "allocated_weight": allocated_qty * product["weight"],
        "priority": product["priority"],
        "storage_type": product["storage_type"],
        "status": status,
    }


def _first_fit_order(rack_states):
    return lambda remaining_qty: rack_states


def _best_fit_order(rack_states):
    # Tightest fit first: rack with the smallest remaining volume that can still hold something
    def order(remaining_qty):
        return sorted(rack_states, key=lambda r: r.remaining_volume)
    return order


def _worst_fit_order(rack_states):
    # Loosest fit first: rack with the largest remaining volume
    def order(remaining_qty):
        return sorted(rack_states, key=lambda r: -r.remaining_volume)
    return order


def _weight_balanced_order(rack_states):
    # Rack with the lowest current weight-utilization ratio goes first
    def order(remaining_qty):
        def ratio(r):
            return (r.used_weight / r.max_weight) if r.max_weight > 0 else 1.0
        return sorted(rack_states, key=ratio)
    return order


def run_allocation(products, racks, algorithm):
    """
    Execute the chosen allocation algorithm.

    Args:
        products: list[dict] parsed/validated product rows
        racks:    list[Rack] SQLAlchemy Rack objects (active racks)
        algorithm: one of the keys in Config.ALGORITHMS

    Returns:
        (results: list[dict], rack_states: list[RackState])
    """
    rack_states = [RackState(r) for r in racks]

    if algorithm == "first_fit":
        ordered_products = list(products)
        order_fn = _first_fit_order(rack_states)

    elif algorithm == "best_fit":
        ordered_products = list(products)
        order_fn = _best_fit_order(rack_states)

    elif algorithm == "worst_fit":
        ordered_products = list(products)
        order_fn = _worst_fit_order(rack_states)

    elif algorithm == "priority_based":
        ordered_products = sorted(
            products, key=lambda p: -PRIORITY_WEIGHT.get(p["priority"], 0)
        )
        order_fn = _first_fit_order(rack_states)

    elif algorithm == "space_optimized":
        # Largest volume first (classic decreasing bin-packing heuristic), then best-fit
        ordered_products = sorted(
            products, key=lambda p: -(p["length"] * p["width"] * p["height"] * p["quantity"])
        )
        order_fn = _best_fit_order(rack_states)

    elif algorithm == "weight_balanced":
        ordered_products = list(products)
        order_fn = _weight_balanced_order(rack_states)

    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    results = []
    for product in ordered_products:
        result = _allocate_product_across_racks(product, rack_states, order_fn)
        results.append(result)

    return results, rack_states


def compute_statistics(results, rack_states):
    """Aggregate warehouse-wide statistics from an allocation run."""
    total_volume = sum(r.capacity_volume for r in rack_states)
    occupied_volume = sum(r.used_volume for r in rack_states)
    unused_volume = total_volume - occupied_volume
    space_utilization = (occupied_volume / total_volume * 100) if total_volume else 0

    avg_rack_utilization = (
        sum(r.utilization_pct for r in rack_states) / len(rack_states) if rack_states else 0
    )

    total_weight_capacity = sum(r.max_weight for r in rack_states)
    total_weight_used = sum(r.used_weight for r in rack_states)
    weight_utilization = (
        (total_weight_used / total_weight_capacity * 100) if total_weight_capacity else 0
    )

    # Priority score: weighted fraction of quantity successfully allocated,
    # where High priority items count 3x, Medium 2x, Low 1x.
    weighted_total = 0.0
    weighted_allocated = 0.0
    for r in results:
        w = PRIORITY_WEIGHT.get(r["priority"], 1)
        weighted_total += w * r["total_quantity"]
        weighted_allocated += w * r["allocated_quantity"]
    priority_score = (weighted_allocated / weighted_total * 100) if weighted_total else 0

    allocated_products = sum(1 for r in results if r["status"] == "Allocated")
    partial_products = sum(1 for r in results if r["status"] == "Partial")
    unallocated_products = sum(1 for r in results if r["status"] == "Unallocated")

    return {
        "total_volume": total_volume,
        "occupied_volume": occupied_volume,
        "unused_volume": unused_volume,
        "space_utilization": space_utilization,
        "avg_rack_utilization": avg_rack_utilization,
        "weight_utilization": weight_utilization,
        "priority_score": priority_score,
        "allocated_products": allocated_products,
        "partial_products": partial_products,
        "unallocated_products": unallocated_products,
    }
