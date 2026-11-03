# IntelliQ

> **Enterprise AI Requirements & JIRA Test Engineering Platform**  
> *Scale-to-Zero Serverless Architecture • $0 Idle Cost Guaranteed • Always-Free Tier Maximized*

IntelliQ transforms meeting transcripts, architectural diagrams, specification PDFs, and project notes into fully traced, audit-ready **Business Requirements Documents (BRDs)**, **Epics**, **INVEST-Compliant User Stories**, and **JIRA-Compatible Test Cases** (with step-by-step actions and expected results), culminating in a downloadable JIRA/Xray Excel (`.xlsx`) package.

---

## 🏛 Architectural Directives Conformance Matrix

| Directive | Architectural Standard | Implementation Strategy |
| :--- | :--- | :--- |
| **ADR-01** | Scale-to-Zero Compute & Free-Tier Storage | AWS Lambda Python 3.13 on **ARM64 Graviton** via AWS Lambda Web Adapter (`RESPONSE_STREAM`); DynamoDB provisioned at **10 RCU / 10 WCU** ($0 Always-Free Tier) or On-Demand toggle; S3 with 1-day multipart abort and 7-day `tmp/` lifecycle expiration. |
| **ADR-02** | Zero-Cost Secrets & CloudWatch Hygiene | Zero paid Secrets Manager or KMS keys ($0.00 SSM Parameter Store / Lambda env vars). Explicit **7-day log retention**. Zero `PutMetricData` API calls (CloudWatch EMF JSON to stdout). |
| **ADR-03** | SST v3 (Ion) Single-Domain Routing | Single CloudFront distribution (`PriceClass_100`) proxies static assets and routes `/api/*` to Lambda Function URLs, bypassing API Gateway limits and timeouts. |
| **ADR-04** | Edge-Guarded Auth & OAC SigV4 Hashing | Cognito Lite tier ($0 idle, 10k+ free MAUs). Frontend computes **`x-amz-content-sha256`** via native Web Crypto API for CloudFront OAC SigV4 integrity. Atomic DynamoDB rate limiting. Cached RS256 JWKS validation. |
| **ADR-05** | Streaming LLM Engine & Free Cascade | Zero heavy vendor SDKs (lean `httpx` HTTP/2 SSE streaming). Free-tier cascade: **Google Gemini 2.5 Flash / Pro** (Primary) → **Groq Cloud / OpenRouter** (Secondary) → Fallback. DynamoDB and EMF telemetry flushed in async generator `finally:` block before closing `event: done`. |
| **ADR-06** | Structured Output Schema Contracts | Canonical JSON schemas in `schemas/` synchronized with compiled Pydantic v2 models and TypeScript interfaces. |
| **ADR-07** | High-Fidelity Reactive SPA | Vite + **Svelte 5 Runes** (`$state`, `$derived`, `$state.raw`) + **Tailwind CSS v4** conforming to the **Deloitte Enterprise UI Spec** (**`border-radius: 0px !important`**, WCAG AAA contrast, `#86BC25` accent discipline). 60fps `requestAnimationFrame` batching & markdown fence healer. |
| **ADR-08** | First-Class Local DX via `uv` | Python 3.13 lockfiles managed strictly with `uv`. |
| **ADR-09** | Single-Table State & S3 Offloading | DynamoDB single-table design with 24-hour idempotency locks. Payloads > 350 KB automatically compressed (`gzip`) and offloaded to S3. |

---

## 📋 Free-Tier Safety Checklist ($0/Month Target)

- [x] **No VPC NAT Gateways**: Lambdas execute in default VPC-less networking ($0 ENI / NAT surcharge).
- [x] **No EC2 / ECS / RDS**: Exclusively ephemeral scale-to-zero serverless functions.
- [x] **DynamoDB**: Configured with 10 RCU / 10 WCU (stays safely below AWS's 25 RCU / 25 WCU Always-Free tier limit).
- [x] **CloudFront**: PriceClass `PriceClass_100` (1 TB egress + 10M requests free monthly).
- [x] **Cognito**: Lite Tier (10,000+ MAUs free permanently; no paid Advanced Security features).
- [x] **S3 Storage**: Lifecycle rules expire scratch items (`tmp/`) after 7 days and abort incomplete multipart uploads after 1 day.
- [x] **CloudWatch Logs**: Capped with explicit 7-day retention (`retention: "1 week"`).
- [x] **CloudWatch Metrics**: Emitted via embedded metric format (EMF) JSON lines to `stdout` ($0 API cost).

---

## 🚀 Quickstart & Local Development

### Prerequisites
- Node.js >= 20.x & npm
- Python >= 3.11 with [`uv`](https://docs.astral.sh/uv/) installed

### 1. Clone & Configure Environment
```bash
cp .env.example .env
```
Fill in your free Google Gemini API key (`GEMINI_API_KEY`) from [Google AI Studio](https://aistudio.google.com).

### 2. Install Dependencies & Provision Free-Tier AWS Cloud Resources
```bash
# Backend dependencies via uv
uv sync --extra dev

# Frontend dependencies
npm install --prefix frontend

# Provision Always-Free Cloud Resources & Sync .env
npm run provision:aws
# (or: uv run python scripts/provision_aws.py)
```
This automatically provisions:
- **DynamoDB Single Table** (`intelliq-dev-db`) at 10 RCU/WCU Always-Free tier with automatic TTL.
- **S3 Bucket** (`intelliq-storage-<account_id>-<region>`) with CORS and 1-day/7-day lifecycle rules.
- **AWS Cognito Lite User Pool & App Client** (`intelliq-dev-userpool`) with email sign-up/in.
- Automatically synchronizes all live resource ARNs and IDs directly into `.env`.

### 3. Run Locally
**Terminal 1: Start Backend (Starlette + Uvicorn)**
```bash
uv run uvicorn lambdas.stream_worker.main:app --port 8080 --reload
```

**Terminal 2: Start Frontend (Vite + Svelte 5 + Tailwind v4)**
```bash
npm run dev --prefix frontend
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🧪 Running Automated Tests

Run the full Python test suite with code coverage and schema verification:
```bash
uv run pytest -v tests/
```

Run frontend type checking and production build test:
```bash
npm run build --prefix frontend
```

---

## ☁️ Production Deployment via SST v3 (Ion)

Deploy all infrastructure (CloudFront OAC, DynamoDB, S3, Cognito Lite, ARM64 Streaming Lambdas) in one command:
```bash
# First-time deploy or update
npx sst deploy --stage prod
```

SST outputs your CloudFront distribution URL:
```text
✔  Deployed:
   routerUrl: https://d111111abcdef8.cloudfront.net
   tableName: intelliq-Database
   bucketName: intelliq-Storage
```
Open the `routerUrl` to access the live production application.

