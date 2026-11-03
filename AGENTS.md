# Operational Rules & Architectural Constraints for AI Coding Agents

## Mission & Principles
**IntelliQ** is an enterprise-grade, scale-to-zero serverless AI application designed to run permanently with **$0 idle cost** by staying within AWS Always-Free tier thresholds. Every line of code, infrastructure construct, and data pattern must strictly conform to these rules.

## The Invariant Architectural Directives (ADR-01 through ADR-09)

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
7. **ADR-07: Reactive Frontend (Svelte 5 Runes + Deloitte Enterprise UI)**
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

