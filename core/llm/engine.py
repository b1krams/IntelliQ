"""IntelliQ Multi-Provider LLM Orchestration Engine with Free-Tier Cascade & Failover."""
import base64
import io
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import AsyncGenerator
from typing import Any

from core.config import get_settings
from core.db import get_uploaded_file_bytes
from core.llm.adapters import stream_gemini, stream_openai_compatible
from core.llm.models import (
    ActorEnum,
    AiInsights,
    AssumptionRisk,
    Attachment,
    Brd,
    Epic,
    FunctionalRequirement,
    HistoryItem,
    NonFunctionalRequirement,
    StageEnum,
    Stakeholder,
    StatusEnum,
    Story,
    TestCase,
    WorkflowRequest,
    WorkflowState,
)
from core.telemetry import emit_llm_execution_metrics

logger = logging.getLogger("intelliq.llm.engine")


SYSTEM_PROMPT = """You are IntelliQ, an expert enterprise requirements architect and test engineering AI adhering to Deloitte Quality Assurance and Architecture Standards.
Your mission is to transform raw transcripts, architectural diagrams, and documentation into rigorous, audit-ready software specifications.

You enforce:
1. Complete traceability from Business Requirements -> Epics -> User Stories -> JIRA Test Cases.
2. Strict INVEST criteria for User Stories with clear Gherkin (Given-When-Then) acceptance criteria.
3. High-rigor test coverage including positive path, negative exceptions, boundary conditions, and security validation.
4. Always respond with strict, valid JSON matching the exact schema provided. Never output conversational prose outside the JSON payload."""


def _extract_docx_text(raw_bytes: bytes) -> str:
    """Extract plain text from .docx OpenXML package using standard zipfile & xml."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
            xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            texts = [
                node.text for node in tree.iter()
                if node.tag.endswith("}t") and node.text
            ]
            return "\n".join(texts)
    except Exception as e:
        logger.warning("Failed to extract docx text: %s", e)
        return ""


def extract_attachment_context(attachments: list[Attachment]) -> tuple[str, list[dict[str, Any]]]:
    """
    Extract readable text content from attachments (txt, vtt, docx, csv, md, json)
    and prepare valid binary media payloads for multi-modal LLM models (pdf, images).
    """
    doc_texts: list[str] = []
    media_attachments: list[dict[str, Any]] = []

    for att in attachments:
        name = att.name or "document.txt"
        ext = os.path.splitext(name)[1].lower()
        mime = (att.mime_type or "").lower()

        # 1. Text already pre-extracted in frontend client
        if att.text_content and att.text_content.strip():
            doc_texts.append(f"--- START FILE: {name} ---\n{att.text_content.strip()}\n--- END FILE: {name} ---")
            continue

        # 2. Retrieve raw bytes from base64 or S3 / memory cache
        raw_bytes: bytes | None = None
        if att.base64_data:
            try:
                raw_bytes = base64.b64decode(att.base64_data)
            except Exception:
                pass
        if not raw_bytes and att.s3_key:
            raw_bytes = get_uploaded_file_bytes(att.s3_key)

        if not raw_bytes:
            continue

        # 3. Text-based documents: decode to UTF-8
        if ext in (".txt", ".vtt", ".md", ".csv", ".tsv", ".json", ".log") or mime.startswith("text/"):
            try:
                decoded = raw_bytes.decode("utf-8", errors="replace").strip()
                if decoded:
                    doc_texts.append(f"--- START FILE: {name} ---\n{decoded}\n--- END FILE: {name} ---")
            except Exception as e:
                logger.warning("Failed to decode text file %s: %s", name, e)

        # 4. Word Documents (.docx): extract XML text from document.xml
        elif ext == ".docx" or "wordprocessingml" in mime:
            docx_text = _extract_docx_text(raw_bytes)
            if docx_text:
                doc_texts.append(f"--- START FILE: {name} (Word Document) ---\n{docx_text}\n--- END FILE: {name} ---")

        # 5. PDF documents: native multimodal inline_data for Gemini
        elif ext == ".pdf" or mime == "application/pdf":
            b64 = att.base64_data or base64.b64encode(raw_bytes).decode("ascii")
            media_attachments.append({"name": name, "mime_type": "application/pdf", "base64_data": b64})
            # Also search for basic plain text streams for non-multimodal models
            try:
                import re
                text_chunks = re.findall(rb"\((.*?)\)\s*Tj", raw_bytes)
                if text_chunks:
                    extracted_pdf = " ".join([c.decode("utf-8", errors="ignore") for c in text_chunks[:500]])
                    if extracted_pdf.strip():
                        doc_texts.append(f"--- START FILE: {name} (PDF Summary) ---\n{extracted_pdf}\n--- END FILE: {name} ---")
            except Exception:
                pass

        # 6. Images: native multimodal inline_data for Gemini
        elif ext in (".png", ".jpg", ".jpeg", ".webp") or mime.startswith("image/"):
            b64 = att.base64_data or base64.b64encode(raw_bytes).decode("ascii")
            clean_mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
            media_attachments.append({"name": name, "mime_type": clean_mime, "base64_data": b64})

    combined_text = "\n\n".join(doc_texts)
    return combined_text, media_attachments


def _build_brd_prompt(user_prompt: str, feedback: str = "", document_context: str = "") -> str:
    prompt = "Generate a comprehensive, audit-ready Business Requirements Document (BRD) based strictly on the provided inputs and attached project documents.\n"
    if document_context:
        prompt += f"\n=== ATTACHED REQUIREMENTS DOCUMENTATION ===\n{document_context}\n"
    if user_prompt:
        prompt += f"\n=== USER REQUIREMENTS NOTES / INSTRUCTIONS ===\n{user_prompt}\n"
    if feedback:
        prompt += f"\n=== SPECIFIC USER REVISIONS / FEEDBACK ===\n{feedback}\n"

    prompt += """
CRITICAL INSTRUCTIONS:
1. The BRD MUST directly reflect the domain, functional requirements, and objectives specified in the attached documentation and user inputs above.
2. DO NOT hallucinate, substitute, or invent unrelated initiatives or generic templates (e.g. do NOT assume an unrelated serverless analytics or cloud migration unless explicitly stated in the input context).
3. Derive specific functional requirements (FR-01, FR-02...), measurable business objectives, and realistic domain stakeholders from the source material.

