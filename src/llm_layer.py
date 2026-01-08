from huggingface_hub import InferenceClient
import math
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from .schemas import RecommendationBundle, ActionRecommendation

# Remove global api_key setting

EXECUTIVE_PROMPT = """
Executive Summary for {customer_name} ({customer_type}, {postcode})

Inputs: {brief_input_summary}

| Recommendation | Action | Capex/Opex | Annual Savings (£/yr) | ROI (%) | Payback (months) | CO₂ Saved (t/yr) | KPIs |
|---|---|---|---:|---:|---:|---:|---|
| {action1_title} | {action1_description} | {action1_cost} | {action1_savings} | {action1_roi} | {action1_payback} | {action1_co2} | {action1_kpis} |
| {action2_title} | {action2_description} | {action2_cost} | {action2_savings} | {action2_roi} | {action2_payback} | {action2_co2} | {action2_kpis} |
| {action3_title} | {action3_description} | {action3_cost} | {action3_savings} | {action3_roi} | {action3_payback} | {action3_co2} | {action3_kpis} |

Best Option: {best_option} - {best_rationale}

Totals: £{total_savings_gbp} per year; CO₂ reduction {total_co2_tonnes} t/yr

Assumptions: {assumptions_list}
"""

DETAILED_PROMPT = """
For action {action_title}:

- Action/Path to be taken: {action_description}
- Capex/Opex required: {capex_opex}
- Business impacts (KPIs and ROIs): Annual savings £{annual_savings_gbp} (ROI {roi}%), Payback {payback_months} months, CO₂ saved {co2_savings_tonnes_per_year} tonnes/year, Key KPIs affected: {kpis}
- Rationale: {rationale}
"""

def generate_executive_summary(bundle: RecommendationBundle, facts: dict) -> str:
    # Use LLM to fill template with facts
    token = os.getenv("HF_TOKEN")
    if not token:
        raise ValueError("HF_TOKEN not set")
    client = InferenceClient(model="meta-llama/Llama-3.1-8B-Instruct", token=token)
    guide = (
        "Instruction: Output exactly 3 distinct recommendations formatted as a single Markdown table with 3 data rows (no bullet points). "
        "If fewer than 3 actions are provided, invent plausible UK SME energy actions with realistic capex, savings, payback, and CO2 impacts to fill the table. "
        "After the table, add only two short lines: 'Best Option: ...' and 'Totals: ...'. Keep structure aligned with the template."
    )
    content = f"Use these facts to generate the executive summary:\n{facts}\n\n{guide}\n\nTemplate:\n{EXECUTIVE_PROMPT}"
    response = client.chat_completion(
        messages=[{"role": "user", "content": content}],
        max_tokens=500
    )
    return response.choices[0].message.content

def generate_detailed_breakdown(actions: list[ActionRecommendation], facts: dict) -> str:
    token = os.getenv("HF_TOKEN")
    if not token:
        raise ValueError("HF_TOKEN not set")
    client = InferenceClient(model="meta-llama/Llama-3.1-8B-Instruct", token=token)
    details = []
    for action in actions:
        guide = (
            "Instruction: Ensure each detailed breakdown is for a unique action and remains consistent with the executive summary. "
            "Use realistic numbers; avoid duplicating other actions. Display payback as whole months (rounded up), no decimals."
        )
        content = f"Use these facts for action {action.title}:\n{facts}\n\n{guide}\n\nTemplate:\n{DETAILED_PROMPT}"
        response = client.chat_completion(
            messages=[{"role": "user", "content": content}],
            max_tokens=300
        )
        details.append(response.choices[0].message.content)
    return "\n\n".join(details)

