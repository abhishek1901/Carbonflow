# Ener-GPT: LLM-powered Energy Recommendation Engine
# MVP for UK households and SMEs

## Overview
This system ingests energy bills and asset data, computes deterministic savings and carbon impacts, scores actions by ROI, and uses an LLM to generate human-readable recommendations.

## Architecture
- Data ingestion: Parses CSV/PDF bills and asset inventories.
- Calculation engine: Deterministic energy, cost, carbon math.
- Rules layer: UK-specific constraints and defaults.
- Scoring: ROI-first ranking with constraints.
- LLM layer: Synthesizes outputs using prompt templates.

## Running the UI
- Install Streamlit: `pip install streamlit`
- Create a `.env` at repo root with `HF_TOKEN=...`
- Run: `streamlit run examples/ui.py`
- Open the browser URL shown.

Upload a CSV bill, enter industry and region, click "Get Recommendations".

## Files
- `src/ingest.py`: Data parsers
- `src/engine/calculations.py`: Core math functions
- `src/rules/uk_rules.py`: UK domain rules
- `src/scoring.py`: Ranking logic
- `src/llm_layer.py`: LLM integration (Hugging Face Inference; requires `HF_TOKEN`)
- `prompts/`: Prompt templates
- `examples/`: Sample runs

## Future
- Add vector store for benchmarks
- Integrate vendor APIs
- Add UI and persistence