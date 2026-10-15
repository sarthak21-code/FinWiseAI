# FinWiseAI

**Smarter Insights. Better Investments.**

FinWiseAI is a financial research workspace for transparent market analysis, specialist-agent disagreement, financial document retrieval, investor risk context, and historical signal evaluation. Its current document corpus includes synthetic examples; lexical retrieval does not verify factual claims.

## Run locally

Start the backend using the isolated demo database instructions in the repository [README](../README.md), then start this frontend:

```powershell
cd C:\vantageai\frontend-improved
npm install
npm run dev
```

The frontend uses the configured `/api/backend` proxy. See the root README and [demo runbook](../DEMO_RUNBOOK.md) for backend configuration and the reproducible walkthrough.

## Verification

```powershell
npm test
npm run lint
npm run build
```