Return a JSON object conforming strictly to this structure:
{
  "title": "Project Title",
  "version": "1.0",
  "executive_summary": "High level summary directly grounded in the input context",
  "business_objectives": ["Objective 1", "Objective 2"],
  "stakeholders": [{"role": "Product Owner", "department": "Digital", "responsibilities": "Scope signoff"}],
  "in_scope": ["Feature A", "Feature B"],
  "out_of_scope": ["Deferred Item C"],
  "functional_requirements": [
    {"id": "FR-01", "title": "Requirement Title", "description": "Detailed description", "priority": "HIGH"}
  ],
  "non_functional_requirements": [
    {"category": "Performance", "specification": "Sub-500ms API response time at 99th percentile"}
  ],
  "assumptions_and_risks": [
    {"type": "RISK", "description": "Third-party API latency", "mitigation": "Circuit-breaker fallback"}
  ],
  "compliance_regulatory": ["SOC2 Type II", "GDPR Article 25"],
  "ai_insights": {
    "confidence_score": 0.96,
    "rationale_bullets": ["Synthesized core modules from source transcript/document", "Aligned with client specifications"],
    "ambiguities_flagged": ["Need confirmation on exact authentication provider"],
    "suggested_actions": ["Review non-functional latency targets with infrastructure lead"]
  }
}
"""
    return prompt


def _build_epics_prompt(brd_dict: dict[str, Any], feedback: str = "") -> str:
    prompt = f"""Decompose the following approved Business Requirements Document into structured business Epics.
BRD Title: {brd_dict.get('title')}
Executive Summary: {brd_dict.get('executive_summary')}
Functional Requirements: {json.dumps(brd_dict.get('functional_requirements', []))}
"""
    if feedback:
        prompt += f"\nUser Revisions / Feedback:\n{feedback}\n"

    prompt += """
Return a JSON object conforming strictly to this structure:
{
  "epics": [
    {
      "id": "EPIC-01",
      "title": "Authentication & Access Control",
      "summary": "Implement enterprise SSO and RBAC enforcement.",
      "business_value": "Ensures zero-trust compliance and client tenant security.",
      "priority": "CRITICAL",
      "dependencies": [],
      "acceptance_criteria": ["All endpoints require valid JWT", "Rate-limiting enforced at perimeter"]
    }
  ],
  "ai_insights": {
    "confidence_score": 0.98,
    "rationale_bullets": ["Segmented requirements into modular agile deliverable epics"],
    "ambiguities_flagged": [],
    "suggested_actions": ["Confirm prioritization with scrum team"]
  }
}
"""
    return prompt


def _build_stories_prompt(
    epics_list: list[dict[str, Any]],
    feedback: str = "",
    target_epic_id: str | None = None,
    brd_dict: dict[str, Any] | None = None,
    user_prompt: str = "",
    existing_stories: list[dict[str, Any]] | None = None,
) -> str:
    brd = brd_dict or {}
    brd_title = brd.get("title", "")
    exec_summary = brd.get("executive_summary", "") or user_prompt
    objectives = brd.get("business_objectives", [])
    functional_reqs = brd.get("functional_requirements", [])
    in_scope = brd.get("in_scope", [])

    if target_epic_id:
        clean_target_id = target_epic_id.strip()
        target_epic = next((e for e in epics_list if e.get("id", "").strip().upper() == clean_target_id.upper()), None)
        if not target_epic:
            target_epic = {"id": clean_target_id, "title": f"Epic {clean_target_id}", "summary": "", "acceptance_criteria": []}

        # Find existing stories for this epic (if any)
        current_epic_stories = [
            s for s in (existing_stories or [])
            if s.get("epic_id", "").strip().upper() == clean_target_id.upper()
        ]

        prompt = f"""You are a Principal Product Owner & Agile Architect generating detailed, INVEST-compliant User Stories with Gherkin Acceptance Criteria.

=== BUSINESS REQUIREMENTS DOCUMENT (BRD) CONTEXT ===
Project / System Title: {brd_title or 'Enterprise Application'}
Executive Summary: {exec_summary}
Business Objectives:
{json.dumps(objectives, indent=2) if objectives else 'None specified'}
Key Functional Requirements from BRD:
{json.dumps(functional_reqs, indent=2) if functional_reqs else 'None specified'}
In Scope:
{json.dumps(in_scope, indent=2) if in_scope else 'None specified'}

=== TARGET EPIC FOR STORY GENERATION ===
Epic ID: {target_epic.get('id', clean_target_id)}
Epic Title: {target_epic.get('title', '')}
Epic Narrative / Business Value: {target_epic.get('business_value') or target_epic.get('summary', '')}
Epic Acceptance Criteria:
{json.dumps(target_epic.get('acceptance_criteria', []), indent=2)}

=== SOLUTION ARCHITECTURE EPICS OVERVIEW ===
{json.dumps([{'id': e.get('id'), 'title': e.get('title'), 'summary': e.get('summary')} for e in epics_list], indent=2)}
"""

        if current_epic_stories:
            prompt += f"""
=== CURRENT STORIES FOR THIS EPIC (BEING REGENERATED/REFINED) ===
{json.dumps([{'id': s.get('id'), 'title': s.get('title'), 'user_role': s.get('user_role'), 'capability': s.get('capability')} for s in current_epic_stories], indent=2)}
Note: The user is REGENERATING or REFINING stories for this specific epic. Produce improved, highly relevant user stories that directly fulfill this Epic's scope and acceptance criteria.
"""

        if feedback:
            prompt += f"\n=== USER REFINEMENT FEEDBACK / INSTRUCTIONS ===\n{feedback}\n"

        prompt += f"""
