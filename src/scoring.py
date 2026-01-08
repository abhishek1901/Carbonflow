from .schemas import ActionRecommendation

def compute_score(action: ActionRecommendation, weights=None) -> float:
    if weights is None:
        weights = {"roi": 0.6, "carbon": 0.2, "disruption": 0.1, "confidence": 0.1}
    capex = max(action.capex_gbp or 0.0, 1.0)  # Avoid div by zero
    roi_metric = action.annual_savings_gbp / capex
    roi_score = min(1.0, roi_metric / 1.0)  # Cap at 1 for 100% annual ROI

    carbon_score = min(1.0, action.co2_savings_tonnes_per_year / 1.0)

    disruption_map = {"Low": 1.0, "Medium": 0.6, "High": 0.2}
    disruption_score = disruption_map.get(action.operational_disruption, 0.6)

    confidence = action.confidence

    raw_score = (weights["roi"] * roi_score +
                 weights["carbon"] * carbon_score +
                 weights["disruption"] * disruption_score +
                 weights["confidence"] * confidence)
    # Hard rule: if payback >24 months and carbon <1t, penalize
    if action.payback_months and action.payback_months > 24 and action.co2_savings_tonnes_per_year < 1.0:
        raw_score *= 0.5
    return round(raw_score, 3)

def rank_actions(actions: list[ActionRecommendation], weights=None) -> list[ActionRecommendation]:
    scored = [(compute_score(a, weights), a) for a in actions]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored]

def filter_feasible(actions: list[ActionRecommendation]) -> list[ActionRecommendation]:
    # Placeholder: exclude if payback inf or negative savings
    return [a for a in actions if a.payback_months != float('inf') and a.annual_savings_gbp > 0]