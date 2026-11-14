# Operational Rules & Architectural Constraints for AI Coding Agents

## Mission & Principles
**IntelliQ** is an enterprise-grade, scale-to-zero serverless AI application designed to run permanently with **$0 idle cost** by staying within AWS Always-Free tier thresholds. Every line of code, infrastructure construct, and data pattern must strictly conform to these rules.

## The Invariant Architectural Directives (ADR-01 through ADR-13)

1. **ADR-01: Scale-to-Zero & Free-Tier Guardrails**
   - Compute: Only AWS Lambda Python 3.13 on ARM64 (Graviton). No EC2, ECS, NAT Gateways, RDS, or VPC endpoints.
   - Database: Single-Table DynamoDB provisioned at 10 RCU / 10 WCU (stays under 25 RCU/WCU Always-Free limit) with an On-Demand toggle. Maximum 2 GSIs.
   - Storage: S3 buckets must enforce 1-day abort for incomplete multipart uploads and 7-day expiration for `tmp/` objects.
   - CDN: CloudFront PriceClass_100.
2. **ADR-02: Zero-Cost Secrets, Encryption & Log Hygiene**
   - Never use AWS Secrets Manager or KMS Customer-Managed Keys ($0.40/secret and $1.00/key/month).
   - Use SSM Parameter Store (Standard Tier $0.00) or deploy-time Lambda environment variables. Default `SSE-S3` and AWS-owned DynamoDB keys.
   - CloudWatch Log Groups must have explicit 7-day retention (`retention: "1 week"`).
   - Zero `PutMetricData` API calls. Emit metrics strictly via CloudWatch Embedded Metric Format (EMF) JSON to `stdout`.
3. **ADR-03: SST v3 (Ion) Infrastructure**
   - Single CloudFront distribution routes static assets from S3 and proxies `/api/*` to Lambda Function URLs (`streaming: true`).
   - Bypasses API Gateway timeouts and cost surcharges.
4. **ADR-04: Edge-Guarded Auth & OAC SigV4 Hashing**
   - Cognito Lite tier only (no paid WAF/advanced security).
   - Function URLs require `AuthType: AWS_IAM` and are locked to CloudFront OAC.
   - Frontend **MUST** attach `x-amz-content-sha256` computed via browser Web Crypto API on all `POST`/`PUT` requests.
   - Zero-cost rate limiting in Starlette ASGI middleware using atomic DynamoDB `UpdateItem` with TTL.
   - Zero-network-overhead cached RS256 JWKS verification via `PyJWT`.
5. **ADR-05: Python Streaming Engine & Zero Heavy SDKs**
   - AWS Lambda Web Adapter ARM64 layer with `RESPONSE_STREAM`.
   - Never import heavy vendor SDKs (`openai`, `anthropic`, `google-genai`, `langchain`, `litellm`). Use lean `httpx.AsyncClient(http2=True)` adapters in `core/llm/adapters.py`.
   - Free-tier cascade: Google Gemini Free Tier -> Groq Cloud Free Tier -> paid fallback.
   - Lambda freezes immediately when generator ends: flush DynamoDB state and EMF logs in `finally:` block *prior* to `event: done`.
6. **ADR-06: Native Structured Outputs & Strict Contracts**
   - All structured outputs conform to `schemas/*.schema.json` and compiled Pydantic v2 models.
7. **ADR-07: Reactive Frontend (Svelte 5 Runes + Geometric Enterprise UI)**
   - Strict 0px border-radius (`border-radius: 0px !important`). Strictly no rounded pills, soft inputs, or circular avatars.
   - Svelte 5 Runes only (`$state`, `$state.raw`, `$derived`, `$effect`, `$props`). No Svelte 4 legacy syntax.
   - Tailwind CSS v4 (`@tailwindcss/vite`).
   - Line-buffered SSE parser with markdown fence healing and 60fps `requestAnimationFrame` batching.
8. **ADR-08: Python 3.13 DX via uv**
   - All Python dependencies managed via `uv`.
9. **ADR-09: Single-Table State & S3 Offloading**
   - Single-table composite keys (`PK`, `SK`, `GSI1PK`, `GSI1SK`).
   - Payloads > 350 KB must be gzip-compressed and stored in S3.
   - Idempotency locks stored with 24-hour TTL.
10. **ADR-10: Resilient Real-Time AI Stream Processing & Chunk Fence Healing**
    - Line-Buffered Chunk Processing: Incremental line buffering prior to SSE parsing. Never assume a single network chunk contains a complete semantic token or SSE event.
    - Dynamic Markdown & Delimiter Healing: Detect unclosed fences (code blocks, quotes, structural tables) and auto-heal in rendering buffer to prevent UI layout breakage during streaming.
    - Frame-Throttled Rendering (`requestAnimationFrame`): Batch high-velocity streaming text updates to 60fps to prevent main-thread UI lockups.
    - Idempotency & Lifecycle Controls: Every streaming request must provide an explicit cancellation handle (`AbortController`), an idempotency key header, and visual indicators for all stream states.
11. **ADR-11: Zero-Regression Multi-Tier UI Quality Gate**
    - Strict Type-Level Gatekeeping: Zero-warning/zero-error TypeScript and framework diagnostic compilation prior to build (`npm run check`).
    - Headless Unit & State Testing: Business logic, reactive stores/state machines, cryptographic operations, and protocol parsers tested via in-memory runner (Vitest).
    - Contract-Driven Mock Streams: UI streaming consumers tested with synthetic, reproducible stream generators simulating token delays, network drops, and corrupted chunks.
    - End-to-End User Flow Verification: Critical paths tested in automated headless browser environments before deployments.
12. **ADR-12: Zero-Dependency URL-State Hydration & Deep Linking**
    - Native History/URL Synchronization: Active resource identifiers and multi-step view stages synchronize directly with browser location (`pushState`/`replaceState` or hash parameters) without heavy third-party routing dependencies.
    - Bidirectional Hydration: Initial mount hydrates state from URL parameters; UI state changes reflect into query/hash parameters without full-page reloads.
    - Graceful Fallback: Missing or invalid route entities recover gracefully to default state with polite user notification.
13. **ADR-13: Rigid Architectural Design System & Universal Accessibility Standards**
    - Geometric Design Tokens (Strict 0px Radius): Universal `border-radius: 0px !important` across all primitives (buttons, inputs, cards, dialogs, badges). No rounded pills or circular avatars.
    - High-Density Typography & Monospacing: Structural headers and technical metadata prioritize clean sans-serif and monospace fonts.
    - Mandatory Focus Rings & Keyboard Navigation: Explicit, high-contrast 2px focus ring (`:focus-visible`). Modals and drawers must implement focus trapping and support `Escape` key cancellation.
    - Accessible Dynamic AI Announcers: Streaming outputs and notifications must use appropriate ARIA live regions (`aria-live="polite"` or `role="status"`).
