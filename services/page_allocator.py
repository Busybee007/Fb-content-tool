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
    """Select `total_slots` items from pools according to ratios dict.
    Mutates pool_by_key by consuming selected items.
    """
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
        # Remove consumed leftovers from pools
        consumed = set(id(p) for p in leftover[:remaining])
        for key in pool_by_key:
            pool_by_key[key] = [p for p in pool_by_key[key] if id(p) not in consumed]

    return selected


def _select_day(by_type, type_ratios, category_ratios, per_day):
    """Pick per_day products for a single day using two-tier ratio selection.
    Pools (by_type) are mutated — consumed items are removed so the next day
    picks from what remains.
    """
    # Tier 1: pick by chiến lược
    selected_by_type = _select_by_ratios(by_type, type_ratios, per_day)

    # Tier 2: pick by danh mục from the tier-1 result
    # Build a fresh per-day category pool (don't mutate the week-level pools here)
    by_cat = defaultdict(list)
    for p in selected_by_type:
        by_cat[p.get("danh_muc") or "Khác"].append(p)

    day_final = _select_by_ratios(by_cat, category_ratios, len(selected_by_type))
    return day_final


def allocate_page_week(products, type_ratios, category_ratios, min_price, max_price,
                       start_date: date, per_day=DEFAULT_PER_DAY, allow_repeat=False):
    """
    Allocate products for one fanpage across 7 days.
    Ratios are applied PER DAY so every day reflects the configured mix.

    Returns list of {product_id, slot_date (str), slot_order}.
    """
    per_day = max(1, int(per_day))

    # Filter by price
    eligible = [
        p for p in products
        if min_price <= float(p.get("gia_ban") or 0) <= max_price
    ]
    if not eligible:
        return []

    # Build week-level pools by chiến lược, sorted by priority
    by_type = defaultdict(list)
    for p in eligible:
        key = str(p.get("chien_luoc") or "mass").lower().strip()
        by_type[key].append(p)
    for key in by_type:
        by_type[key].sort(key=_uu_tien_sort)

    # When allow_repeat, cycle the eligible pool so we never run out
    if allow_repeat:
        total_slots = DAYS * per_day
        pool_size = len(eligible)
        if pool_size < total_slots:
            sorted_eligible = sorted(eligible, key=lambda p: (_uu_tien_sort(p), -float(p.get("gia_ban") or 0)))
            repeated = [sorted_eligible[i % pool_size] for i in range(total_slots)]
            by_type = defaultdict(list)
            for p in repeated:
                key = str(p.get("chien_luoc") or "mass").lower().strip()
                by_type[key].append(p)

    # Allocate per day
    slots = []
    for day_idx in range(DAYS):
        slot_date = (start_date + timedelta(days=day_idx)).isoformat()
        day_products = _select_day(by_type, type_ratios, category_ratios, per_day)
        for order, product in enumerate(day_products):
            slots.append({
                "product_id": product["id"],
                "slot_date": slot_date,
                "slot_order": order,
            })

    return slots
