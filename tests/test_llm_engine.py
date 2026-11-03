"""Unit tests for multi-provider streaming orchestrator and free-tier cascade."""
import pytest
from core.llm.engine import (
    _build_brd_prompt,
    _build_epics_prompt,
    _build_stories_prompt,
    _build_test_cases_prompt,
    _generate_mock_stage_payload,
    process_workflow_action,
)
from core.llm.models import (
    StageEnum,
    StatusEnum,
    WorkflowRequest,
    WorkflowState,
)


def test_prompt_builders():
    """Verify that all stage prompt builders include key constraints and formatting contracts."""
    brd_p = _build_brd_prompt("User notes", "Refine objectives")
    assert "Business Requirements Document" in brd_p
    assert "Refine objectives" in brd_p

    epics_p = _build_epics_prompt({"title": "Test BRD", "functional_requirements": []})
    assert "EPIC-01" in epics_p

    stories_p = _build_stories_prompt([{"id": "EPIC-01"}], target_epic_id="EPIC-01")
    assert "INVEST-compliant" in stories_p
    assert "Gherkin" in stories_p

    tc_p = _build_test_cases_prompt([{"id": "US-101"}])
    assert "TC-001" in tc_p
    assert "JIRA-compatible" in tc_p


def test_mock_stage_payloads():
    """Verify mock payloads for each stage return valid JSON conforming to schemas."""
    import json
    for stage in ["intake", "brd", "epics", "stories", "test_cases"]:
        payload_str = _generate_mock_stage_payload(stage, "prompt")
        parsed = json.loads(payload_str)
        assert isinstance(parsed, dict)
        assert "ai_insights" in parsed


@pytest.mark.asyncio
async def test_process_workflow_action_streaming():
    """Verify the asynchronous generator yields token deltas and ends with a valid state frame."""
    state = WorkflowState(
        workflow_id="wf_test_stream",
        current_stage=StageEnum.INTAKE,
        status=StatusEnum.IDLE,
        title="Test Initiative",
    )
    req = WorkflowRequest(
        action="generate_brd",
        stage=StageEnum.INTAKE,
        user_prompt="Automate audit testing",
    )

    events = []
    try:
        async for event_item in process_workflow_action(state, req, "user_unit_test"):
            events.append(event_item)
    except RuntimeError as re:
        if "503" in str(re) or "high demand" in str(re):
            pytest.skip("External Gemini API currently returning 503 high demand spike")
        raise

    # Must contain token events and a terminal state event
    event_types = [e["event"] for e in events]
    assert "token" in event_types
    assert "state" in event_types

    # Final event must have updated stage
    final_state_data = [e["data"] for e in events if e["event"] == "state"][-1]
    assert final_state_data["current_stage"] == StageEnum.BRD
    assert final_state_data["brd"] is not None


def test_extract_attachment_context():
    """Verify text and media extraction from attachments."""
    import base64
    from core.llm.engine import extract_attachment_context
    from core.llm.models import Attachment

    sample_text = "Project: HealthTrack Patient Portal\nRequirements: Telehealth video consultation."
    b64_sample = base64.b64encode(sample_text.encode("utf-8")).decode("ascii")

    att_text = Attachment(
        id="att_1",
        name="health_reqs.txt",
        mime_type="text/plain",
        s3_key="",
        base64_data=b64_sample,
    )
    att_pdf = Attachment(
        id="att_2",
        name="architecture.pdf",
        mime_type="application/pdf",
        s3_key="",
        base64_data=base64.b64encode(b"%PDF-1.4 minimal").decode("ascii"),
    )

    doc_text, media = extract_attachment_context([att_text, att_pdf])
    assert "HealthTrack Patient Portal" in doc_text
    assert "Telehealth video consultation" in doc_text
    assert len(media) == 1
    assert media[0]["mime_type"] == "application/pdf"
    assert media[0]["name"] == "architecture.pdf"


