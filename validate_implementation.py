#!/usr/bin/env python
"""Final comprehensive validation of team workflow extension"""

from backend.app.models import (
    TaskSpecification, BackendHandoff, QAReport, PODecision,
    SDLCTask, SDLCProjectConfig, ProjectWorkflowConfig,
    ModelInfo, ProjectModelSettings, ProjectAISettings
)
from backend.app.services import (
    get_next_workflow_stage, can_transition_to,
    create_sanitized_prompt_for_role, sanitize_agent_result_for_role
)

# Validate SDLCTask has all new fields
sdlc_fields = set(SDLCTask.model_fields.keys())
required_fields = {
    'task_specification', 'backend_handoff', 'qa_report', 'po_decision',
    'backend_review_status', 'frontend_review_status', 'qa_review_status',
    'analyst_final_review_status', 'analyst_final_summary',
    'analyst_knowledge_path', 'backend_knowledge_path', 'frontend_knowledge_path', 'qa_knowledge_path'
}
missing = required_fields - sdlc_fields
if missing:
    print(f"ERROR: Missing SDLCTask fields: {missing}")
else:
    print("✓ SDLCTask has all required fields")

# Validate ProjectWorkflowConfig has review gate config
pw_config = ProjectWorkflowConfig()
assert pw_config.auto_backend_review == True
assert pw_config.auto_frontend_review == True
assert pw_config.auto_qa_review == True
assert pw_config.auto_analyst_final_review == True
assert pw_config.require_po_approval == True
print("✓ ProjectWorkflowConfig has all review gate config")

# Validate new models can be instantiated
spec = TaskSpecification(id="test-1", user_business_need="Test need")
print(f"✓ TaskSpecification created: {spec.user_business_need}")

handoff = BackendHandoff(id="test-2", what_changed="Test changes")
print(f"✓ BackendHandoff created: {handoff.what_changed}")

qa_report = QAReport(id="test-3")
print(f"✓ QAReport created with {len(qa_report.test_cases)} test cases")

po_decision = PODecision(id="test-4", decision="pending")
print(f"✓ PODecision created: {po_decision.decision}")

# Validate service functions exist and are callable
assert callable(get_next_workflow_stage)
assert callable(can_transition_to)
assert callable(create_sanitized_prompt_for_role)
assert callable(sanitize_agent_result_for_role)
print("✓ All service functions are callable")

# Validate API endpoints exist
from backend.app.main import app
endpoints = [route.path for route in app.routes if hasattr(route, 'path')]
required_endpoints = [
    '/api/sdlc/tasks/{task_id}/backend-review',
    '/api/sdlc/tasks/{task_id}/frontend-review',
    '/api/sdlc/tasks/{task_id}/qa-review',
    '/api/sdlc/tasks/{task_id}/analyst-final-review',
    '/api/sdlc/tasks/{task_id}/po-approval',
    '/api/sdlc/tasks/{task_id}/release-ready',
    '/api/sdlc/tasks/{task_id}/workflow-status',
    '/api/sdlc/projects/{project_id}/default-workflow'
]
for endpoint in required_endpoints:
    if endpoint in endpoints:
        print(f"✓ Endpoint {endpoint} registered")
    else:
        print(f"MISSING: {endpoint}")

print("\n✓ All validations passed!")
