# Ener-GPT Copilot Instructions

Brief, actionable guidance for AI agents working in this repository.

## Project overview & architecture ✅
- Ener-GPT: deterministic energy calculations + LLM synthesis to generate recommendations for UK households and SMEs.
- High-level flow: bill ingest (CSV/PDF) → deterministic calculations (savings, CO₂, payback) → rules & conservative defaults → scoring & ranking → LLM synthesis (executive + detailed).
- Primary code locations: `src/ingest.py`, `src/engine/`, `src/rules/`, `src/scoring.py`, `src/llm_layer.py`, `src/schemas.py`, `prompts/`, `examples/`.

## Quick start (commands) 🔧
- Install: `pip install -r requirements.txt` (also `pip install streamlit` for UI demos).
- Environment: Create `.env` at repo root. The code expects `HF_TOKEN` for LLM access (Hugging Face Inference).
- Run CLI demo: `python examples/run_example.py`.
- Run UI demo: `streamlit run examples/ui.py`.

## Key patterns & conventions to follow 💡
- Use Python `@dataclass` types from `src/schemas.py` (e.g., `BillRecord`, `ActionRecommendation`) rather than ad-hoc dicts.
- Deterministic math lives in `src/engine/calculations.py` and returns simple dicts/primitives (e.g., `lighting_retrofit_savings` returns `{"annual_kwh_saved", "annual_savings_gbp"}`).
- Scoring defaults and logic: `src/scoring.py` uses weights `{"roi":0.6, "carbon":0.2, "disruption":0.1, "confidence":0.1}` and applies a hard penalty when payback > 24 months and CO₂ < 1 t.
- Conservative defaults and constants used widely: `derive_unit_rate()` fallback 30 p/kWh; `GRID_CARBON_UK_AVERAGE = 181 gCO2/kWh`.
- Inputs/outputs are intentionally simple for readability; keep function signatures small and clear.
 - Sectoral adjustments: `industry_multipliers()` in `src/rules/uk_rules.py` conservatively adjusts savings by industry and is applied in `examples/ui.py`.

## LLM & prompts (integration) 🤖
- LLM is called via `huggingface_hub.InferenceClient` in `src/llm_layer.py` with model `meta-llama/Llama-3.1-8B-Instruct` and requires `HF_TOKEN`.
 - If `HF_TOKEN` is missing, the LLM functions raise `ValueError`; the Streamlit UI surfaces a clear error instructing users to set `HF_TOKEN`.
 - Prompt templates exist in `prompts/`, but `src/llm_layer.py` currently defines and uses inline template strings.
 - Follow-ups: `followup_response(question, bundle)` will propose creative alternatives when the question contains keywords like "revise", "different", "creative", or "alternatives".

## Integration & external deps 🔗
 - Pandas: CSV parsing. Accepted formats include `kwh/cost_gbp` columns or `Consumption (kWh)/Time slot` with simple time-of-day rate mapping (see `examples/run_example.py` and `examples/ui.py`).
- Streamlit: demo UI only (`examples/ui.py`).
- No DB or vector store yet (FAISS mentioned as future work).

## Common pitfalls & gotchas ⚠️
- Env var standardization — code expects `HF_TOKEN`; older docs mention `OPENAI_API_KEY`. Prefer `HF_TOKEN` going forward.
- Many functions are stubs/placeholder implementations (e.g., detailed bill parsing, regional grid carbon lookup). Verify and extend in `src/ingest.py`, `src/engine`, and `src/rules` when implementing features.
- Payback can be `float('inf')` (handled by `filter_feasible()`); watch for divisions by zero in ROI calculations (scoring code guards with `max(capex,1.0)`).

## How to extend (recipes) 📚
- Add a new calculation: implement in `src/engine/calculations.py`, return consistent keys (document keys in function docstring).
- Add a new rule: add to `src/rules/uk_rules.py`, and append rule IDs to `ActionRecommendation.rule_ids_applied`.
- Add tests: there are no automated tests currently — recommended additions: `tests/test_calculations.py`, `tests/test_scoring.py` (unit test deterministic outputs and ranking behaviour).

## Reference snippets (useful exact checks) 🔎
- LLM token env var: search for `HF_TOKEN` in `src/llm_layer.py`.
- Grid carbon constant: `GRID_CARBON_UK_AVERAGE = 181` (in `src/engine/calculations.py`).
- Payback inf logic: `payback_months()` returns `float('inf')` when annual savings ≤ 0 (in `src/engine/calculations.py`).
- Scoring hard rule: penalise long-payback low-carbon actions (`src/scoring.py`).
 - Sector multipliers: `industry_multipliers()` for lighting/hvac/solar (`src/rules/uk_rules.py`).

---
If you'd like, I can (A) standardize env var names across README and examples to `HF_TOKEN`, (B) add a `.env.example` with `HF_TOKEN=`, or (C) add basic unit tests for the calculations and scoring. Which should I do next?