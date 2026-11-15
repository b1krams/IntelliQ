# Operational Rules & Architectural Constraints for AI Coding Agents

## 1. Mission & Architectural Principles
**IntelliQ** is an enterprise-grade, scale-to-zero serverless AI platform designed to transform raw product inputs (meeting transcripts, architectural diagrams, specification PDFs, and notes) into fully traced, audit-ready **Business Requirements Documents (BRDs)**, **Epics**, **INVEST-Compliant User Stories**, and **JIRA/Xray-Compatible Test Cases** (with step-by-step actions and expected results).

Every line of code, infrastructure construct, and data pattern in this repository must strictly adhere to the **$0 Idle Cost Invariant**:
- **$0 Idle Cost**: The application must incur $0.00 when not handling active requests, operating entirely within AWS Always-Free tier thresholds.
- **Scale-to-Zero Serverless**: Ephemeral execution only. No persistent compute instances, NAT gateways, or provisioned idle databases.
- **Zero Heavy SDKs**: Ultra-lean Lambda deployment packages (<15MB) using native HTTP/2 clients instead of bloated vendor SDKs.
- **Strict Geometric Enterprise UI**: High-density enterprise aesthetics with zero rounded corners (`border-radius: 0px !important`).

---

## 2. Repository Directory Map
Agents must consult this map to locate files and ensure changes are placed in their proper layer:

```text
IntelliQ/
├── core/                         # Shared backend business logic & core primitives
│   ├── auth.py                   # PyJWT cached JWKS RS256 token verification
│   ├── cognito.py                # SRP / USER_PASSWORD_AUTH client for Cognito Lite
│   ├── config.py                 # Pydantic v2 settings & SSM/env resolution
│   ├── db.py                     # DynamoDB single-table repo, atomic rate limiter & S3 offloader
│   ├── telemetry.py              # Zero-cost CloudWatch Embedded Metric Format (EMF) to stdout
│   └── llm/                      # Zero-SDK streaming LLM engine & cascade
│       ├── adapters.py           # Direct HTTP/2 SSE streaming (Gemini, Groq, OpenAI fallback)
│       ├── engine.py             # Multi-stage orchestrator, schema enforcer & stream buffer
│       └── models.py             # Generated Pydantic v2 schema models
├── lambdas/                      # AWS Lambda compute entrypoints
│   ├── api_handler/              # REST API Lambda (auth, uploads, downloads, exports)
│   │   └── handler.py
│   └── stream_worker/            # Streaming AI Lambda via AWS Lambda Web Adapter
│       ├── main.py               # Starlette ASGI application with streaming response
│       ├── run.sh                # Container/adapter boot script
│       └── run.py
├── frontend/                     # High-fidelity reactive SPA (Vite + Svelte 5 + Tailwind v4)
│   ├── src/
│   │   ├── App.svelte            # Root application view
│   │   ├── app.css               # Global geometric reset (border-radius: 0px !important)
│   │   ├── main.ts               # Client entrypoint
│   │   ├── components/           # Svelte 5 components (AuthModal, WorkflowStepper, etc.)
│   │   │   └── stages/           # Workflow stage views (IntakeStage, BrdStage, etc.)
│   │   └── lib/                  # Frontend utilities, stores & test suites
│   │       ├── api.ts            # Client fetch wrapper with Web Crypto SigV4 SHA-256
│   │       ├── auth.svelte.ts    # Svelte 5 reactive auth state rune
│   │       ├── crypto.ts         # Native Web Crypto SHA-256 payload hasher
│   │       ├── stores.svelte.ts  # Application reactive state runes
│   │       ├── stream_parser.ts  # Line-buffered SSE parser with markdown fence healing
│   │       ├── types.ts          # Synchronized TypeScript contracts
│   │       └── url_sync.ts       # Zero-dependency URL & history hydration
│   └── package.json
├── schemas/                      # Canonical JSON schemas (Single Source of Truth)
│   ├── brd.schema.json           # Business Requirements Document schema
│   ├── epic.schema.json          # Epic breakdown schema
│   ├── story.schema.json         # INVEST user story schema
│   ├── test_case.schema.json     # JIRA/Xray test case schema
│   └── workflow_state.schema.json
├── scripts/                      # Developer automation & cloud provisioning
│   ├── provision_aws.py          # Provisions Always-Free AWS resources & updates .env
│   ├── generate_types.py         # Compiles JSON schemas to Pydantic v2 & TypeScript
│   └── generate_types.sh
├── tests/                        # Backend unit & integration test suite
│   ├── test_auth.py              # Token verification & JWKS caching tests
│   ├── test_cognito_challenge.py # Cognito Lite auth flow tests
│   ├── test_llm_engine.py        # LLM streaming adapters & fallback cascade tests
│   ├── test_rate_limiter.py      # DynamoDB atomic tumbling window rate limit tests
│   └── test_schema_conformance.py# Pydantic schema validation tests
├── sst.config.ts                 # SST v3 (Ion) infrastructure-as-code
├── pyproject.toml                # Python 3.13 dependencies & tooling via uv
└── package.json                  # Root orchestration & scripts
```

