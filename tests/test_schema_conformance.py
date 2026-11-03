"""Unit tests verifying Pydantic v2 schema conformance, JIRA Excel workbook generation, and payload offloading."""
import json
from pathlib import Path
import pytest
from core.db import MAX_DDB_ITEM_SIZE_BYTES, get_workflow_state, save_workflow_state
from core.llm.models import (
    AiInsights,
    Brd,
    Epic,
    FunctionalRequirement,
    PriorityEnum,
    StageEnum,
    Story,
    StoryPriorityEnum,
    TestCase as SchemaTestCase,
    TestCaseStep as SchemaTestCaseStep,
    TestTypeEnum as SchemaTestTypeEnum,
    WorkflowState,
)
from lambdas.api_handler.handler import handle_export_jira_excel


def test_pydantic_model_hierarchy():
    """Verify complete domain model instantiation and serialization."""
    brd = Brd(
        title="Enterprise Serverless Analytics",
        executive_summary="Executive overview text",
        business_objectives=["Scale-to-zero", "Free tier maximized"],
        functional_requirements=[
            FunctionalRequirement(
                id="FR-01",
                title="Presigned Upload",
                description="Upload transcripts directly to S3",
                priority=PriorityEnum.CRITICAL,
            )
        ],
    )

    epic = Epic(
        id="EPIC-01",
        title="Ingestion Engine",
        summary="S3 direct pipeline",
        business_value="Prevents Lambda limits",
        priority=PriorityEnum.CRITICAL,
        acceptance_criteria=["Presign URL returns in <100ms"],
    )

    story = Story(
        id="US-101",
        epic_id="EPIC-01",
        title="Presign API",
        user_role="Developer",
        capability="request presigned URL",
        benefit="upload directly to S3",
        priority=StoryPriorityEnum.MUST_HAVE,
        story_points=3,
        acceptance_criteria_gherkin=["Given valid token, When requested, Then return signed URL"],
    )

    test_case = SchemaTestCase(
        id="TC-001",
        story_id="US-101",
        epic_id="EPIC-01",
        title="Verify presigned URL allows direct PUT",
        test_type=SchemaTestTypeEnum.POSITIVE,
        priority=PriorityEnum.HIGH,
        steps=[
            SchemaTestCaseStep(step_number=1, action="Execute PUT with binary body", expected_result="HTTP 200")
        ],
    )

    state = WorkflowState(
        workflow_id="wf_conformance_01",
        current_stage=StageEnum.TEST_CASES,
        title=brd.title,
        brd=brd,
        epics=[epic],
        stories=[story],
        test_cases=[test_case],
        ai_insights=AiInsights(confidence_score=0.99, rationale_bullets=["Verified"]),
    )

    dumped = state.model_dump()
    assert dumped["workflow_id"] == "wf_conformance_01"
    assert len(dumped["epics"]) == 1
    assert len(dumped["stories"]) == 1
    assert len(dumped["test_cases"]) == 1


def test_jira_excel_export_generation():
    """Verify that handle_export_jira_excel generates a compliant multi-sheet workbook."""
    user_id = "test_user_export"
    workflow_id = "wf_export_test"

    # Pre-populate state
    state = {
        "workflow_id": workflow_id,
        "title": "Cloud Analytics Modernization",
        "current_stage": "test_cases",
        "status": "completed",
        "brd": {
            "title": "Cloud Analytics Modernization",
            "executive_summary": "Executive summary for testing",
            "business_objectives": ["Obj 1", "Obj 2"],
            "in_scope": ["Scope A"],
            "out_of_scope": ["Scope B"],
        },
        "epics": [
            {
                "id": "EPIC-01",
                "title": "Data Pipeline",
                "summary": "Ingestion",
                "business_value": "Accelerate analytics",
                "priority": "HIGH",
                "acceptance_criteria": ["Criteria 1"],
            }
        ],
        "stories": [
            {
                "id": "STORY-101",
                "epic_id": "EPIC-01",
                "title": "Upload Transcript",
                "user_role": "Analyst",
                "capability": "upload transcript",
                "benefit": "generate BRD",
                "story_points": 3,
                "priority": "MUST_HAVE",
                "acceptance_criteria_gherkin": ["Given file, When uploaded, Then parse"],
            }
        ],
        "test_cases": [
            {
                "id": "TC-001",
                "story_id": "STORY-101",
                "epic_id": "EPIC-01",
                "title": "Verify file upload under 50MB",
                "test_type": "POSITIVE",
                "priority": "CRITICAL",
                "preconditions": ["User signed in"],
                "steps": [{"step_number": 1, "action": "PUT file", "expected_result": "Success"}],
                "postconditions": "S3 object exists",
            }
        ],
    }

    save_workflow_state(user_id, workflow_id, state)

    resp = handle_export_jira_excel(user_id, workflow_id)
    assert resp["statusCode"] == 200

    resp_data = json.loads(resp["body"])
    assert resp_data["epics_exported"] == 1
    assert resp_data["stories_exported"] == 1
    assert resp_data["test_cases_exported"] == 1
    assert resp_data["filename"].endswith(".xlsx")
    assert len(resp_data["content_base64"]) > 0


def test_large_payload_offload_logic():
    """Verify ADR-09 safeguard for payloads > 350 KB."""
    user_id = "test_user_offload"
    workflow_id = "wf_large_test"

    # Create a payload exceeding 350 KB
    large_text = "Deloitte Enterprise Quality Assurance Requirements Traceability Specification. " * 6000
    state = {
        "workflow_id": workflow_id,
        "title": "Large Payload Initiative",
        "current_stage": "brd",
        "status": "processing",
        "brd": {"title": "Large BRD", "executive_summary": large_text},
    }

    raw_bytes_len = len(json.dumps(state).encode("utf-8"))
    assert raw_bytes_len > MAX_DDB_ITEM_SIZE_BYTES

    # Save state
    save_workflow_state(user_id, workflow_id, state)

    # Retrieve state
    retrieved = get_workflow_state(user_id, workflow_id)
    assert retrieved is not None
    assert retrieved["workflow_id"] == workflow_id
    assert retrieved["title"] == "Large Payload Initiative"
