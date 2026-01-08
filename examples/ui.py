import os
from datetime import date, datetime
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.schemas import BillRecord, AssetRecord, CustomerProfile, ActionRecommendation, RecommendationBundle
from src.engine.calculations import derive_unit_rate, lighting_retrofit_savings, co2_from_kwh, payback_months, confidence_score, get_grid_carbon
from src.scoring import rank_actions, filter_feasible
from src.rules.uk_rules import get_rule_ids_for_action, industry_multipliers
from src.llm_layer import synthesize_recommendations, followup_response


load_dotenv()


def _build_bundle_from_csv(df: pd.DataFrame, region: str, industry: str, bill_source: str) -> RecommendationBundle:
    if 'Consumption (kWh)' in df.columns and 'Time slot' in df.columns:
        def get_rate(slot):
            slot = str(slot).lower()
            if '7am to 10am' in slot or '5pm to 10pm' in slot:
                return 0.30
            elif '10am to 5pm' in slot:
                return 0.20
            else:
                return 0.00
        df['rate'] = df['Time slot'].apply(get_rate)
        df['cost'] = df['Consumption (kWh)'] * df['rate']
        total_kwh = df['Consumption (kWh)'].sum()
        total_cost = df['cost'].sum()
        start_date = date.today().replace(day=1, month=1)
        end_date = date.today()
    elif 'kwh' in df.columns and 'cost_gbp' in df.columns:
        total_kwh = df['kwh'].sum()
        total_cost = df['cost_gbp'].sum()
        start_date = pd.to_datetime(df['date'].min()).date() if 'date' in df.columns else date.today().replace(day=1, month=1)
        end_date = pd.to_datetime(df['date'].max()).date() if 'date' in df.columns else date.today()
    else:
        raise ValueError("CSV must have 'kwh' and 'cost_gbp' or 'Consumption (kWh)' and 'Time slot'.")

    bill = BillRecord(
        total_kwh=total_kwh,
        total_cost_gbp=total_cost,
        standing_charge_per_day=0.30,
        start_date=start_date,
        end_date=end_date
    )

    profile = CustomerProfile(
        type="SME",
        business_category=industry or "HORECA",
        postcode=region,
        floor_area_m2=120,
        operating_hours_per_day=12
    )

    # Deterministic calc for a few actions (mirror run_example.py)
    unit_rate = derive_unit_rate(bill)
    grid_co2 = get_grid_carbon(profile.postcode)
    rate_gbp = max(unit_rate / 100.0, 0.0001)
    mult = industry_multipliers(profile.business_category or "")

    savings = lighting_retrofit_savings(50, 12, 40, profile.operating_hours_per_day, unit_rate)
    annual_kwh_saved = savings["annual_kwh_saved"]
    annual_savings = savings["annual_savings_gbp"] * mult.get("lighting", 1.0)
    capex = 1600
    payback = payback_months(capex, annual_savings)
    co2_saved = co2_from_kwh(annual_kwh_saved, grid_co2)
    confidence = confidence_score({"usage_missing": False, "efficiency_missing": False})

    action1 = ActionRecommendation(
        title="LED Lighting Retrofit",
        category="capex",
        capex_gbp=capex,
        annual_savings_gbp=annual_savings,
        payback_months=payback,
        co2_savings_tonnes_per_year=co2_saved,
        short_term_impact="Energy savings from day 1, capex paid in 19 months",
        long_term_impact="Ongoing savings, LED lifespan 10+ years",
        operational_disruption="Low",
        confidence=confidence,
        assumptions_list=["Unit rate derived from bill", "12 hours/day operation"],
        rule_ids_applied=get_rule_ids_for_action("LED Lighting Retrofit")
    )

    hvac_savings = 600 * mult.get("hvac", 1.0)
    hvac_capex = 200
    hvac_payback = payback_months(hvac_capex, hvac_savings)
    hvac_kwh_saved = hvac_savings / rate_gbp
    hvac_co2 = co2_from_kwh(hvac_kwh_saved, grid_co2)

    action2 = ActionRecommendation(
        title="Smart HVAC Tuning",
        category="no-capex",
        capex_gbp=hvac_capex,
        annual_savings_gbp=hvac_savings,
        payback_months=hvac_payback,
        co2_savings_tonnes_per_year=hvac_co2,
        short_term_impact="Immediate tuning benefits",
        long_term_impact="Sustained efficiency",
        operational_disruption="Low",
        confidence=0.9,
        assumptions_list=["Conservative savings estimate"],
        rule_ids_applied=[]
    )

    solar_savings = 1200 * mult.get("solar", 1.0)
    solar_capex = 10000
    solar_payback = payback_months(solar_capex, solar_savings)
    solar_kwh = solar_savings / rate_gbp
    solar_co2 = co2_from_kwh(solar_kwh, grid_co2)

    action3 = ActionRecommendation(
        title="Solar Panel Installation",
        category="capex",
        capex_gbp=solar_capex,
        annual_savings_gbp=solar_savings,
        payback_months=solar_payback,
        co2_savings_tonnes_per_year=solar_co2,
        short_term_impact="Installation period",
        long_term_impact="Long-term clean energy",
        operational_disruption="Medium",
        confidence=0.8,
        assumptions_list=["Based on average UK solar incentives"],
        rule_ids_applied=[]
    )

    actions = [action1, action2, action3]
    feasible = filter_feasible(actions)
    ranked = rank_actions(feasible)

    bundle = RecommendationBundle(
        customer_id=f"User from {region}",
        generated_at=str(datetime.now()),
        executive_summary={},
        detailed=ranked,
        scoring_weights={"roi": 0.6, "carbon": 0.2, "disruption": 0.1, "confidence": 0.1},
        provenance={
            "bill_source": bill_source,
            "calculations": "deterministic",
            "industry": profile.business_category,
            "region": profile.postcode,
        }
    )
    return bundle