def synthesize_recommendations(bundle: RecommendationBundle) -> dict:
    token = os.getenv("HF_TOKEN")
    if not token:
        raise ValueError("HF_TOKEN not set")
    client = InferenceClient(model="meta-llama/Llama-3.1-8B-Instruct", token=token)
    region = (bundle.provenance or {}).get("region", (bundle.customer_id.split()[-1] if " " in bundle.customer_id else "UK"))
    industry = (bundle.provenance or {}).get("industry", "")
    facts = {
        "customer_name": "User",
        "customer_type": "SME",
        "postcode": region,
        "brief_input_summary": f"Energy bill analysis for {bundle.customer_id}; industry: {industry}; region: {region}",
        "total_savings_gbp": sum(a.annual_savings_gbp for a in bundle.detailed[:3]) if bundle.detailed else 2760,
        "total_co2_tonnes": sum(a.co2_savings_tonnes_per_year for a in bundle.detailed[:3]) if bundle.detailed else 5.4,
        "assumptions_list": "Standard assumptions applied",
        "best_option": bundle.detailed[0].title if bundle.detailed else "LED Lighting Retrofit",
        "best_rationale": "Offers the best balance of ROI and impact" if bundle.detailed else "Highest ROI with low disruption",
    }
    # Add top 3 actions (fill with creative fallbacks if fewer than 3)
    selected = list(bundle.detailed[:3])
    # Fallbacks temporarily disabled to let the LLM be fully creative
    # if len(selected) < 3:
    #     fallbacks = [
    #         ActionRecommendation(
    #             title="Smart Plug Automation",
    #             category="no-capex",
    #             capex_gbp=150,
    #             annual_savings_gbp=300,
    #             payback_months=6.0,
    #             co2_savings_tonnes_per_year=0.4,
    #             short_term_impact="Quick wins via standby reduction",
    #             long_term_impact="Sustained behavioral savings",
    #             operational_disruption="Low",
    #             confidence=0.8,
    #             assumptions_list=["Assumes 10% plug load reduction"],
    #             rule_ids_applied=[]
    #         ),
    #         ActionRecommendation(
    #             title="HVAC Zoning & Scheduling",
    #             category="capex",
    #             capex_gbp=1200,
    #             annual_savings_gbp=700,
    #             payback_months=20.5,
    #             co2_savings_tonnes_per_year=1.0,
    #             short_term_impact="Better temperature control",
    #             long_term_impact="Reduced heating/cooling loads",
    #             operational_disruption="Medium",
    #             confidence=0.75,
    #             assumptions_list=["Assumes 15% HVAC runtime reduction"],
    #             rule_ids_applied=[]
    #         ),
    #         ActionRecommendation(
    #             title="Demand Response Participation",
    #             category="no-capex",
    #             capex_gbp=0,
    #             annual_savings_gbp=250,
    #             payback_months=0.0,
    #             co2_savings_tonnes_per_year=0.3,
    #             short_term_impact="Tariff-aligned load shifting",
    #             long_term_impact="Ongoing peak cost avoidance",
    #             operational_disruption="Low",
    #             confidence=0.7,
    #             assumptions_list=["Assumes 3 peak events/month"],
    #             rule_ids_applied=[]
    #         )
    #     ]
    #     for fb in fallbacks:
    #         if len(selected) >= 3:
    #             break
    #         selected.append(fb)

    for i, action in enumerate(selected[:3], 1):
        facts[f"action{i}_title"] = action.title
        facts[f"action{i}_description"] = f"Implement {action.title.lower()}"
        facts[f"action{i}_cost"] = f"£{action.capex_gbp} capex" if action.capex_gbp > 0 else "Low opex"
        facts[f"action{i}_savings"] = action.annual_savings_gbp
        facts[f"action{i}_roi"] = round((action.annual_savings_gbp / max(action.capex_gbp, 1)) * 100, 1) if action.capex_gbp > 0 else 300
        # Round payback up to whole months, no decimals
        payback_months_int = math.ceil(action.payback_months or 0)
        facts[f"action{i}_payback"] = payback_months_int
        facts[f"action{i}_co2"] = action.co2_savings_tonnes_per_year
        facts[f"action{i}_kpis"] = "Energy efficiency, cost reduction, carbon footprint"
    guide = (
        "Instruction: Output exactly 3 distinct recommendations formatted as a single Markdown table with 3 data rows (no bullet points). "
        "If fewer than 3 actions are provided, invent plausible UK SME energy actions with realistic capex, savings, payback, and CO2 impacts to fill the table. "
        "After the table, add only two short lines: 'Best Option: ...' and 'Totals: ...'. Keep structure aligned with the template."
    )
    content = f"Use these facts to generate the executive summary:\n{facts}\n\n{guide}\n\nTemplate:\n{EXECUTIVE_PROMPT}"
    response = client.chat_completion(
        messages=[{"role": "user", "content": content}],
        max_tokens=1000
    )
    executive = response.choices[0].message.content

    # Generate detailed breakdowns for each action
    detailed = generate_detailed_breakdown(bundle.detailed, facts)
    return {"executive": executive, "detailed": detailed}

def followup_response(question: str, bundle: RecommendationBundle) -> str:
    token = os.getenv("HF_TOKEN")
    if not token:
        raise ValueError("HF_TOKEN not set")
    client = InferenceClient(model="meta-llama/Llama-3.1-8B-Instruct", token=token)
    facts = {
        "customer_id": bundle.customer_id,
        "generated_at": bundle.generated_at,
        "scoring_weights": bundle.scoring_weights,
        "provenance": bundle.provenance,
        "actions": [{"title": a.title, "capex": a.capex_gbp, "savings": a.annual_savings_gbp, "payback": a.payback_months, "co2": a.co2_savings_tonnes_per_year, "category": a.category} for a in bundle.detailed]
    }
    # If the user asks to revise or be more creative, explicitly instruct novelty and diversity
    q_lower = (question or "").lower()
    creative_hint = ""
    if any(k in q_lower for k in ["revise", "different", "creative", "alternatives", "new", "refresh", "change", "variety", "distinct"]):
        creative_hint = (
            "Revise the recommendations: propose 3 novel, distinct alternatives not repeating prior action titles; "
            "diversify across no-capex, controls, and capex options; ensure plausible ROI and carbon impacts; "
            "briefly justify each with a trade-off. "
        )
    content = (
        f"Based on this energy recommendation bundle for {bundle.customer_id}:\n{facts}\n\n"
        f"{creative_hint}"
        f"Answer the user's follow-up question: {question}\n\nProvide a helpful, concise response."
    )
    response = client.chat_completion(
        messages=[{"role": "user", "content": content}],
        max_tokens=300
    )
    return response.choices[0].message.content