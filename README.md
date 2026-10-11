# Bid Intelligence

**Decision support for a road construction contractor's bid / no-bid decisions.**
Upload a highway bid package (PDF) and the system pulls out the facts an estimator needs, checks
them with a human, and predicts which competitors are likely to bid against you.

> Team project from a Summer 2026 analytics-lab engagement. The client is anonymized as `CLIENT`
> throughout the code and data. Bid results come from public state DOT lettings
> (MN, ND, SD, IA, NE, MT).

---

## The problem

Before every DOT letting, an estimator has to answer two questions quickly:

1. **What does this project actually require?** Quantities, schedule, special provisions and
   hidden "gotchas" are buried in a long plan set.
2. **Who else is going to bid?** The competitive field drives how aggressively to price, or
   whether to bid at all.

Both used to be answered by reading the PDF by hand and relying on memory.

## How it works

```
                    ┌───────────────┐     ┌──────────────┐     ┌────────────────────┐
  bid package PDF ─▶│ 1. Plan Reader │ ──▶ │ 2. Human     │ ──▶ │ 3. Competitor      │ ──▶ report
                    │  (LLM + RAG)   │     │    check     │     │    prediction (ML) │
                    └───────────────┘     └──────────────┘     └────────────────────┘
                            │
                            └──▶ 4. Chat assistant: ask questions about the plan and bid history
```

**1. Plan Reader: PDF to structured facts.**
The PDF is converted to text, split into sections, and embedded locally (MiniLM + Chroma).
Claude then extracts each field (location, project type, quantities, dates, special requirements,
a 20-type "gotcha" checklist) with a page citation and a confidence level. Fields buried in the
middle of the document are recovered with retrieval-augmented passes. All arithmetic, such as
converting quantities to tons, is done in Python, never by the model.

**2. Human check.**
The extraction is shown to the estimator with low-confidence fields flagged. They confirm or fix
values before anything downstream uses them, so one misread number can't flow silently into the
prediction or the report.

**3. Competitor prediction.**
Using the verified location, project type and quantities:

- **Candidate pool:** firms with relevant history before the bid date, such as same county, same
  project type, recent activity, past winners and regular regional bidders.
- **Scoring:** a 4-feature logistic model.
  ```
  score = 2.10·log(1 + wins in this county) + 0.61·log(1 + wins on this project type)
        + 0.56·log(1 + wins in this state)  + 0.49·size_fit
  ```
  `size_fit` measures how close this project's size is to the jobs that firm usually wins.
- **Output:** the top 5 likely bidders, each with a probability.

**4. Chat assistant.**
A Claude tool-use agent that picks from six tools: search the plan text, query bid history, look
up a project, look up competitors, view a competitor's record, and save a user correction. It
answers questions like *"What are the liquidated damages on this job?"* or *"Who usually beats us
in Stearns County?"*. Answers about the plan cite the page each fact came from.

## Results

The models are evaluated on a **time split**: trained on lettings before 2025-01-01 and tested on
lettings after 2025-05-01, so the model never sees the future. The test set has 209 projects with
a known winner.

| Model | Features | Winner in top 10 |
|---|---:|---:|
| **4-feature logistic (in production)** | 4 | **57.4%** |
| 36-feature logistic regression | 36 | 62.7% |
| Shallow decision tree | 36 | 62.7% |
| XGBoost | 36 | 67.9% |
| Random ranking | — | 5.4% |

- The production model finds the eventual winner **about 10× more often than random**.
- In its top-5 list, at least one firm actually bids on **74.5%** of test projects.
- **Why not XGBoost?** It scores about 10 points higher, but an estimator can check the 4-feature
  score by eye. We chose an auditable model over a stronger black box.
- **Strongest signal:** a firm's win history *in that specific county*. Local players stay local.

Evaluation code and outputs: [`pipelines/ci_model/04_evaluation/`](pipelines/ci_model/04_evaluation/).

## Design decisions worth noting

- **Live scoring instead of record matching.** An earlier version matched each new plan to a
  historical project by county + state + date. We measured that this isn't a unique key: there
  were 169 same-day, same-county collisions. As a result, a report could show *another project's*
  competitors. We replaced the matching with live scoring from the plan's own data.
- **The LLM reads, Python computes.** The model reliably extracts stated numbers but does not
  reliably multiply them, so prompts ask only for raw values.
- **Fail-open.** Optional steps never break a report. If a state GIS lookup or a database query
  fails, the report still renders with that field empty.
- **Never predict the client as its own competitor.** The client is the most active bidder in the
  data, so it is explicitly excluded from the candidate pool.

## Limitations

- Model metrics are offline (historical replay). The live path, which uses LLM-extracted inputs,
  has not been evaluated end to end.
- Extraction accuracy is checked by the human review step. It has not been formally scored against
  the small golden set in [`pipelines/plan_reader/03_evaluation/`](pipelines/plan_reader/03_evaluation/).
- Pit-location data covers Minnesota only, which is why distance features aren't in the
  production model.

## Tech stack

Python · FastAPI · Next.js / React / TypeScript · Anthropic Claude · Chroma + MiniLM (local
embeddings) · pymupdf4llm / pdfplumber · pandas · scikit-learn · PostgreSQL

## Repository map

| Path | What's there |
|---|---|
| [`apps/api/`](apps/api/) | FastAPI backend: PDF upload, report assembly, chat agent, live prediction |
| [`apps/web/`](apps/web/) | Next.js frontend: upload, human-check screen, report, chat |
| [`pipelines/plan_reader/`](pipelines/plan_reader/) | PDF to structured facts: conversion, indexing, extraction, evaluation |
| [`pipelines/ci_model/`](pipelines/ci_model/) | Competitor model: candidate pools, features, training, evaluation |
| [`data/`](data/) | Historical bid data (raw, cleaned, processed) and the cleaning scripts |
| [`docs/`](docs/) | Architecture reference, setup guide, data notes |

## Running it

The full app needs an `ANTHROPIC_API_KEY` and a PostgreSQL database holding the bid tables. The
project's database is **not** public, so live competitor prediction won't work out of the box.
The historical data in `data/` and the model training and evaluation scripts in
`pipelines/ci_model/` can be explored without it.

```bash
# backend (http://localhost:8010/docs)
python -m venv .venv && source .venv/bin/activate
pip install -r apps/api/requirements.txt
cd apps/api && uvicorn app:app --port 8010

# frontend, in a second terminal (http://localhost:3000)
cd apps/web && npm install && npm run dev
```

Step-by-step setup: [`docs/SETUP.md`](docs/SETUP.md) · System reference:
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · Design invariants and debugging notes:
[`docs/ENGINEERING_NOTES.md`](docs/ENGINEERING_NOTES.md)
