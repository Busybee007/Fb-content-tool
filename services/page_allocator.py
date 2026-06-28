import math
from collections import defaultdict
from datetime import date, timedelta

TYPE_KEYS = ["mass", "thanh ly", "mo ban", "order"]
DEFAULT_TYPE_RATIOS = {"mass": 50.0, "thanh ly": 20.0, "mo ban": 20.0, "order": 10.0}

# Products per day defaults
DEFAULT_PER_DAY = 12
MIN_PER_DAY = 10
MAX_PER_DAY = 15
DAYS = 7


def _uu_tien_sort(p):
    try:
        return int(p.get("uu_tien") or 2)
    except (ValueError, TypeError):
        return 2


def _select_by_ratios(pool_by_key, ratios, total_slots):
    """Select `total_slots` items from pools according to ratios dict."""
    ratio_sum = sum(float(v) for v in ratios.values()) or 100
    selected = []
    remaining = total_slots

    for key in sorted(ratios, key=lambda k: float(ratios[k]), reverse=True):
        if remaining <= 0:
            break
        pool = pool_by_key.get(key, [])
        if not pool:
            continue
        quota = min(len(pool), max(1, math.floor(total_slots * float(ratios[key]) / ratio_sum)))
        quota = min(quota, remaining)
        selected.extend(pool[:quota])
        pool_by_key[key] = pool[quota:]
        remaining -= quota

    # Fill remaining from leftovers
    if remaining > 0:
        leftover = [p for pool in pool_by_key.values() for p in pool]
        leftover.sort(key=_uu_tien_sort)
        selected.extend(leftover[:remaining])

    return selected


def allocate_page_week(products, type_ratios, category_ratios, min_price, max_price,
                       start_date: date, per_day=DEFAULT_PER_DAY, allow_repeat=False):
    """
    Allocate products for one fanpage across 7 days.

    Returns list of {product_id, slot_date (str), slot_order}.
    When allow_repeat=False products are de-duplicated within the week.
    When allow_repeat=True the pool is cycled to fill all slots.
    """
    per_day = max(MIN_PER_DAY, min(MAX_PER_DAY, per_day))
    total_slots = DAYS * per_day

    # Filter by price
    eligible = [
        p for p in products
        if min_price <= float(p.get("gia_ban") or 0) <= max_price
    ]
    if not eligible:
        return []

    # Tier 1: by chiến lược (loại hàng)
    by_type = defaultdict(list)
    for p in eligible:
        key = str(p.get("chien_luoc") or "mass").lower().strip()
        by_type[key].append(p)
    for key in by_type:
        by_type[key].sort(key=_uu_tien_sort)

    selected_by_type = _select_by_ratios(by_type, type_ratios, total_slots)

    # Tier 2: by danh mục (category)
    by_cat = defaultdict(list)
    for p in selected_by_type:
        by_cat[p.get("danh_muc") or "Khác"].append(p)

    final = _select_by_ratios(by_cat, category_ratios, len(selected_by_type))

    if allow_repeat and final and len(final) < total_slots:
        pool = final[:]
        final = [pool[i % len(pool)] for i in range(total_slots)]

    # Distribute across 7 days
    slots = []
    for day_idx in range(DAYS):
        slot_date = (start_date + timedelta(days=day_idx)).isoformat()
        day_products = final[day_idx * per_day: (day_idx + 1) * per_day]
        for order, product in enumerate(day_products):
            slots.append({
                "product_id": product["id"],
                "slot_date": slot_date,
                "slot_order": order,
            })

    return slots
