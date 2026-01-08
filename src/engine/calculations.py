import math
from datetime import date
from ..schemas import BillRecord, AssetRecord

def days_in_period(bill: BillRecord) -> int:
    return (bill.end_date - bill.start_date).days or 1

def derive_unit_rate(bill: BillRecord) -> float:
    days = days_in_period(bill)
    if bill.unit_rate_p_per_kwh:
        return bill.unit_rate_p_per_kwh
    # Fallback: remove standing charge, compute average p/kWh
    standing_total = bill.standing_charge_per_day * days
    variable_cost = max(0.0, bill.total_cost_gbp - standing_total)
    if bill.total_kwh <= 0:
        return 30.0  # Conservative high rate
    return (variable_cost / bill.total_kwh) * 100.0  # pence/kWh

def calc_cost_from_unit_rate(kwh: float, unit_rate_p: float, standing_p_per_day: float, days: int) -> float:
    return (kwh * (unit_rate_p / 100.0)) + (standing_p_per_day / 100.0) * days

def lighting_retrofit_savings(current_w_per_fixture: float, new_w_per_fixture: float,
                             n_fixtures: int, hours_per_day: float, electricity_price_p_per_kwh: float) -> dict:
    daily_kwh_saved = (current_w_per_fixture - new_w_per_fixture) * n_fixtures * hours_per_day / 1000.0
    annual_kwh_saved = daily_kwh_saved * 365
    annual_savings_gbp = annual_kwh_saved * (electricity_price_p_per_kwh / 100.0)
    return {
        "annual_kwh_saved": annual_kwh_saved,
        "annual_savings_gbp": round(annual_savings_gbp, 2)
    }

def co2_from_kwh(kwh: float, grid_gco2_per_kwh: float) -> float:
    # gCO2/kWh to tonnes/year
    return (kwh * grid_gco2_per_kwh) / 1_000_000.0

def payback_months(capex_gbp: float, annual_savings_gbp: float) -> float:
    if annual_savings_gbp <= 0:
        return float('inf')
    years = capex_gbp / annual_savings_gbp
    return years * 12.0

def confidence_score(data_quality_flags: dict) -> float:
    score = 1.0
    for missing in data_quality_flags.values():
        if missing:
            score -= 0.2
    return max(0.0, round(score, 2))

# Placeholder for grid carbon lookup (hardcoded for UK average)
GRID_CARBON_UK_AVERAGE = 181  # gCO2/kWh

def get_grid_carbon(postcode: str) -> float:
    """Return an approximate grid carbon intensity based on region label.
    Accepts simple region names (UK, EU, India, Other). Defaults to UK average.
    """
    region = (postcode or "").strip().lower()
    if region == "uk":
        return 181.0
    if region == "eu":
        return 255.0
    if region == "india":
        return 650.0
    if region == "other":
        return 400.0
    # Fallback
    return GRID_CARBON_UK_AVERAGE