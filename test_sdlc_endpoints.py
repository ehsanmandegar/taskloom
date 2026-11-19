#!/usr/bin/env python3
"""Test script for SDLC API endpoints"""

import json

# Create a sample project for testing
sample_project = {
    'id': 'test-project-edit',
    'name': 'Test Project for Editing',
    'description': 'This is a test project for PUT/DELETE operations',
    'enabled': True,
    'sdlc_enabled': True,
    'workflow': {
        'stages': ['analysis', 'backend', 'frontend', 'testing', 'deployment'],
        'triggers': ['manual', 'automated']
    },
    'agents': {
        'analysis': {'enabled': True, 'model': 'gpt-4'},
        'backend': {'enabled': True, 'model': 'gpt-4'},
        'frontend': {'enabled': True, 'model': 'gpt-4'},
        'qa': {'enabled': True, 'model': 'gpt-4'}
    }
}

print('=== SDLC API Endpoints Test ===')
print('Available endpoints:')
print('1. GET    /api/sdlc/projects')
print('2. POST   /api/sdlc/projects  (create new)')
print('3. PUT    /api/sdlc/projects/{id}  (update)')
print('4. DELETE /api/sdlc/projects/{id}  (delete)')
print()
print('To test these endpoints:')
print('1. Run the backend: python -m backend.app.main')
print('2. Use curl or Postman to test:')
print()
print('Sample commands:')
print()
print('Create project (POST):')
print(f'curl -X POST http://localhost:8000/api/sdlc/projects \\')
print(f'  -H "Content-Type: application/json" \\')
print(f'  -d \'{json.dumps(sample_project)}\'')
print()
print('Update project (PUT):')
updated_project = sample_project.copy()
updated_project['name'] = 'Updated Name'
print(f'curl -X PUT http://localhost:8000/api/sdlc/projects/{sample_project["id"]} \\')
print(f'  -H "Content-Type: application/json" \\')
print(f'  -d \'{json.dumps(updated_project)}\'')
print()
print('Delete project (DELETE):')
print(f'curl -X DELETE http://localhost:8000/api/sdlc/projects/{sample_project["id"]}')
print()
print('Frontend changes summary:')
print('- Added Edit/View/Create Task/Delete buttons to project cards')
print('- Added PUT endpoint support in backend')
print('- Added danger button styling for delete')
print('- Form validation and proper state management')
print('- Modal overlay for better UX')