def _actions_to_df(actions: list[ActionRecommendation]) -> pd.DataFrame:
    rows = []
    for a in actions[:3]:
        roi = (a.annual_savings_gbp / a.capex_gbp * 100.0) if a.capex_gbp and a.capex_gbp > 0 else None
        rows.append({
            "Title": a.title,
            "Category": a.category,
            "Capex (£)": round(float(a.capex_gbp), 2) if a.capex_gbp is not None else None,
            "Annual Savings (£/yr)": round(float(a.annual_savings_gbp), 2) if a.annual_savings_gbp is not None else None,
            "ROI (%)": round(float(roi), 1) if roi is not None else None,
            "Payback (months)": round(float(a.payback_months), 1) if a.payback_months is not None else None,
            "CO2 Saved (t/yr)": round(float(a.co2_savings_tonnes_per_year), 2) if a.co2_savings_tonnes_per_year is not None else None,
            "Disruption": a.operational_disruption,
            "Confidence": round(float(a.confidence), 2) if a.confidence is not None else None,
        })
    return pd.DataFrame(rows)


def main():
    st.set_page_config(page_title="Ener-GPT", page_icon="⚡", layout="wide")
    st.title("Ener-GPT: UK Energy Decarbonisation Assistant ⚡")
    st.caption("Deterministic savings + LLM synthesis. Upload a bill, get 3 distinct recommendations, then chat.")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "bundle" not in st.session_state:
        st.session_state.bundle = None

    # Sidebar: data input
    with st.sidebar:
        st.header("Input")
        uploaded = st.file_uploader("Upload bill CSV", type=["csv"])
        use_sample = st.checkbox("Use sample bill (examples/sample_bill.csv)", value=uploaded is None)
        industry = st.selectbox("Industry", ["HORECA", "Office", "Retail", "Other"], index=0)
        region = st.selectbox("Region", ["UK", "EU", "India", "Other"], index=0)
        generate = st.button("Generate recommendations", type="primary")
        if st.button("Clear session"):
            st.session_state.clear()
            st.rerun()

    # Generate initial recommendations
    if generate:
        try:
            if uploaded is not None:
                df = pd.read_csv(uploaded)
                bill_source = getattr(uploaded, 'name', 'uploaded.csv')
            else:
                sample_path = os.path.join(os.path.dirname(__file__), 'sample_bill.csv')
                if use_sample and os.path.exists(sample_path):
                    df = pd.read_csv(sample_path)
                    bill_source = sample_path
                else:
                    st.error("Provide a CSV or enable 'Use sample bill'.")
                    df = None

            if df is not None:
                bundle = _build_bundle_from_csv(df, region, industry, bill_source)
                st.session_state.bundle = bundle

                with st.spinner("Synthesizing recommendations..."):
                    outputs = synthesize_recommendations(bundle)
                initial_text = (
                    "Executive Summary\n\n" + outputs.get("executive", "")
                )
                st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": initial_text})
                st.success("Generated recommendations. You can now ask follow-ups below.")
        except Exception as e:
            st.error(f"Generation failed: {e}. Ensure HF_TOKEN is set in your .env.")

    # Chat history display
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input and immediate processing (no queues, no off-by-one)
    if prompt := st.chat_input("Ask a follow-up about your plan"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        if st.session_state.bundle is None:
            reply = "Please generate recommendations first using the sidebar."
        else:
            try:
                with st.spinner("Thinking..."):
                    reply = followup_response(prompt, st.session_state.bundle)
            except Exception as e:
                reply = f"Follow-up failed: {e}. Ensure HF_TOKEN is set."
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()


if __name__ == "__main__":
    main()