---

## 3. The Invariant Architectural Directives (ADR-01 through ADR-13)

### ADR-01: Scale-to-Zero & Free-Tier Guardrails
- **Compute**: Exclusively AWS Lambda on **ARM64 (Graviton)** using Python 3.13 and the AWS Lambda Web Adapter (`RESPONSE_STREAM`). Never introduce EC2, ECS, Fargate, RDS, VPC NAT Gateways, or VPC endpoints ($0 network/idle cost).
- **Database**: Single-Table DynamoDB provisioned at **10 RCU / 10 WCU** (well within AWS Always-Free 25 RCU/WCU limit) with an On-Demand toggle. Maximum 2 Global Secondary Indexes (GSIs).
- **Storage**: S3 lifecycle rules must enforce **1-day abort** for incomplete multipart uploads and **7-day expiration** for objects under `tmp/`.
- **CDN**: CloudFront PriceClass configured strictly to `PriceClass_100` (North America & Europe; 1 TB egress + 10M requests free monthly).

### ADR-02: Zero-Cost Secrets, Encryption & Log Hygiene
- **Zero Paid Secrets/Keys**: Never use AWS Secrets Manager ($0.40/secret/mo) or KMS Customer-Managed Keys ($1.00/key/mo). Use **SSM Parameter Store** (Standard Tier $0.00) or deploy-time Lambda environment variables. Rely on default `SSE-S3` for storage and AWS-owned keys for DynamoDB.
- **Log Hygiene**: All CloudWatch Log Groups must have explicit 7-day retention (`retention: "1 week"`). Debug logs sampled at 10% in production to stay below 5 GB/month.
- **Zero Paid Metrics**: Zero `PutMetricData` API calls ($0.00). Emit metrics strictly via **CloudWatch Embedded Metric Format (EMF)** JSON lines to `stdout`.

### ADR-03: SST v3 (Ion) Single-Domain Infrastructure
- A single CloudFront distribution routes static SPA assets from S3 and proxies `/api/*` to Lambda Function URLs (`streaming: true`).
- Bypasses API Gateway limits (30-second execution caps, payload surcharges, and HTTP API costs).

### ADR-04: Edge-Guarded Auth & OAC SigV4 Hashing
- **Auth Provider**: AWS Cognito Lite Tier (SRP / `USER_PASSWORD_AUTH`, 10,000+ MAUs free; no paid Advanced Security / WAF features).
- **Function URL Security**: Function URLs configured with `AuthType: AWS_IAM` and locked to CloudFront Origin Access Control (OAC).
- **Payload Integrity**: Frontend **MUST** attach the `x-amz-content-sha256` header (hex-encoded SHA-256 computed via native browser Web Crypto API) on all `POST` and `PUT` requests for SigV4 compliance.
- **Rate Limiting**: Starlette ASGI middleware enforces zero-cost rate limiting using atomic DynamoDB `UpdateItem` (`ADD request_count :inc`) with automatic TTL.
- **Token Verification**: In-memory cached RS256 JWKS verification via `PyJWT` with zero network overhead on repeated invocations.

### ADR-05: Python Streaming Engine & Zero Heavy SDKs
- **Zero Heavy SDKs**: Never import `openai`, `anthropic`, `google-genai`, `google-generativeai`, `langchain`, or `litellm`. Use lean `httpx.AsyncClient(http2=True)` adapters in `core/llm/adapters.py`.
- **Free-Tier LLM Cascade**:
  1. Primary: **Google Gemini Free Tier** (`gemini-2.5-flash` / `gemini-2.5-pro` via AI Studio key)
  2. Secondary: **Groq Cloud Free Tier** (`llama-3.3-70b-versatile`)
  3. Fallback: Optional paid provider (OpenAI compatible)
- **Lifecycle & Flushing**: Lambda freezes immediately when the streaming response generator terminates. DynamoDB state persistence and EMF metrics **MUST** be flushed in a `finally:` block *prior* to yielding `event: done`.

