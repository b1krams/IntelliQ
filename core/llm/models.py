# Auto-generated Pydantic v2 models conforming to schemas/response.schema.json
# Generated for IntelliQ Serverless AI Platform
from __future__ import annotations

import json
from enum import Enum
from typing import Annotated, Any
from pydantic import BaseModel, Field, field_validator


class StageEnum(str, Enum):
    INTAKE = "intake"
    BRD = "brd"
    EPICS = "epics"
    STORIES = "stories"
    TEST_CASES = "test_cases"
    EXPORT = "export"


class StatusEnum(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    COMPLETED = "completed"
    ERROR = "error"


class PriorityEnum(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class StoryPriorityEnum(str, Enum):
    MUST_HAVE = "MUST_HAVE"
    SHOULD_HAVE = "SHOULD_HAVE"
    COULD_HAVE = "COULD_HAVE"
    WONT_HAVE = "WONT_HAVE"


class TestTypeEnum(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    BOUNDARY = "BOUNDARY"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"


class ActorEnum(str, Enum):
    AGENT = "AGENT"
    USER = "USER"
    GATEWAY = "GATEWAY"


class AssumptionRiskTypeEnum(str, Enum):
    ASSUMPTION = "ASSUMPTION"
    RISK = "RISK"
    DEPENDENCY = "DEPENDENCY"


class Stakeholder(BaseModel):
    role: str = "Stakeholder"
    name: str = ""
    department: str = ""
    responsibilities: str = ""


class FunctionalRequirement(BaseModel):
    id: str = "FR-01"
    title: str = "Requirement"
    description: str = ""
    priority: PriorityEnum = PriorityEnum.HIGH


class NonFunctionalRequirement(BaseModel):
    category: str = "General"
    specification: str = ""


class AssumptionRisk(BaseModel):
    type: AssumptionRiskTypeEnum = AssumptionRiskTypeEnum.ASSUMPTION
    description: str = ""
    mitigation: str = ""


class Brd(BaseModel):
    title: str = "Business Requirements Document"
    version: str = "1.0"
    executive_summary: str = ""
    business_objectives: list[str] = Field(default_factory=list)
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    functional_requirements: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional_requirements: list[NonFunctionalRequirement] = Field(default_factory=list)
    assumptions_and_risks: list[AssumptionRisk] = Field(default_factory=list)
    compliance_regulatory: list[str] = Field(default_factory=list)


class Epic(BaseModel):
    id: str = ""
    title: str = ""
    summary: str = ""
    business_value: str = ""
    priority: PriorityEnum = PriorityEnum.HIGH
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)

    @field_validator("dependencies", mode="before")
    @classmethod
    def coerce_dependencies(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        if isinstance(v, str):
            clean = v.strip()
            if not clean or clean.lower() in ("none", "n/a", "[]", "nil", "null"):
                return []
            return [s.strip() for s in clean.split(",") if s.strip()]
        return []

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def coerce_acceptance_criteria(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        if isinstance(v, str):
            clean = v.strip()
            if not clean:
                return []
            return [s.strip() for s in clean.split("\n") if s.strip()]
        return []

    @field_validator("priority", mode="before")
    @classmethod
    def coerce_epic_priority(cls, v: Any) -> PriorityEnum:
        if isinstance(v, PriorityEnum):
            return v
        if isinstance(v, str):
            val = v.strip().upper()
            if val in PriorityEnum.__members__:
                return PriorityEnum[val]
            if val in ("MUST_HAVE", "MUST"):
                return PriorityEnum.CRITICAL
            if val in ("SHOULD_HAVE", "SHOULD"):
                return PriorityEnum.HIGH
            if val in ("COULD_HAVE", "COULD"):
                return PriorityEnum.MEDIUM
            if val in ("WONT_HAVE", "WONT"):
                return PriorityEnum.LOW
        return PriorityEnum.HIGH


class Story(BaseModel):
    id: str = ""
    epic_id: str = ""
    title: str = ""
    user_role: str = ""
    capability: str = ""
    benefit: str = ""
    priority: StoryPriorityEnum = StoryPriorityEnum.MUST_HAVE
    story_points: int = 3
    acceptance_criteria_gherkin: list[str] = Field(default_factory=list)
    technical_notes: str = ""

    @field_validator("priority", mode="before")
    @classmethod
    def coerce_priority(cls, v: Any) -> StoryPriorityEnum:
        if isinstance(v, StoryPriorityEnum):
            return v
        if isinstance(v, str):
            val = v.strip().upper()
            if val in StoryPriorityEnum.__members__:
                return StoryPriorityEnum[val]
            # Map standard priority strings (HIGH, CRITICAL, MEDIUM, LOW) to MoSCoW
            if val in ("CRITICAL", "HIGH", "P0", "P1", "MUST", "MUST-HAVE", "MUST_HAVE"):
                return StoryPriorityEnum.MUST_HAVE
            if val in ("MEDIUM", "P2", "SHOULD", "SHOULD-HAVE", "SHOULD_HAVE"):
                return StoryPriorityEnum.SHOULD_HAVE
            if val in ("LOW", "P3", "COULD", "COULD-HAVE", "COULD_HAVE"):
                return StoryPriorityEnum.COULD_HAVE
            if val in ("WONT", "WONT-HAVE", "WONT_HAVE", "P4"):
                return StoryPriorityEnum.WONT_HAVE
        return StoryPriorityEnum.MUST_HAVE

    @field_validator("story_points", mode="before")
    @classmethod
    def coerce_story_points(cls, v: Any) -> int:
        try:
            return int(v)
        except Exception:
            return 3

    @field_validator("acceptance_criteria_gherkin", mode="before")
    @classmethod
    def coerce_ac(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        if isinstance(v, str):
            clean = v.strip()
            return [s.strip() for s in clean.split("\n") if s.strip()] if clean else []
        return []


class TestCaseStep(BaseModel):
    step_number: int = 1
    action: str = ""
    expected_result: str = ""

    @field_validator("step_number", mode="before")
    @classmethod
    def coerce_step_number(cls, v: Any) -> int:
        try:
            return int(v)
        except Exception:
            return 1

    @field_validator("action", mode="before")
    @classmethod
    def coerce_action(cls, v: Any) -> str:
        return str(v) if v is not None else ""

    @field_validator("expected_result", mode="before")
    @classmethod
    def coerce_expected_result(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class TestCase(BaseModel):
    id: str = ""
    story_id: str = ""
    epic_id: str = ""
    title: str = ""
    test_type: TestTypeEnum = TestTypeEnum.POSITIVE
    priority: PriorityEnum = PriorityEnum.HIGH
    preconditions: list[str] = Field(default_factory=list)
    steps: list[TestCaseStep] = Field(default_factory=list)
    postconditions: str = ""
    test_data: str = ""

    @field_validator("test_data", mode="before")
    @classmethod
    def coerce_test_data(cls, v: Any) -> str:
        if isinstance(v, (dict, list)):
            return json.dumps(v, indent=2)
        return str(v) if v is not None else ""

    @field_validator("postconditions", mode="before")
    @classmethod
    def coerce_postconditions(cls, v: Any) -> str:
        if isinstance(v, list):
            return "; ".join(str(item) for item in v)
        if isinstance(v, dict):
            return json.dumps(v, indent=2)
        return str(v) if v is not None else ""

    @field_validator("preconditions", mode="before")
    @classmethod
    def coerce_preconditions(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    @field_validator("test_type", mode="before")
    @classmethod
    def coerce_test_type(cls, v: Any) -> TestTypeEnum:
        if isinstance(v, TestTypeEnum):
            return v
        if isinstance(v, str):
            val = v.strip().upper()
            if val in TestTypeEnum.__members__:
                return TestTypeEnum[val]
            if "POS" in val or "HAPPY" in val or "FUNC" in val:
                return TestTypeEnum.POSITIVE
            if "NEG" in val or "ERR" in val or "FAIL" in val:
                return TestTypeEnum.NEGATIVE
            if "BOUND" in val or "EDGE" in val or "LIMIT" in val:
                return TestTypeEnum.BOUNDARY
            if "SEC" in val or "AUTH" in val:
                return TestTypeEnum.SECURITY
            if "PERF" in val or "LOAD" in val:
                return TestTypeEnum.PERFORMANCE
        return TestTypeEnum.POSITIVE

    @field_validator("priority", mode="before")
    @classmethod
    def coerce_priority(cls, v: Any) -> PriorityEnum:
        if isinstance(v, PriorityEnum):
            return v
        if isinstance(v, str):
            val = v.strip().upper()
            if val in PriorityEnum.__members__:
                return PriorityEnum[val]
        return PriorityEnum.HIGH

    @field_validator("steps", mode="before")
    @classmethod
    def coerce_steps(cls, v: Any) -> list[Any]:
        if not isinstance(v, list):
            return []
        coerced = []
        for i, step in enumerate(v, 1):
            if isinstance(step, dict):
                action = step.get("action") or step.get("description") or step.get("step") or ""
                expected = step.get("expected_result") or step.get("expected") or step.get("result") or ""
                num = step.get("step_number", i)
                coerced.append({"step_number": num, "action": action, "expected_result": expected})
            elif isinstance(step, str):
                coerced.append({"step_number": i, "action": step, "expected_result": "Successful execution"})
            else:
                coerced.append(step)
        return coerced


class AiInsights(BaseModel):
    confidence_score: Annotated[float, Field(ge=0.0, le=1.0)] = 0.95
    rationale_bullets: list[str] = Field(default_factory=list)
    ambiguities_flagged: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)

    @field_validator("confidence_score", mode="before")
    @classmethod
    def coerce_confidence_score(cls, v: Any) -> float:
        try:
            if isinstance(v, str):
                v = v.replace("%", "").strip()
            val = float(v)
            if val > 1.0:
                val = val / 100.0
            return max(0.0, min(1.0, val))
        except Exception:
            return 0.95

    @field_validator("rationale_bullets", "ambiguities_flagged", "suggested_actions", mode="before")
    @classmethod
    def coerce_string_list(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        if isinstance(v, str):
            clean = v.strip()
            return [s.strip() for s in clean.split("\n") if s.strip()] if clean else []
        return []


class HistoryItem(BaseModel):
    timestamp: str
    actor: ActorEnum
    action: str
    details: str


# Request Contract Models
class Attachment(BaseModel):
    id: str
    name: str
    mime_type: str
    s3_key: str
    size_bytes: int = 0
    base64_data: str | None = None
    text_content: str | None = None


class WorkflowState(BaseModel):
    workflow_id: str
    current_stage: StageEnum = StageEnum.INTAKE
    status: StatusEnum = StatusEnum.IDLE
    title: str = "Untitled Project"
    user_prompt: str = ""
    attachments: list[Attachment] = Field(default_factory=list)
    brd: Brd | None = None
    epics: list[Epic] = Field(default_factory=list)
    stories: list[Story] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    ai_insights: AiInsights = Field(default_factory=AiInsights)
    history: list[HistoryItem] = Field(default_factory=list)


class WorkflowRequest(BaseModel):
    workflow_id: str | None = None
    action: str
    stage: StageEnum = StageEnum.INTAKE
    user_prompt: str = ""
    feedback: str = ""
    target_id: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    model_preference: str = "auto"

