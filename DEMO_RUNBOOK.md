# FinWiseAI — Hackathon Judge Demonstration Runbook

> **Step-by-step walkthrough for a 5-to-10 minute recorded demonstration or live judging session.**

---

## Stage 1 — Launch Platform & Verify Health

1. Open PowerShell and start the FastAPI Backend:
   ```powershell
   cd C:\vantageai\backend
   .\.venv\Scripts\Activate.ps1
   # Use a dedicated demo database; startup creates tables and seeds demo data.
   $env:DATABASE_URL = "sqlite:///C:/vantageai/backend/vantageai-demo.sqlite3"
   python -m uvicorn app.main:app --reload --port 8000
   ```
2. In a second terminal, launch the Next.js Frontend:
   ```powershell
   cd C:\vantageai\frontend-improved
   npm run dev
   ```
3. Open browser to **[http://localhost:3000](http://localhost:3000)**.
4. Verify the top bar displays data source status, observation date, and active investor profile dropdown.

---

## Stage 2 — Stock Selection & Market Baseline

1. Click on **`NVDA`** in the top bar preset shortcuts (or type `NVDA` in the global search bar).
2. Point out:
   - Latest close, session delta, and volume.
   - 20-day and 50-day SMA trend overlays on the interactive price chart.
   - Provider data provenance (`Yahoo Finance` or `Alpha Vantage`).

---

## Stage 3 — Multi-Agent Concurrent Execution & Latency

1. Navigate to **Agent Intelligence** (`/intelligence?ticker=NVDA`) in the sidebar.
2. Highlight:
   - **Monotonic Latency**: Total execution time (typically ~150–450ms) and per-agent latency breakdown.
   - **Parallel Dispatch**: All independent analytical agents executed concurrently via `asyncio.gather`.
   - **Independent Signal Classifications**: Price Momentum, Volume Anomaly, News Sentiment, and Fundamental Health.

---

## Stage 4 — Financial Document Retrieval & Source Attribution

1. Scroll down to the **Grounded Financial Document Passages (RAG)** panel.
2. Point out:
   - NVIDIA-themed filing-style demonstration passages, visibly labeled **Synthetic Demo**.
   - BM25 relevance scores indicate topical matches; they do not prove a passage confirms an agent statement.
   - Seed examples are synthetic and have no SEC source link. Public SEC ingestion is not implemented; this demo does not show genuine filing ingestion.
3. Explain that retrieval adds context and traceability, not fact verification.

---

## Stage 5 — Agent Disagreement Intelligence

1. Inspect the **Agent Disagreement Intelligence** card.
2. Explain the core platform philosophy:
   - FinWiseAI surfaces genuine analytical divergence (e.g. Bullish Technical Momentum vs Rich Fundamental Valuation multiples).
   - The platform deterministic consensus rules prevent averaging contradictory evidence into an artificial stance.

---

## Stage 6 — Deterministic Reasoning Trace

1. Expand the **Deterministic Execution & Reasoning Trace** accordion at the bottom of `/intelligence`.
2. Walk the judges through the 6 distinct execution steps:
   - Step 1: Market Observation & Data Ingestion
   - Step 2: Multi-Dimensional Signal Classification
   - Step 3: Financial Document Retrieval (RAG)
   - Step 4: Deterministic Consensus & Disagreement Resolution
   - Step 5: Investor Profile Risk Personalization
   - Step 6: Informational Synthesis & Provenance Verification

---

## Stage 7 — Investor Personalization & Live Profile Comparison

1. Navigate to **Portfolio & Risk** (`/portfolio?ticker=NVDA`) in the sidebar.
2. Point out the active profile's **Herfindahl-Hirschman Index (HHI)** concentration score and portfolio holdings table.
3. Scroll down to the **Deterministic Profile Comparison Tool**:
   - Select **Profile A: Conservative Capital Preservation** (Risk 1/5) vs **Profile B: Aggressive Growth Investor** (Risk 5/5).
   - Click **Run Side-by-Side Comparison**.
   - Show the result:
     - Profile A receives `Caution / High Volatility for Conservative Mandate` with strict downside caveats and cash-flow questions.
     - Profile B receives `Suitable for Growth Mandate` with growth beta and operating leverage questions.
     - Highlight the green verification banner: **"Underlying Market Data Snapshot Unaltered: 100% IDENTICAL"**.

---

## Stage 8 — System Performance & Historical Signal Evaluation

1. Navigate to **System Evaluation** (`/evaluation`) in the sidebar.
2. Show the judges:
   - Average end-to-end latency and BM25 RAG retrieval latency.
   - Recent session completeness; a partial analysis may have an overall direction while an agent is unavailable.
   - Historical 30-Day Forward Return Evaluation Log:
     - Synthetic evaluation examples are labeled and excluded from real accuracy.
     - Pending, unavailable, evaluated, and synthetic-excluded states are shown separately; unavailable outcomes are not losses.
     - The updater runs only when an operator calls its protected endpoint. No recurring scheduler is configured, so do not claim evaluation outcomes update autonomously.
   - Recent Intelligence Sessions Audit Trail.

---

## Stage 9 — Controlled Degraded-Data & Unlisted Symbols

1. Type an unlisted valid ticker like **`AMD`** or **`INTC`** into the top search bar:
   - Demonstrates that the global search supports any valid ticker beyond presets.
2. In `/news`, type a search query in the RAG explorer:
   - Demonstrates BM25 search over the documents already stored in the local corpus, which is seeded with synthetic examples.
3. Note the explicit handling of missing or incomplete fundamentals:
   - An unavailable provider returns `UNAVAILABLE` rather than faking data or crashing the terminal.

---

## Stage 10 — Conclusion & Methodology Review

1. Navigate to **Data & Methodology** (`/methodology`).
2. Conclude the presentation:
   - "FinWiseAI does not pretend all financial indicators agree. It runs independent deterministic analysis services, retrieves related document context without treating lexical matches as proof, preserves disagreements, and personalizes risk context to an investor's mandate."