### ADR-06: Native Structured Outputs & Strict Contracts
- All structured outputs conform to canonical JSON schemas in `schemas/*.schema.json`.
- Python Pydantic v2 models (`core/llm/models.py`) and TypeScript interfaces (`frontend/src/lib/types.ts`) are compiled directly from these schemas via `scripts/generate_types.py`. Never edit generated models manually.

### ADR-07: Reactive Frontend (Svelte 5 Runes + Geometric Enterprise UI)
- **Strict 0px Border-Radius**: Universal `border-radius: 0px !important` across all UI primitives (buttons, inputs, cards, dialogs, badges, tables). Absolutely NO rounded pills, rounded corners (`rounded-*`), or circular avatars.
- **Svelte 5 Runes Only**: Exclusively use `$state`, `$state.raw`, `$derived`, `$effect`, and `$props`. Never write legacy Svelte 3/4 syntax (`export let`, `$:`, writable stores).
- **Tailwind CSS v4**: `@tailwindcss/vite` configuration with enterprise monospacing and deliberate Deloitte Green (`#86BC25`) accent discipline.
- **Frame-Throttled Streaming**: Line-buffered SSE stream consumer with automatic markdown fence healing and 60fps `requestAnimationFrame` token batching.

### ADR-08: Python 3.13 DX via uv
- All Python dependencies and virtual environments are managed strictly with [`uv`](https://docs.astral.sh/uv/). Lockfiles are maintained via `uv.lock`.

### ADR-09: Single-Table State & S3 Offloading
- Single-Table DynamoDB schema conventions:
  - Primary Key: `PK` (String, partition key) and `SK` (String, sort key)
  - Global Secondary Index 1: `GSI1PK` and `GSI1SK`
  - Entity prefixes:
    - User/Workflow state: `PK = "USER#{user_id}"`, `SK = "WORKFLOW#{workflow_id}"`
    - GSI stage query: `GSI1PK = "STAGE#{stage}"`, `GSI1SK = "TIME#{timestamp}"`
    - Rate limits: `PK = "RATELIMIT#{identifier}"`, `SK = "WINDOW#{bucket}"`
    - Idempotency locks: `PK = "IDEMPOTENCY#{idempotency_key}"`, `SK = "LOCK"` (24-hour TTL)
- **Large Payload Offloading**: Payloads > 350 KB must be gzip-compressed and offloaded to S3 at `artifacts/{workflow_id}/state.json.gz`. A pointer (`s3_key`) and SHA-256 hash are recorded in DynamoDB.

### ADR-10: Resilient Real-Time AI Stream Processing & Chunk Fence Healing
- **Line-Buffered Processing**: Buffer incomplete incoming network chunks across `\n\n` boundaries before parsing SSE events. Never assume a network chunk represents a full token or event.
- **Markdown & Delimiter Healing**: Detect unclosed fences (code blocks, quotes, tables, lists) and heal in the rendering buffer to prevent UI layout breakage mid-stream.
- **Lifecycle & Cancellation**: Every streaming request must provide an `AbortController` cancellation handle, an idempotency key header, and visual indicators for all stream states (`idle`, `streaming`, `paused`, `error`, `done`).

### ADR-11: Zero-Regression Multi-Tier Quality Gate
- **Strict Type-Level Gatekeeping**: Zero-warning/zero-error TypeScript and framework compilation prior to build (`pnpm run frontend:check` or `pnpm --filter intelliq-frontend check`).
- **Headless Unit & State Testing**: Business logic, reactive state runes, crypto hashing, and protocol parsers tested via in-memory runner (Vitest: `pnpm run frontend:test` or `pnpm --filter intelliq-frontend test`).
- **Backend Quality Verification**: Pytest suite verifying auth, rate limiting, LLM fallback cascade, and schema conformance (`uv run --extra dev pytest tests/`).

### ADR-12: Zero-Dependency URL-State Hydration & Deep Linking
- **Native History Synchronization**: Synchronize active workflow ID and stage directly with browser location (`pushState`/`replaceState`/query/hash) without heavy client-side router dependencies.
- **Bidirectional Hydration**: Initial page mount hydrates state from URL parameters; stage transitions update the URL without full-page reloads.
- **Graceful Fallback**: Missing or invalid session IDs recover gracefully to a default state with a clear notification.

### ADR-13: Rigid Architectural Design System & Universal Accessibility Standards
- **Geometric Design Tokens**: Universal 0px border-radius across every component without exception.
- **High-Density Typography**: Prioritize clean monospaced technical metadata (`font-mono`) and crisp sans-serif headers.
- **Keyboard Navigation & Focus Rings**: Explicit 2px high-contrast focus rings (`:focus-visible`). Modals and drawers must trap focus and close on `Escape`.
- **Accessible AI Announcers**: Dynamic AI stream updates and status banners must use ARIA live regions (`aria-live="polite"` or `role="status"`).

---

## 4. Developer & Agent Command Reference

### Python Backend (Managed via `uv`)
```bash
# Install dependencies including dev tools
uv sync --extra dev

# Run full backend test suite
uv run --extra dev pytest tests/

# Run specific test file
uv run --extra dev pytest tests/test_llm_engine.py

# Lint & check formatting with ruff
uv run ruff check .

# Start local backend API / streaming server
uv run uvicorn lambdas.stream_worker.main:app --port 8080 --reload
```

### Frontend (Vite + Svelte 5 + Tailwind v4 via pnpm)
```bash
# Install all dependencies across workspace
pnpm install

# Run frontend type checking (must produce 0 errors, 0 warnings)
pnpm run frontend:check
# (or: pnpm --filter intelliq-frontend check)

# Run frontend unit tests (Vitest)
pnpm run frontend:test
# (or: pnpm --filter intelliq-frontend test)

# Start local frontend dev server (http://localhost:5173)
pnpm run frontend:dev

# Production frontend build
pnpm run frontend:build
```

### Schemas & Cloud Provisioning
```bash
# Recompile JSON schemas to Pydantic v2 models and TypeScript types
uv run python scripts/generate_types.py

# Provision Always-Free AWS Cloud Resources & sync .env
pnpm run provision:aws
# (or: uv run python scripts/provision_aws.py)

# SST v3 Deployment (Ion)
pnpm run dev      # SST local dev
pnpm run deploy   # SST deploy
```

---

## 5. Prohibited Practices & Anti-Patterns ("Hard No-Go List")

Agents working on this repository must **NEVER**:
1. **Never install or import heavy vendor LLM SDKs**: Do not add `openai`, `anthropic`, `google-genai`, `google-generativeai`, `langchain`, `langchain-core`, `litellm`, or `llama-index`. Use `httpx` in `core/llm/adapters.py`.
2. **Never introduce paid or idle-cost AWS services**: Do not provision EC2 instances, ECS/Fargate clusters, RDS databases, VPC NAT Gateways, VPC Endpoints, AWS Secrets Manager, KMS Customer Managed Keys, or CloudWatch Synthetics.
3. **Never call `PutMetricData`**: Emitting metrics via the CloudWatch API incurs surcharges. Emit exclusively through Embedded Metric Format (EMF) JSON to `stdout`.
4. **Never use rounded UI corners**: Do not use `rounded`, `rounded-sm`, `rounded-md`, `rounded-lg`, `rounded-full`, or pill badges in frontend markup. The design system enforces strict `border-radius: 0px !important`.
5. **Never write Svelte 4 legacy syntax**: Do not use `export let`, `$: reactive`, `on:click`, or legacy Svelte writable stores in `.svelte` files. Use Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`, `onclick`).
6. **Never edit generated schema models directly**: Do not modify `core/llm/models.py` or `frontend/src/lib/types.ts` by hand. Update the canonical schemas in `schemas/*.schema.json` and run `scripts/generate_types.py`.
7. **Never perform non-streaming LLM requests**: All generative operations must stream via Server-Sent Events (SSE) with `AbortController` handles and line buffering.
8. **Never bypass frontend SigV4 hash calculation**: All mutating HTTP requests (`POST`, `PUT`) must compute and pass `x-amz-content-sha256` via Web Crypto API.

---

## 6. Agent Operational Protocols & Quality Gates

When completing any task or bugfix, coding agents must follow this verification protocol before reporting completion:

1. **Verify Architectural Compliance**: Confirm that changes do not violate ADR-01 through ADR-13 (check for zero idle cost, 0px border-radius, lean imports).
2. **Execute Backend Verification**: Run the Pytest suite:
   ```bash
   uv run --extra dev pytest tests/
   ```
   All tests must pass.
3. **Execute Frontend Type & Unit Gate**: Run both typecheck and unit tests:
   ```bash
   pnpm run frontend:check
   pnpm run frontend:test
   ```
   Must pass with 0 errors and 0 warnings.
4. **Preserve Schema Synchronization**: If modifying data shapes, update the canonical schema in `schemas/`, execute `uv run python scripts/generate_types.py`, and verify both Pydantic and TypeScript consumers compile cleanly.
