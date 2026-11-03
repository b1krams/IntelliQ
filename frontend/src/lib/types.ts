/**
 * Auto-generated TypeScript definitions conforming to schemas/response.schema.json
 * For IntelliQ Serverless AI Platform
 */

export type Stage = 'intake' | 'brd' | 'epics' | 'stories' | 'test_cases' | 'export';
export type Status = 'idle' | 'processing' | 'review_required' | 'approved' | 'completed' | 'error';
export type Priority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type StoryPriority = 'MUST_HAVE' | 'SHOULD_HAVE' | 'COULD_HAVE' | 'WONT_HAVE';
export type TestType = 'POSITIVE' | 'NEGATIVE' | 'BOUNDARY' | 'SECURITY' | 'PERFORMANCE';
export type Actor = 'AGENT' | 'USER' | 'GATEWAY';
export type AssumptionRiskType = 'ASSUMPTION' | 'RISK' | 'DEPENDENCY';

export interface Stakeholder {
  role: string;
  name?: string;
  department?: string;
  responsibilities: string;
}

export interface FunctionalRequirement {
  id: string;
  title: string;
  description: string;
  priority: Priority;
}

export interface NonFunctionalRequirement {
  category: string;
  specification: string;
}

export interface AssumptionRisk {
  type: AssumptionRiskType;
  description: string;
  mitigation: string;
}

export interface Brd {
  title: string;
  version?: string;
  executive_summary: string;
  business_objectives: string[];
  stakeholders: Stakeholder[];
  in_scope: string[];
  out_of_scope: string[];
  functional_requirements: FunctionalRequirement[];
  non_functional_requirements: NonFunctionalRequirement[];
  assumptions_and_risks: AssumptionRisk[];
  compliance_regulatory: string[];
}

export interface Epic {
  id: string;
  title: string;
  summary: string;
  business_value: string;
  priority: Priority;
  dependencies: string[];
  acceptance_criteria: string[];
}

export interface Story {
  id: string;
  epic_id: string;
  title: string;
  user_role: string;
  capability: string;
  benefit: string;
  priority: StoryPriority;
  story_points: number;
  acceptance_criteria_gherkin: string[];
  technical_notes?: string;
}

export interface TestCaseStep {
  step_number: number;
  action: string;
  expected_result: string;
}

export interface TestCase {
  id: string;
  story_id: string;
  epic_id: string;
  title: string;
  test_type: TestType;
  priority: Priority;
  preconditions: string[];
  steps: TestCaseStep[];
  postconditions?: string;
  test_data?: string;
}

export interface AiInsights {
  confidence_score: number;
  rationale_bullets: string[];
  ambiguities_flagged: string[];
  suggested_actions: string[];
}

export interface HistoryItem {
  timestamp: string;
  actor: Actor;
  action: string;
  details: string;
}

export interface WorkflowState {
  workflow_id: string;
  current_stage: Stage;
  status: Status;
  title: string;
  user_prompt?: string;
  attachments?: Attachment[];
  brd?: Brd;
  epics: Epic[];
  stories: Story[];
  test_cases: TestCase[];
  ai_insights: AiInsights;
  history: HistoryItem[];
}

export interface Attachment {
  id: string;
  name: string;
  mime_type: string;
  s3_key: string;
  size_bytes?: number;
  base64_data?: string;
  text_content?: string;
}

export interface WorkflowRequest {
  workflow_id?: string;
  action:
    | 'init_workflow'
    | 'generate_brd'
    | 'refine_brd'
    | 'generate_epics'
    | 'refine_epics'
    | 'generate_stories'
    | 'refine_stories'
    | 'generate_test_cases'
    | 'refine_test_cases'
    | 'approve_stage';
  stage?: Stage;
  user_prompt?: string;
  feedback?: string;
  target_id?: string;
  attachments?: Attachment[];
  model_preference?: string;
}

export interface UserProfile {
  user_id: string;
  email: string;
  name: string;
  created_at: string;
}

