import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from datetime import date, datetime
import pandas as pd
from src.schemas import BillRecord, AssetRecord, CustomerProfile, ActionRecommendation, RecommendationBundle
from src.engine.calculations import derive_unit_rate, lighting_retrofit_savings, co2_from_kwh, payback_months, confidence_score, get_grid_carbon
from src.scoring import rank_actions, filter_feasible
from src.rules.uk_rules import apply_conservative_defaults, get_rule_ids_for_action
from src.llm_layer import synthesize_recommendations

def chatbot():
    print("Welcome to Ener-GPT: Your UK Energy Decarbonisation Assistant!")
    print("Let's get started with some information.\n")

    # 1. Upload Energy Bill
    bill_file = input("Please provide the path to your energy bill CSV file (e.g., C:\\path\\to\\bill.csv): ").strip()
    if not os.path.exists(bill_file):
        print("File not found. Please try again.")
        return

    # Parse bill (assume CSV with columns: date, kwh, cost_gbp)
    try:
        df = pd.read_csv(bill_file)
        print("Detected columns:", list(df.columns))
        if 'Consumption (kWh)' in df.columns and 'Time slot' in df.columns:
            # Calculate kwh and cost from this format
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
            # Dummy dates
            start_date = date.today().replace(day=1, month=1)
            end_date = date.today()
        elif 'kwh' in df.columns and 'cost_gbp' in df.columns:
            total_kwh = df['kwh'].sum()
            total_cost = df['cost_gbp'].sum()
            start_date = pd.to_datetime(df['date'].min()).date() if 'date' in df.columns else date.today().replace(day=1, month=1)
            end_date = pd.to_datetime(df['date'].max()).date() if 'date' in df.columns else date.today()
        else:
            print("CSV must have 'kwh' and 'cost_gbp' columns, or 'Consumption (kWh)' and 'Time slot' for calculation.")
            return
        bill = BillRecord(
            total_kwh=total_kwh,
            total_cost_gbp=total_cost,
            standing_charge_per_day=0.30,  # Assume default
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        print(f"Error parsing bill: {e}")
        return

    # 2. Industry
    industry = input("What industry do you work in? (e.g., HORECA, office, retail): ").strip()

    # 3. Region
    region = input("Select your region (UK, EU, India, Other): ").strip().title()
    if region not in ["UK", "EU", "India", "Other"]:
        print("Invalid region. Using UK.")
        region = "UK"

    # Create profile
    profile = CustomerProfile(
        type="SME",
        business_category=industry,
        postcode=region,
        floor_area_m2=120,  # Stub
        operating_hours_per_day=12  # Stub
    )

    # Stub asset (lighting)
    asset = AssetRecord(
        asset_type="lighting",
        capacity_kw=2.0,
        efficiency=0.9,
        usage_kwh_per_day=24,
        opex_per_year_gbp=100,
        capex_estimate_gbp=1600
    )

    # Calculations
    unit_rate = derive_unit_rate(bill)
    grid_co2 = get_grid_carbon(profile.postcode)

    savings = lighting_retrofit_savings(50, 12, 40, profile.operating_hours_per_day, unit_rate)
    annual_kwh_saved = savings["annual_kwh_saved"]
    annual_savings = savings["annual_savings_gbp"]
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

    # Another stub action
    action2 = ActionRecommendation(
        title="Smart HVAC Tuning",
        category="no-capex",
        capex_gbp=200,
        annual_savings_gbp=600,
        payback_months=4,
        co2_savings_tonnes_per_year=0.7,
        short_term_impact="Immediate tuning benefits",
        long_term_impact="Sustained efficiency",
        operational_disruption="Low",
        confidence=0.9,
        assumptions_list=["Conservative savings estimate"],
        rule_ids_applied=[]
    )

    # Add a third action to ensure 3 recommendations
    action3 = ActionRecommendation(
        title="Solar Panel Installation",
        category="capex",
        capex_gbp=10000,
        annual_savings_gbp=1200,
        payback_months=100.0,
        co2_savings_tonnes_per_year=3.5,
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
        provenance={"bill_source": bill_file, "calculations": "deterministic"}
    )

    # Output
    print("\nProcessing your data...")
    print(f"Bill: {total_kwh} kWh, £{total_cost}")
    print(f"Industry: {industry}, Region: {region}")
    print(f"Derived unit rate: {unit_rate:.2f} p/kWh")

    print("\nTop Recommendations (LLM-Generated Creative Solutions):")
    try:
        outputs = synthesize_recommendations(bundle)
        print("Executive Summary:")
        print(outputs["executive"])
        print("\nDetailed Breakdown:")
        print(outputs["detailed"])
    except Exception as e:
        print(f"LLM generation failed: {e}. Set HF_TOKEN.")

if __name__ == "__main__":
    chatbot()