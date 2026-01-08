from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class BillRecord:
    total_kwh: float
    total_cost_gbp: float
    standing_charge_per_day: float  # GBP/day
    start_date: date
    end_date: date
    unit_rate_p_per_kwh: Optional[float] = None  # pence/kWh if provided

@dataclass
class AssetRecord:
    asset_type: str  # e.g., "lighting", "boiler"
    capacity_kw: float
    efficiency: float  # fraction
    usage_kwh_per_day: float
    opex_per_year_gbp: float
    capex_estimate_gbp: float

@dataclass
class CustomerProfile:
    type: str  # "household" or "SME"
    postcode: str
    floor_area_m2: float
    operating_hours_per_day: float
    business_category: Optional[str] = None

@dataclass
class ActionRecommendation:
    title: str
    category: str  # "no-capex", "capex"
    capex_gbp: float
    annual_savings_gbp: float
    payback_months: float
    co2_savings_tonnes_per_year: float
    short_term_impact: str
    long_term_impact: str
    operational_disruption: str  # "Low", "Medium", "High"
    confidence: float  # 0-1
    assumptions_list: list[str]
    rule_ids_applied: list[str]

@dataclass
class RecommendationBundle:
    customer_id: str
    generated_at: str
    executive_summary: dict
    detailed: list[ActionRecommendation]
    scoring_weights: dict
    provenance: dict