=== CRITICAL GENERATION RULES ===
1. STRICT RELEVANCE: Every story MUST be directly derived from Epic '{target_epic.get('id', clean_target_id)}: {target_epic.get('title')}' and the BRD functional requirements.
2. NO DISCONNECTED TEMPLATES: Do NOT generate generic authentication, JWT token, or infrastructure stories unless Epic '{target_epic.get('id', clean_target_id)}' explicitly requires them. The personas ('user_role'), capabilities, and acceptance criteria MUST reflect the actual business domain (e.g. healthcare, e-commerce, banking, logistics, etc. as described in the BRD).
3. EPIC ID ENFORCEMENT: Every story's 'epic_id' attribute MUST be set to '{target_epic.get('id', clean_target_id)}'.
4. INVEST GUIDELINES: Stories must be Independent, Negotiable, Valuable, Estimable, Small, and Testable with 2 to 4 stories generated.
5. GHERKIN CRITERIA: Include at least 2 detailed Gherkin acceptance criteria per story formatted as 'Given [condition], When [action], Then [expected outcome]'.
"""
    else:
        prompt = f"""You are a Principal Product Owner & Agile Architect generating detailed, INVEST-compliant User Stories with Gherkin Acceptance Criteria across all solution epics.

=== BUSINESS REQUIREMENTS DOCUMENT (BRD) CONTEXT ===
Project / System Title: {brd_title or 'Enterprise Application'}
Executive Summary: {exec_summary}
Business Objectives:
{json.dumps(objectives, indent=2) if objectives else 'None specified'}
Key Functional Requirements from BRD:
{json.dumps(functional_reqs, indent=2) if functional_reqs else 'None specified'}

=== EPICS TO IMPLEMENT ===
{json.dumps(epics_list, indent=2)}
"""
        if feedback:
            prompt += f"\n=== USER REFINEMENT FEEDBACK / INSTRUCTIONS ===\n{feedback}\n"

        prompt += """
=== CRITICAL GENERATION RULES ===
1. Generate 2 to 3 detailed, INVEST-compliant user stories for EACH epic listed above.
2. Every story MUST explicitly link to its parent epic by setting 'epic_id' to that epic's ID.
3. Stories MUST reflect the specific business domain in the BRD and the parent epic's acceptance criteria.
"""

    prompt += """
Return a JSON object conforming strictly to this structure:
{
  "stories": [
    {
      "id": "US-101",
      "epic_id": "EPIC-01",
      "title": "<Concise, action-oriented story title specific to this epic>",
      "user_role": "<Specific domain persona, e.g. Store Manager, Patient, Dispatcher>",
      "capability": "<Specific business capability or action to perform>",
      "benefit": "<Measurable business or customer value achieved>",
      "priority": "MUST_HAVE",
      "story_points": 3,
      "acceptance_criteria_gherkin": [
        "Given <initial context or precondition>, When <domain action occurs>, Then <expected system response>",
        "Given <invalid data or edge case>, When <action attempted>, Then <appropriate validation or error handling>"
      ],
      "technical_notes": "<Key implementation notes, API routes, or data validations>"
    }
  ],
  "ai_insights": {
    "confidence_score": 0.98,
    "rationale_bullets": ["Stories directly address the target Epic's acceptance criteria and BRD functional specifications"],
    "ambiguities_flagged": [],
    "suggested_actions": ["Review story point estimations in sprint planning"]
  }
}
"""
    return prompt


def _build_test_cases_prompt(
    stories_list: list[dict[str, Any]],
    feedback: str = "",
    target_story_id: str | None = None,
) -> str:
    if target_story_id:
        target_clean = target_story_id.strip()
        matched = [s for s in stories_list if s.get("id") == target_clean]
        story_obj = matched[0] if matched else None

        if story_obj:
            user_role = story_obj.get("user_role", "user")
            capability = story_obj.get("capability", "")
            benefit = story_obj.get("benefit", "")
            ac_list = story_obj.get("acceptance_criteria_gherkin", [])
            epic_id = story_obj.get("epic_id", "")
            title = story_obj.get("title", "")
            prompt = f"""Generate production JIRA-compatible Test Cases with explicit numbered steps and expected results specifically for User Story {target_clean}.
Story ID: {target_clean}
Epic ID: {epic_id}
Title: {title}
Persona / Narrative: As a {user_role}, I want to {capability}, so that {benefit}.
Story Points: {story_obj.get('story_points', 3)}
Priority: {story_obj.get('priority', 'MUST_HAVE')}
Acceptance Criteria (Gherkin Given-When-Then):
{json.dumps(ac_list, indent=2)}

Test Engineering Instructions:
- Synthesize 3 to 5 comprehensive test cases specifically for this user story.
- Every test case must reference story_id: "{target_clean}" and epic_id: "{epic_id}".
- Include thorough coverage across POSITIVE (happy path), NEGATIVE (error handling, invalid inputs), BOUNDARY (thresholds, rate limits), and SECURITY (authz, input validation) test types.
- Ensure all steps have clear actions and explicit expected results.
"""
        else:
            prompt = f"""Generate production JIRA-compatible Test Cases with explicit numbered steps and expected results specifically for User Story {target_clean}.
User Stories Context:
{json.dumps(stories_list)}
"""
        if feedback:
            prompt += f"\nCustom Prompt / Test Engineering Focus for {target_clean}:\n{feedback}\n"
    else:
        prompt = f"""Generate production JIRA-compatible Test Cases with explicit numbered steps and expected results based on these User Stories.
User Stories:
{json.dumps(stories_list)}
"""
        if feedback:
            prompt += f"\nUser Revisions / Feedback:\n{feedback}\n"

    prompt += """