@pytest.mark.asyncio
async def test_process_workflow_with_uploaded_file_attachment():
    """Verify BRD generation follows uploaded document content rather than made-up generic templates."""
    import base64
    from core.llm.models import Attachment

    doc_content = (
        "Project: VetClinic Companion Animal EHR\n"
        "Requirements:\n"
        "1. Pet patient vaccination schedule tracking\n"
        "2. Rabies certificate automated digital generation\n"
        "3. Microchip lookup integration"
    )
    b64_doc = base64.b64encode(doc_content.encode("utf-8")).decode("ascii")

    state = WorkflowState(
        workflow_id="wf_test_vet",
        current_stage=StageEnum.INTAKE,
        status=StatusEnum.IDLE,
        title="Session K9B2M",
    )
    req = WorkflowRequest(
        action="generate_brd",
        stage=StageEnum.INTAKE,
        user_prompt="",  # User provided no prompt, only attached the document
        attachments=[
            Attachment(
                id="att_vet",
                name="vet_clinic_specs.txt",
                mime_type="text/plain",
                s3_key="",
                base64_data=b64_doc,
                text_content=doc_content,
            )
        ],
    )

    events = []
    try:
        async for event_item in process_workflow_action(state, req, "user_unit_test"):
            events.append(event_item)
    except RuntimeError as re:
        if "503" in str(re) or "high demand" in str(re):
            pytest.skip("External Gemini API currently returning 503 high demand spike")
        raise

    final_state_data = [e["data"] for e in events if e["event"] == "state"][-1]
    brd = final_state_data.get("brd")
    assert brd is not None
    # Must follow the VetClinic domain from the file, NOT made-up serverless analytics
    assert "Modernization initiative transitioning legacy analytics" not in brd.get("executive_summary", "")
    assert any(term in (brd.get("title", "") + brd.get("executive_summary", "")).lower() for term in ["vet", "animal", "pet", "clinic"])


@pytest.mark.asyncio
async def test_no_mock_on_llm_failure(monkeypatch):
    """Verify that when LLM providers fail, the system NEVER falls back to mock content, but raises a technical error."""
    import core.config
    import core.llm.engine
    from core.config import Settings

    bad_settings = Settings(
        app_name="intelliq",
        stage="dev",
        aws_region="ap-south-1",
        dynamodb_table="test-table",
        s3_bucket="test-bucket",
        cognito_user_pool_id="",
        cognito_client_id="",
        allowed_email_domains=["*"],
        gemini_api_key="invalid_gemini_key_xyz",
        gemini_model="test-gemini-model",
        groq_api_key="invalid_groq_key_xyz",
        groq_model="test-groq-model",
        openai_api_key="",
        rate_limit_max=60,
        rate_limit_window_seconds=300,
    )
    monkeypatch.setattr(core.config, "get_settings", lambda: bad_settings)
    monkeypatch.setattr(core.llm.engine, "get_settings", lambda: bad_settings)

    state = WorkflowState(
        workflow_id="wf_test_fail",
        current_stage=StageEnum.INTAKE,
        status=StatusEnum.IDLE,
        title="Session FAIL",
    )
    req = WorkflowRequest(
        action="generate_brd",
        stage=StageEnum.INTAKE,
        user_prompt="Build inventory tracker",
    )

    events = []
    with pytest.raises(RuntimeError) as exc_info:
        async for event_item in process_workflow_action(state, req, "user_unit_test"):
            events.append(event_item)

    assert "All LLM providers in cascade failed" in str(exc_info.value)
    error_states = [e["data"] for e in events if e.get("event") == "state"]
    assert len(error_states) >= 1
    last_state = error_states[-1]
    assert last_state["status"] == StatusEnum.ERROR
    assert last_state["brd"] is None


def test_build_test_cases_prompt_with_target_story():
    """Verify targeted prompt construction for a specific user story with custom prompt."""
    stories = [
        {
            "id": "US-101",
            "epic_id": "EPIC-01",
            "title": "Token Refresh Protocol",
            "user_role": "Authenticated Client",
            "capability": "refresh my expired JWT",
            "benefit": "remain signed in seamlessly",
            "story_points": 5,
            "priority": "MUST_HAVE",
            "acceptance_criteria_gherkin": [
                "Given valid refresh token, When POST /auth/refresh, Then return 200 with new JWT"
            ],
        },
        {
            "id": "US-102",
            "epic_id": "EPIC-01",
            "title": "Revoke Token",
            "user_role": "User",
            "capability": "log out",
            "benefit": "invalidate session",
        },
    ]

    # Without target story
    general_prompt = _build_test_cases_prompt(stories, "General testing instructions")
    assert "US-101" in general_prompt
    assert "General testing instructions" in general_prompt

    # With target story US-101 and custom prompt
    targeted_prompt = _build_test_cases_prompt(
        stories,
        feedback="Focus heavily on expired and tampered refresh tokens",
        target_story_id="US-101",
    )
    assert "specifically for User Story US-101" in targeted_prompt
    assert "Token Refresh Protocol" in targeted_prompt
    assert "Authenticated Client" in targeted_prompt
    assert "refresh my expired JWT" in targeted_prompt
    assert "Focus heavily on expired and tampered refresh tokens" in targeted_prompt
    assert "POSITIVE" in targeted_prompt
    assert "NEGATIVE" in targeted_prompt
    assert "BOUNDARY" in targeted_prompt
    assert "SECURITY" in targeted_prompt


