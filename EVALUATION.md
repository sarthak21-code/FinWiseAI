# FinWiseAI Session Metrics and Outcome Evaluation

FinWiseAI is a deterministic financial-research prototype. Execution metrics describe system work; they do not measure investment skill. Heuristic signal confidence is not a calibrated probability.

## Session measurements

| Metric | Formula / scope | Units | Null and failure semantics |
| --- | --- | --- | --- |
| Analysis duration | `time.perf_counter()` from `analyze_symbol` entry through synthesis and optional profile interpretation, before persistence | Milliseconds | Reported for completed analysis; displayed rounded to 0.1 ms, stored session rounded to 0.01 ms |
| Per-agent service duration | `time.perf_counter()` inside each technical/fundamental/news task, including provider processing through result or caught error | Milliseconds per agent | The failed agent still records elapsed failure time and status `unavailable` |
| BM25 search duration | RAG-stage start through claim preparation, local DB session acquisition when necessary, and searches | Milliseconds | A completed empty search is timed; a failed search retains measured duration but its evidence coverage is null |
| Lexical evidence coverage | Distinct agent evidence claims with at least one BM25 context passage ÷ evidence claims submitted to BM25 × 100 | Percent | 0% means the search completed with no matched claims; null means no agent claims existed or retrieval did not complete |

The three latency measurements are carried in existing response/session structures: `total_latency_ms`, per-assessment `latency_ms`, and `rag_latency_ms`. Session persistence stores the timings in existing columns and serialized agent/reasoning JSON; no new DB columns are required. Coverage counts are in the response and persisted RAG reasoning-step metadata. A BM25 match does not establish factual support. Coverage is not accuracy.

The API's session endpoint returns the saved analysis, assessments, signals, citations and reasoning trace. Old rows may not contain new coverage metadata; do not infer it from missing values.

## Rule-based signal confidence

Signal and assessment confidence values are heuristic. Technical values reflect configured indicator rules; fundamentals use configured rule concordance and available metric count; news uses provider-sourced headline volume and lexical sentiment. Missing/unavailable agents have zero confidence and explicit unavailable status. No value is a calibrated probability or forecast.

## RAG and source integrity

BM25 ranks lexical matches over persisted document chunks. Seeded passages are synthetic and must remain marked synthetic. Results retain document ID, chunk ID, title, period, source name/URL, synthetic flag, and calculated relevance score. `claim_type=context` means related text, not evidence that the text proves a claim. The current API has no public SEC or transcript ingestion route; no genuine SEC filing retrieval is claimed.

An empty completed search has 0% lexical evidence coverage and returns no citations. A failed retrieval reports coverage as null. It does not generate replacement passages.

## 30-calendar-day forward evaluation

New directional synthesis records use the observed close and signal timestamp and set `evaluation_horizon_days=30`; target date is signal timestamp plus 30 calendar days. This is a calendar-day convention, not 30 trading sessions. The explicit updater uses the existing historical-price abstraction and selects the first valid completed daily close strictly after the target date and before the current UTC day. Since daily bars retain only their date (not their exact close timestamp), this conservative rule avoids using a same-day close that may precede the precise horizon or a possibly incomplete current-day bar.

The updater is an explicit operator operation at `POST /api/v1/intelligence/evaluation/update`, protected by the `X-Evaluation-Update-Token` header. Configure `EVALUATION_UPDATE_TOKEN` in the backend process before using it. The route is disabled when no token is configured. It processes at most 100 mature rows by default (limit 1–500), never sends synthetic records to a provider, has a 20-second per-symbol wait bound, and defers remaining rows after a 60-second operation budget. It is not scheduled: recurring execution still requires deployment infrastructure or a trusted operator to invoke the route.

The API serializes status separately from the classification outcome: `pending` means the window has not matured or has not yet been processed; `unavailable` means mature data retrieval or classification failed and the row can be retried; `evaluated` means an outcome was classified; `excluded` represents synthetic/demo records. A source-safe status detail is retained for unavailable records. Pending and unavailable records are not counted as wins or losses. The session audit includes separate evaluated, pending, unavailable, and excluded counts, and derives `complete`/`partial` from the serialized technical, fundamental, and news assessments. Partial analyses remain in the session audit but do not create evaluation rows.

Evaluation writes with a session ID derive the row primary key deterministically from `(session_id, signal_dimension)`. The existing primary-key constraint therefore serializes concurrent creates without an added column or migration. Outcome transitions use a conditional database update from only `pending_window` or `unavailable`, so finalized records are not overwritten by concurrent retries. Existing rows created by prior random-ID implementations are returned by logical-key lookup; unknown historical duplicate rows are not removed or deduplicated.

Synthetic examples are flagged and excluded from real completed accuracy. If there are zero eligible completed real outcomes, accuracy rate is numerically 0 for API compatibility, but the completed-real count must be read alongside it; zero here means no measured sample, not zero predictive skill.

Accuracy, where eligible outcomes exist, is calculated over non-synthetic records with outcome `accurate`, `inaccurate`, or `inconclusive`; report the sample size and do not treat the prototype's thresholds as a validated trading strategy.
