# UK-specific rules and heuristics

UK_HEAT_PUMP_ELIGIBILITY = {
    "min_floor_area_m2": 50,
    "max_age_years": 20,  # Building age
    "grants_available": True
}

def is_heat_pump_eligible(profile, asset):
    # Simple check
    if profile.floor_area_m2 < UK_HEAT_PUMP_ELIGIBILITY["min_floor_area_m2"]:
        return False, "Floor area too small"
    return True, ""

def apply_conservative_defaults(missing_fields: dict) -> dict:
    defaults = {
        "usage_kwh_per_day": 10.0,  # Conservative low
        "efficiency": 0.8,
        "operating_hours_per_day": 8.0
    }
    for field, default in defaults.items():
        if field in missing_fields and missing_fields[field]:
            missing_fields[field] = False  # Mark as filled
            # In real code, set the value in data
    return missing_fields

def get_rule_ids_for_action(action_title: str) -> list[str]:
    # Placeholder mapping
    rules = {
        "LED Lighting Retrofit": ["rule-uk-lighting-efficiency-2024"],
        "Heat Pump Installation": ["rule-uk-heatpump-elig-2024", "rule-uk-grants-bus-2024"]
    }
    return rules.get(action_title, [])


def industry_multipliers(industry: str) -> dict:
    """Return simple multipliers to reflect sectoral differences.
    Applied to annual savings for actions; values are conservative.
    """
    key = (industry or "").strip().lower()
    if key == "horeca":
        return {"lighting": 1.15, "hvac": 1.10, "solar": 1.00}
    if key == "office":
        return {"lighting": 1.10, "hvac": 1.20, "solar": 1.00}
    if key == "retail":
        return {"lighting": 1.12, "hvac": 1.10, "solar": 1.05}
    return {"lighting": 1.00, "hvac": 1.00, "solar": 1.00}