@pytest.mark.asyncio
async def test_per_story_test_case_generation_state_merging(monkeypatch):
    """Verify generating test cases for a specific story merges with existing test cases and remains in STORIES stage."""
    import core.llm.engine
    from core.llm.models import Story, TestCase, TestCaseStep

    state = WorkflowState(
        workflow_id="wf_test_per_story",
        current_stage=StageEnum.STORIES,
        status=StatusEnum.IDLE,
        title="Session STORY_TEST",
        stories=[
            Story(
                id="US-101",
                epic_id="EPIC-01",
                title="Token Refresh",
                user_role="Client",
                capability="refresh token",
                benefit="stay signed in",
            ),
            Story(
                id="US-102",
                epic_id="EPIC-01",
                title="Sign Out",
                user_role="Client",
                capability="sign out",
                benefit="invalidate token",
            ),
        ],
        test_cases=[
            TestCase(
                id="TC-201",
                story_id="US-102",
                epic_id="EPIC-01",
                title="Verify Sign Out Invalidation",
                steps=[TestCaseStep(step_number=1, action="Sign out", expected_result="Token revoked")],
            )
        ],
    )

    # Mock execute_cascade_stream to return test cases for US-101
    mock_llm_json = """{
      "test_cases": [
        {
          "id": "TC-TEMP-1",
          "story_id": "US-101",
          "epic_id": "EPIC-01",
          "title": "Verify Valid Refresh Flow",
          "test_type": "POSITIVE",
          "priority": "HIGH",
          "preconditions": ["Valid refresh token exists"],
          "steps": [
            {"step_number": 1, "action": "POST /auth/refresh", "expected_result": "HTTP 200 returned"}
          ],
          "postconditions": "New access token issued",
          "test_data": "refresh_token=valid.jwt"
        }
      ],
      "ai_insights": {
        "confidence_score": 0.98,
        "rationale_bullets": ["Generated test for US-101"],
        "ambiguities_flagged": [],
        "suggested_actions": []
      }
    }"""

    async def mock_stream(*args, **kwargs):
        yield mock_llm_json

    monkeypatch.setattr(core.llm.engine, "execute_cascade_stream", mock_stream)

    req = WorkflowRequest(
        action="generate_test_cases",
        stage=StageEnum.STORIES,
        target_id="US-101",
        feedback="Test invalid signature",
    )

    events = []
    async for event_item in process_workflow_action(state, req, "test_user"):
        events.append(event_item)

    final_state = [e["data"] for e in events if e.get("event") == "state"][-1]
    # Current stage must remain STORIES for iterative generation
    assert final_state["current_stage"] == StageEnum.STORIES

    # Both existing TC-201 (for US-102) and new test case for US-101 must exist!
    test_cases = final_state["test_cases"]
    assert len(test_cases) == 2
    story_ids = {tc["story_id"] for tc in test_cases}
    assert "US-101" in story_ids
    assert "US-102" in story_ids


def test_test_case_resilient_parsing_dict_test_data():
    """Verify TestCase model cleanly coerces dict/list test_data and flexible step formats without validation errors."""
    from core.llm.models import TestCase, TestTypeEnum, PriorityEnum

    # Dict test_data (the exact error reported by user)
    tc1 = TestCase(
        id="TC-001",
        story_id="US-101",
        epic_id="EPIC-01",
        title="Verify Stripe payment",
        test_type="POSITIVE",
        priority="HIGH",
        preconditions="Valid test card available",
        steps=[{"step": "Enter card details", "expected": "Token created"}],
        postconditions=["Stripe customer created", "Charge succeeded"],
        test_data={"card_number": "4242424242424242", "exp_year": "2025", "cvc": "123"},
    )
    assert isinstance(tc1.test_data, str)
    assert "4242424242424242" in tc1.test_data
    assert tc1.preconditions == ["Valid test card available"]
    assert "Stripe customer created" in tc1.postconditions
    assert len(tc1.steps) == 1
    assert tc1.steps[0].action == "Enter card details"
    assert tc1.steps[0].expected_result == "Token created"
    assert tc1.test_type == TestTypeEnum.POSITIVE
    assert tc1.priority == PriorityEnum.HIGH