Return a JSON object conforming strictly to this structure:
{
  "test_cases": [
    {
      "id": "TC-001",
      "story_id": "US-101",
      "epic_id": "EPIC-01",
      "title": "Verify HTTP 401 on Expired Cognito Bearer Token",
      "test_type": "NEGATIVE",
      "priority": "HIGH",
      "preconditions": ["Cognito user pool is configured", "Expired token is generated"],
      "steps": [
        {"step_number": 1, "action": "Send GET /api/workflows with expired Bearer token", "expected_result": "API gateway forwards request to auth middleware"},
        {"step_number": 2, "action": "Inspect HTTP response status and body", "expected_result": "Response status is HTTP 401 with error 'Token has expired'"}
      ],
      "postconditions": "No session state created in DynamoDB",
      "test_data": "Expired JWT with exp timestamp in the past"
    }
  ],
  "ai_insights": {
    "confidence_score": 0.99,
    "rationale_bullets": ["Generated positive, negative, and edge validation test suites", "Formatted for direct JIRA / Xray import"],
    "ambiguities_flagged": [],
    "suggested_actions": ["Import directly to JIRA via the exported Excel workbook"]
  }
}
"""
    return prompt


async def execute_cascade_stream(
    system_instruction: str,
    prompt: str,
    stage: str,
    attachments: list[dict[str, Any]] | None = None,
) -> AsyncGenerator[str, None]:
    """Execute LLM call across free-tier cascade with automated failover. Strictly never generates mock data."""
    settings = get_settings()
    start_time = time.time()
    errors: list[str] = []

    # 1. Primary: Google Gemini API Free Tier with high-availability model cascade
    if settings.gemini_api_key and settings.gemini_model:
        primary_model = settings.gemini_model.strip()
        candidate_models = [primary_model]
        for fallback in ("gemini-2.5-flash", "gemini-2.5-flash-lite"):
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        for model_name in candidate_models:
            try:
                logger.info("Calling Gemini (%s) for stage %s...", model_name, stage)
                token_count = 0
                async for token in stream_gemini(
                    api_key=settings.gemini_api_key,
                    model=model_name,
                    system_instruction=system_instruction,
                    prompt=prompt,
                    attachments=attachments,
                ):
                    token_count += 1
                    yield token
                latency = (time.time() - start_time) * 1000
                emit_llm_execution_metrics("Gemini", model_name, stage, latency, completion_tokens=token_count)
                return
            except Exception as e:
                err_msg = f"Gemini ({model_name}): {e}"
                logger.warning("Gemini call with %s failed (%s), trying fallback model...", model_name, e)
                errors.append(err_msg)
    elif not settings.gemini_api_key:
        errors.append("GEMINI_API_KEY is not configured")
    elif not settings.gemini_model:
        errors.append("GEMINI_MODEL is not configured")

    # 2. Secondary: Groq Cloud Free Tier
    if settings.groq_api_key and settings.groq_model:
        model_name = settings.groq_model.strip()
        try:
            logger.info("Calling Groq Cloud (%s) for stage %s...", model_name, stage)
            token_count = 0
            endpoint = "https://api.groq.com/openai/v1/chat/completions"
            async for token in stream_openai_compatible(
                endpoint_url=endpoint,
                api_key=settings.groq_api_key,
                model=model_name,
                system_instruction=system_instruction,
                prompt=prompt,
            ):
                token_count += 1
                yield token
            latency = (time.time() - start_time) * 1000
            emit_llm_execution_metrics("Groq", model_name, stage, latency, completion_tokens=token_count)
            return
        except Exception as e:
            err_msg = f"Groq ({model_name}): {e}"
            logger.warning("Groq Cloud call failed (%s)...", e)
            errors.append(err_msg)
    elif not settings.groq_api_key:
        errors.append("GROQ_API_KEY is not configured")
    elif not settings.groq_model:
        errors.append("GROQ_MODEL is not configured")

    # 3. Handle failure strictly - NEVER generate mock content
    technical_err = f"All LLM providers in cascade failed for stage '{stage}'. " + "; ".join(errors)
    logger.error(technical_err)
    raise RuntimeError(technical_err)


def _generate_mock_stage_payload(stage: str, prompt: str) -> str:
    """Generate realistic structured JSON payload grounded in prompt context for development."""
    derived_title = "Enterprise Requirements Specification"
    derived_summary = "Structured requirements specification synthesized from provided business documentation."

    # Dynamically extract topic / project name from prompt if present
    for line in prompt.split("\n"):
        line_clean = line.strip()
        lower = line_clean.lower()
        if lower.startswith(("project:", "system:", "initiative:", "title:")):
            val = line_clean.split(":", 1)[1].strip()
            if val and len(val) > 2:
                derived_title = val
                derived_summary = f"Comprehensive business requirements specification for {val}."
                break
        elif lower.startswith("--- start file:"):
            file_name = line_clean.split(":", 1)[1].replace("---", "").strip()
            base_name = os.path.splitext(file_name)[0].replace("_", " ").title()
            derived_title = f"{base_name} System"
            derived_summary = f"Requirements synthesized from attached document '{file_name}'."
            break
        elif "audit testing" in lower or "automate audit" in lower:
            derived_title = "Automated Audit & Quality Assurance Platform"
            derived_summary = "Automated compliance and audit test verification engine."
            break

    if stage in ("intake", "brd"):
        data = {
            "title": derived_title,
            "version": "1.0",
            "executive_summary": derived_summary,
            "business_objectives": [
                f"Implement core capabilities defined for {derived_title}",
                "Achieve sub-500ms transactional response latency",
                "Ensure regulatory compliance with SOC2 Type II and GDPR",
            ],
            "stakeholders": [
                {"role": "Engagement Partner", "department": "Business Architecture", "responsibilities": "Attestation sign-off"},
                {"role": "Lead Architect", "department": "Engineering", "responsibilities": "Technical design approval"},
            ],
            "in_scope": [
                f"Core {derived_title} workflows",
                "Role-based access control and tenant security",
                "Automated JIRA test case packaging and export",
            ],
            "out_of_scope": ["Legacy mainframe maintenance"],
            "functional_requirements": [
                {"id": "FR-01", "title": "Core Module Intake", "description": f"Intake and processing for {derived_title}", "priority": "CRITICAL"},
                {"id": "FR-02", "title": "Automated BRD Synthesis", "description": "Synthesis of user documentation into formal requirements", "priority": "HIGH"},
                {"id": "FR-03", "title": "Traceability Matrix & Export", "description": "Full end-to-end audit traceability to JIRA test suites", "priority": "HIGH"},
            ],
            "non_functional_requirements": [
                {"category": "Cost", "specification": "Scale-to-zero serverless architecture with $0 idle footprint"},
                {"category": "Latency", "specification": "First token streaming response under 400ms"},
            ],
            "assumptions_and_risks": [
                {"type": "RISK", "description": "Third-party dependency latency", "mitigation": "Circuit-breaker and cached fallback policies"},
            ],
            "compliance_regulatory": ["SOC2 Type II", "WCAG 2.1 AAA Accessibility"],
            "ai_insights": {
                "confidence_score": 0.98,
                "rationale_bullets": [
                    f"Successfully mapped requirements to {derived_title} scope",
                    "Enforced rigid architectural controls and high contrast UI standards",
                ],
                "ambiguities_flagged": [],
                "suggested_actions": ["Review generated epics in next stage"],
            },
        }
    elif stage == "epics":
        data = {
            "epics": [
                {
                    "id": "EPIC-01",
                    "title": "Multi-Modal Document Intake & S3 Direct Upload",
                    "summary": "Ingest transcripts, diagrams, and PDFs without routing bytes through Lambda.",
                    "business_value": "Prevents Lambda payload limits and scales file handling to zero cost.",
                    "priority": "CRITICAL",
                    "dependencies": [],
                    "acceptance_criteria": ["Presigned PUT URLs generated with 50MB ceiling", "Client calculates SHA-256 digest"],
                },
                {
                    "id": "EPIC-02",
                    "title": "Zero-SDK Streaming Requirements Engine",
                    "summary": "Direct HTTP/2 SSE streaming orchestration through Gemini and Groq cascade.",
                    "business_value": "Eliminates heavy vendor SDK cold start penalties and package bloat.",
                    "priority": "HIGH",
                    "dependencies": ["EPIC-01"],
                    "acceptance_criteria": ["Cold starts under 400ms", "Graceful failover on HTTP 429"],
                },
                {
                    "id": "EPIC-03",
                    "title": "JIRA Test Case & Traceability Export Matrix",
                    "summary": "Generate formatted Excel workbook mapping requirements to test suites.",
                    "business_value": "Accelerates QA signoff and integrates directly with Jira/Xray workflows.",
                    "priority": "HIGH",
                    "dependencies": ["EPIC-02"],
                    "acceptance_criteria": ["Standard JIRA column headers", "Formulas and styled summary sheets"],
                },
            ],
            "ai_insights": {
                "confidence_score": 0.97,
                "rationale_bullets": ["Decomposed BRD into 3 modular epics with clean dependency chaining"],
                "ambiguities_flagged": [],
                "suggested_actions": ["Proceed to User Story generation"],
            },
        }
    elif stage == "stories":
        data = {
            "stories": [
                {
                    "id": "STORY-101",
                    "epic_id": "EPIC-01",
                    "title": "S3 Presigned URL Generation Endpoint",
                    "user_role": "Authenticated Client",
                    "capability": "request a presigned PUT URL with content-length restrictions",
                    "benefit": "upload large transcripts directly to S3 without hitting Lambda memory ceilings",
                    "priority": "MUST_HAVE",
                    "story_points": 3,
                    "acceptance_criteria_gherkin": [
                        "Given an authenticated user, When POST /api/upload/presign is called with file metadata, Then return a signed S3 PUT URL valid for 60 minutes",
                        "Given an unauthenticated request, When /api/upload/presign is called, Then return HTTP 401 Unauthorized",
                    ],
                    "technical_notes": "Enforce strict content-type and 50MB ceiling in core/db.py",
                },
                {
                    "id": "STORY-102",
                    "epic_id": "EPIC-02",
                    "title": "Line-Buffered SSE Stream Parser & Markdown Healer",
                    "user_role": "Frontend User",
                    "capability": "stream LLM tokens at 60fps without unclosed code fences or DOM layout thrashing",
                    "benefit": "experience smooth, real-time feedback during requirements generation",
                    "priority": "MUST_HAVE",
                    "story_points": 5,
                    "acceptance_criteria_gherkin": [
                        "Given a high-velocity SSE stream, When tokens arrive, Then batch updates via requestAnimationFrame",
                        "Given an incomplete markdown code block, When rendered, Then automatically close the fence in the UI buffer",
                    ],
                    "technical_notes": "Implemented in frontend/src/lib/stream_parser.ts",
                },
                {
                    "id": "STORY-103",
                    "epic_id": "EPIC-03",
                    "title": "JIRA-Compatible Excel (.xlsx) Packaging",
                    "user_role": "QA Lead",
                    "capability": "download test cases in native Excel format with traceability columns",
                    "benefit": "import directly into JIRA without manual CSV formatting or conversion scripts",
                    "priority": "MUST_HAVE",
                    "story_points": 3,
                    "acceptance_criteria_gherkin": [
                        "Given a completed workflow session, When export is triggered, Then generate an openpyxl workbook with Summary, Epics, Stories, and Test Cases sheets",
                        "Given the Test Cases sheet, When imported to JIRA, Then issue types, priorities, and steps map cleanly",
                    ],
                    "technical_notes": "Utilizes openpyxl in lambdas/api_handler/handler.py",
                },
            ],
            "ai_insights": {
                "confidence_score": 0.98,
                "rationale_bullets": ["Stories adhere to INVEST format with comprehensive Given-When-Then criteria"],
                "ambiguities_flagged": [],
                "suggested_actions": ["Proceed to JIRA Test Case generation"],
            },
        }
    else:  # test_cases or export
        data = {
            "test_cases": [
                {
                    "id": "TC-001",
                    "story_id": "STORY-101",
                    "epic_id": "EPIC-01",
                    "title": "Verify S3 Presigned URL Rejects Oversized File Uploads",
                    "test_type": "BOUNDARY",
                    "priority": "CRITICAL",
                    "preconditions": ["User has valid Cognito session"],
                    "steps": [
                        {"step_number": 1, "action": "Request presigned URL for 60MB file", "expected_result": "API responds with validation error rejecting file > 50MB"},
                        {"step_number": 2, "action": "Attempt direct PUT using crafted URL exceeding limit", "expected_result": "S3 rejects payload with EntityTooLarge"},
                    ],
                    "postconditions": "No orphan S3 object created",
                    "test_data": "60MB dummy binary file",
                },
                {
                    "id": "TC-002",
                    "story_id": "STORY-102",
                    "epic_id": "EPIC-02",
                    "title": "Validate 60fps RequestAnimationFrame Throttling Under High-Velocity Stream",
                    "test_type": "PERFORMANCE",
                    "priority": "HIGH",
                    "preconditions": ["Browser performance observer active"],
                    "steps": [
                        {"step_number": 1, "action": "Transmit 250 tokens/second burst from mock backend", "expected_result": "Non-reactive buffer accumulates chunks"},
                        {"step_number": 2, "action": "Measure DOM update frequency", "expected_result": "Max 60 frame flushes per second; zero layout jank"},
                    ],
                    "postconditions": "Stream completes with intact JSON/markdown state",
                    "test_data": "High velocity SSE token burst",
                },
                {
                    "id": "TC-003",
                    "story_id": "STORY-103",
                    "epic_id": "EPIC-03",
                    "title": "Verify JIRA Test Case Excel Workbook Conformance",
                    "test_type": "POSITIVE",
                    "priority": "HIGH",
                    "preconditions": ["Workflow contains at least 3 test cases"],
                    "steps": [
                        {"step_number": 1, "action": "Click 'Export JIRA Package' and download .xlsx", "expected_result": "HTTP 200 with application/vnd.openxmlformats file"},
                        {"step_number": 2, "action": "Inspect workbook sheets and headers", "expected_result": "Contains Summary, Epics, Stories, and Test Cases with correct column keys"},
                    ],
                    "postconditions": "Audit log records EXPORT event",
                    "test_data": "Current workflow state",
                },
            ],
            "ai_insights": {
                "confidence_score": 0.99,
                "rationale_bullets": [
                    "Generated comprehensive boundary, performance, and positive test cases",
                    "Standardized for seamless JIRA Xray import",
                ],
                "ambiguities_flagged": [],
                "suggested_actions": ["Download JIRA Excel workbook to initiate testing phase"],
            },
        }
    return json.dumps(data, indent=2)


async def process_workflow_action(
    state: WorkflowState,
    request: WorkflowRequest,
    user_id: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Main engine orchestrator processing user actions, streaming token deltas,
    and yielding the updated canonical WorkflowState.
    """
    action = request.action
    user_prompt = request.user_prompt or state.user_prompt or state.title
    feedback = request.feedback

    # Maintain session context across actions
    all_attachments = request.attachments or state.attachments or []
    if request.attachments:
        state.attachments = request.attachments
    if request.user_prompt:
        state.user_prompt = request.user_prompt

    # Extract text and valid multimodal media from all available attachments
    doc_text, media_attachments = extract_attachment_context(all_attachments)

    # Clean generic session placeholders if documents are present
    clean_user_prompt = user_prompt
    if clean_user_prompt and clean_user_prompt.startswith("Session ") and doc_text:
        clean_user_prompt = ""

    # Determine prompt and stage based on action
    target_stage = state.current_stage
    system_instruction = SYSTEM_PROMPT

    if action in ("init_workflow", "generate_brd", "refine_brd"):
        target_stage = StageEnum.BRD
        prompt = _build_brd_prompt(clean_user_prompt, feedback, document_context=doc_text)
    elif action in ("generate_epics", "refine_epics"):
        target_stage = StageEnum.EPICS
        brd_dict = state.brd.model_dump() if state.brd else {"title": state.title, "executive_summary": user_prompt}
        prompt = _build_epics_prompt(brd_dict, feedback)
    elif action in ("generate_stories", "refine_stories"):
        target_stage = StageEnum.STORIES
        epics_list = [e.model_dump() for e in state.epics]
        brd_dict = state.brd.model_dump() if state.brd else {"title": state.title, "executive_summary": user_prompt}
        existing_stories = [s.model_dump() for s in state.stories]
        prompt = _build_stories_prompt(
            epics_list=epics_list,
            feedback=feedback,
            target_epic_id=request.target_id,
            brd_dict=brd_dict,
            user_prompt=user_prompt,
            existing_stories=existing_stories,
        )
    elif action in ("generate_test_cases", "refine_test_cases"):
        target_stage = StageEnum.TEST_CASES
        stories_list = [s.model_dump() for s in state.stories]
        prompt = _build_test_cases_prompt(stories_list, feedback, target_story_id=request.target_id)
    elif action == "approve_stage":
        # Stage gate advancement
        stage_order = [StageEnum.INTAKE, StageEnum.BRD, StageEnum.EPICS, StageEnum.STORIES, StageEnum.TEST_CASES, StageEnum.EXPORT]
        current_idx = stage_order.index(state.current_stage) if state.current_stage in stage_order else 0
        next_stage = stage_order[min(current_idx + 1, len(stage_order) - 1)]
        state.current_stage = next_stage
        state.status = StatusEnum.APPROVED
        state.history.append(
            HistoryItem(
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                actor=ActorEnum.USER,
                action="APPROVE_STAGE",
                details=f"User approved stage {target_stage.value}. Advanced to {next_stage.value}.",
            )
        )
        yield {"event": "state", "data": state.model_dump()}
        return
    else:
        target_stage = StageEnum.BRD
        prompt = _build_brd_prompt(clean_user_prompt, feedback, document_context=doc_text)

    # Stream tokens from LLM cascade
    accumulated_chunks: list[str] = []
    try:
        async for token in execute_cascade_stream(
            system_instruction=system_instruction,
            prompt=prompt,
            stage=target_stage.value,
            attachments=media_attachments,
        ):
            accumulated_chunks.append(token)
            yield {"event": "token", "data": token}
    except Exception as exc:
        logger.error("LLM streaming execution failed for stage %s: %s", target_stage.value, exc)
        state.status = StatusEnum.ERROR
        state.ai_insights.rationale_bullets = [f"Technical Error: {exc}"]
        state.history.append(
            HistoryItem(
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                actor=ActorEnum.AGENT,
                action=f"ERROR_{target_stage.value.upper()}",
                details=f"Technical failure: {exc}",
            )
        )
        yield {"event": "state", "data": state.model_dump()}
        raise exc

    full_output = "".join(accumulated_chunks).strip()

    # Parse and incorporate generated structured output
    try:
        # Strip potential markdown fences and isolate valid JSON object payload
        clean_json = full_output.strip()
        start_idx = clean_json.find("{")
        end_idx = clean_json.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            clean_json = clean_json[start_idx : end_idx + 1]
        elif clean_json.startswith("```"):
            lines = clean_json.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_json = "\n".join(lines).strip()

        parsed = json.loads(clean_json)

        if target_stage == StageEnum.BRD:
            parsed_sh: list[Stakeholder] = []
            for s in parsed.get("stakeholders", []):
                if isinstance(s, dict):
                    try:
                        parsed_sh.append(Stakeholder(**s))
                    except Exception:
                        parsed_sh.append(
                            Stakeholder(
                                role=str(s.get("role") or "Stakeholder"),
                                name=str(s.get("name") or ""),
                                department=str(s.get("department") or ""),
                                responsibilities=str(s.get("responsibilities") or ""),
                            )
                        )
                elif isinstance(s, str):
                    parsed_sh.append(Stakeholder(role=s))

            parsed_fr: list[FunctionalRequirement] = []
            for f in parsed.get("functional_requirements", []):
                if isinstance(f, dict):
                    try:
                        parsed_fr.append(FunctionalRequirement(**f))
                    except Exception:
                        parsed_fr.append(
                            FunctionalRequirement(
                                id=str(f.get("id") or f"FR-{len(parsed_fr) + 1:02d}"),
                                title=str(f.get("title") or "Functional Requirement"),
                                description=str(f.get("description") or ""),
                            )
                        )

            parsed_nfr: list[NonFunctionalRequirement] = []
            for n in parsed.get("non_functional_requirements", []):
                if isinstance(n, dict):
                    try:
                        parsed_nfr.append(NonFunctionalRequirement(**n))
                    except Exception:
                        parsed_nfr.append(
                            NonFunctionalRequirement(
                                category=str(n.get("category") or "General"),
                                specification=str(n.get("specification") or ""),
                            )
                        )

            parsed_ar: list[AssumptionRisk] = []
            for a in parsed.get("assumptions_and_risks", []):
                if isinstance(a, dict):
                    try:
                        parsed_ar.append(AssumptionRisk(**a))
                    except Exception:
                        parsed_ar.append(
                            AssumptionRisk(
                                description=str(a.get("description") or ""),
                                mitigation=str(a.get("mitigation") or ""),
                            )
                        )

            state.brd = Brd(
                title=parsed.get("title") or state.title or "Business Requirements Document",
                version=parsed.get("version", "1.0"),
                executive_summary=parsed.get("executive_summary", ""),
                business_objectives=[str(x) for x in parsed.get("business_objectives", []) if x],
                stakeholders=parsed_sh,
                in_scope=[str(x) for x in parsed.get("in_scope", []) if x],
                out_of_scope=[str(x) for x in parsed.get("out_of_scope", []) if x],
                functional_requirements=parsed_fr,
                non_functional_requirements=parsed_nfr,
                assumptions_and_risks=parsed_ar,
                compliance_regulatory=[str(x) for x in parsed.get("compliance_regulatory", []) if x],
            )
            state.title = state.brd.title
        elif target_stage == StageEnum.EPICS:
            raw_epics = parsed.get("epics", [])
            parsed_epics: list[Epic] = []
            for item in raw_epics:
                if not isinstance(item, dict):
                    continue
                try:
                    parsed_epics.append(Epic(**item))
                except Exception as parse_err:
                    logger.warning("Error parsing epic item, attempting recovery: %s", parse_err)
                    try:
                        recovered = Epic(
                            id=str(item.get("id") or "EPIC-01"),
                            title=str(item.get("title") or "Epic"),
                            summary=str(item.get("summary") or ""),
                            business_value=str(item.get("business_value") or ""),
                            priority=item.get("priority", "HIGH"),
                            dependencies=item.get("dependencies", []),
                            acceptance_criteria=item.get("acceptance_criteria", []),
                        )
                        parsed_epics.append(recovered)
                    except Exception as rec_err:
                        logger.error("Failed to recover epic item: %s", rec_err)
            state.epics = parsed_epics
        elif target_stage == StageEnum.STORIES:
            raw_stories = parsed.get("stories") or parsed.get("user_stories") or []
            if isinstance(parsed, list):
                raw_stories = parsed
            parsed_stories: list[Story] = []
            for item in raw_stories:
                if not isinstance(item, dict):
                    continue
                try:
                    parsed_stories.append(Story(**item))
                except Exception as parse_err:
                    logger.warning("Error parsing story item, attempting recovery: %s", parse_err)
                    try:
                        ac_field = item.get("acceptance_criteria_gherkin") or item.get("acceptance_criteria") or []
                        recovered = Story(
                            id=str(item.get("id") or item.get("story_id") or ""),
                            epic_id=str(item.get("epic_id") or request.target_id or ""),
                            title=str(item.get("title") or "User Story"),
                            user_role=str(item.get("user_role") or item.get("role") or "User"),
                            capability=str(item.get("capability") or item.get("action") or ""),
                            benefit=str(item.get("benefit") or item.get("value") or ""),
                            priority=item.get("priority", "MUST_HAVE"),
                            story_points=item.get("story_points", 3),
                            acceptance_criteria_gherkin=ac_field,
                            technical_notes=str(item.get("technical_notes") or ""),
                        )
                        parsed_stories.append(recovered)
                    except Exception as rec_err:
                        logger.error("Failed to recover story item: %s", rec_err)
            if request.target_id:
                target_epic = request.target_id.strip()
                import re
                digits = re.findall(r"\d+", target_epic)
                prefix_num = int(digits[0]) * 100 if digits else 100

                def _is_target(epic_id_str: str) -> bool:
                    if not epic_id_str:
                        return False
                    s_clean = epic_id_str.strip().upper()
                    t_clean = target_epic.upper()
                    if s_clean == t_clean:
                        return True
                    s_digits = re.findall(r"\d+", s_clean)
                    t_digits = re.findall(r"\d+", t_clean)
                    if s_digits and t_digits and int(s_digits[0]) == int(t_digits[0]):
                        return True
                    return False

                # Stories belonging to any epic other than target_epic (normalized check)
                existing_others = [
                    s for s in state.stories
                    if not _is_target(s.epic_id)
                ]
                used_ids = {s.id for s in existing_others if s.id}

                # Deterministically assign clean sequential IDs (e.g. US-101.. for EPIC-01, US-201.. for EPIC-02)
                counter = 1
                for s in parsed_stories:
                    s.epic_id = target_epic
                    new_id = f"US-{prefix_num + counter}"
                    while new_id in used_ids:
                        counter += 1
                        new_id = f"US-{prefix_num + counter}"
                    s.id = new_id
                    used_ids.add(new_id)
                    counter += 1

                # Merge and deduplicate by story ID
                all_stories = existing_others + parsed_stories
                seen_ids: set[str] = set()
                deduped: list[Story] = []
                for s in all_stories:
                    if s.id and s.id not in seen_ids:
                        seen_ids.add(s.id)
                        deduped.append(s)

                state.stories = deduped
                # In iterative mode, remain in EPICS so user can continue with other epics
                state.current_stage = StageEnum.EPICS
            else:
                # Full story generation: ensure unique sequential IDs and deduplicate
                seen_ids: set[str] = set()
                deduped: list[Story] = []
                for s in parsed_stories:
                    if s.id in seen_ids or not s.id:
                        import re
                        digits = re.findall(r"\d+", s.epic_id or "")
                        prefix = int(digits[0]) * 100 if digits else 100
                        cnt = 1
                        cand = f"US-{prefix + cnt}"
                        while cand in seen_ids:
                            cnt += 1
                            cand = f"US-{prefix + cnt}"
                        s.id = cand
                    seen_ids.add(s.id)
                    deduped.append(s)
                state.stories = deduped
                state.current_stage = StageEnum.STORIES
        elif target_stage in (StageEnum.TEST_CASES, StageEnum.EXPORT):
            raw_tcs = parsed.get("test_cases", [])
            parsed_tcs: list[TestCase] = []
            for item in raw_tcs:
                if not isinstance(item, dict):
                    continue
                if isinstance(item.get("test_data"), (dict, list)):
                    item["test_data"] = json.dumps(item["test_data"], indent=2)
                if isinstance(item.get("postconditions"), list):
                    item["postconditions"] = "; ".join(str(x) for x in item["postconditions"])
                if isinstance(item.get("preconditions"), str):
                    item["preconditions"] = [item["preconditions"]]
                try:
                    parsed_tcs.append(TestCase(**item))
                except Exception as parse_err:
                    logger.warning("Error parsing test case item, attempting recovery: %s", parse_err)
                    try:
                        recovered = TestCase(
                            id=str(item.get("id") or ""),
                            story_id=str(item.get("story_id") or request.target_id or ""),
                            epic_id=str(item.get("epic_id") or ""),
                            title=str(item.get("title") or "Test Case"),
                            test_data=str(item.get("test_data") or ""),
                            postconditions=str(item.get("postconditions") or ""),
                        )
                        parsed_tcs.append(recovered)
                    except Exception:
                        pass
            if request.target_id:
                target_story = request.target_id.strip()
                import re
                digits = re.findall(r"\d+", target_story)
                prefix_num = int(digits[0]) * 10 if digits else 100

                # Test cases belonging to any story other than target_story (case-insensitive)
                existing_others = [
                    tc for tc in state.test_cases
                    if tc.story_id and tc.story_id.strip().upper() != target_story.upper()
                ]
                used_ids = {tc.id for tc in existing_others if tc.id}

                # Find epic_id for target_story if known
                matching_story = next(
                    (s for s in state.stories if s.id and s.id.strip().upper() == target_story.upper()),
                    None,
                )
                target_epic_id = matching_story.epic_id if matching_story else ""

                counter = 1
                for tc in parsed_tcs:
                    tc.story_id = target_story
                    if target_epic_id and not tc.epic_id:
                        tc.epic_id = target_epic_id
                    new_id = f"TC-{prefix_num + counter}"
                    while new_id in used_ids:
                        counter += 1
                        new_id = f"TC-{prefix_num + counter}"
                    tc.id = new_id
                    used_ids.add(new_id)
                    counter += 1

                all_tcs = existing_others + parsed_tcs
                seen_ids: set[str] = set()
                deduped_tcs: list[TestCase] = []
                for tc in all_tcs:
                    if tc.id and tc.id not in seen_ids:
                        seen_ids.add(tc.id)
                        deduped_tcs.append(tc)

                state.test_cases = deduped_tcs
                # In iterative mode, remain in STORIES stage so user can continue
                state.current_stage = StageEnum.STORIES
            else:
                seen_ids: set[str] = set()
                deduped_tcs: list[TestCase] = []
                for tc in parsed_tcs:
                    if tc.id and tc.id not in seen_ids:
                        seen_ids.add(tc.id)
                        deduped_tcs.append(tc)
                state.test_cases = deduped_tcs
                state.current_stage = StageEnum.TEST_CASES

        if "ai_insights" in parsed and isinstance(parsed["ai_insights"], dict):
            try:
                state.ai_insights = AiInsights(**parsed["ai_insights"])
            except Exception as ai_err:
                logger.warning("Error parsing ai_insights, keeping default: %s", ai_err)

        if not (
            (target_stage == StageEnum.STORIES and request.target_id)
            or (target_stage in (StageEnum.TEST_CASES, StageEnum.EXPORT) and request.target_id)
        ):
            state.current_stage = target_stage
        state.status = StatusEnum.REVIEW_REQUIRED
        state.history.append(
            HistoryItem(
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                actor=ActorEnum.AGENT,
                action=f"GENERATE_{target_stage.value.upper()}",
                details=f"Synthesized {target_stage.value.upper()} specification with confidence {state.ai_insights.confidence_score * 100:.1f}%.",
            )
        )

    except Exception as e:
        logger.error("Failed to parse LLM structured output: %s\nOutput was: %s", e, full_output[:300])
        state.status = StatusEnum.ERROR
        state.ai_insights.rationale_bullets = [f"Technical Error: LLM returned malformed structured output ({e})"]
        state.history.append(
            HistoryItem(
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                actor=ActorEnum.AGENT,
                action=f"PARSE_ERROR_{target_stage.value.upper()}",
                details=f"JSON parsing error: {e}",
            )
        )
        yield {"event": "state", "data": state.model_dump()}
        raise RuntimeError(f"Failed to parse LLM structured output: {e}")

    # Yield terminal updated state
    yield {"event": "state", "data": state.model_dump()}

