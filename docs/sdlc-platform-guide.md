# SDLC Platform Implementation Guide

## Overview
This document describes the implementation of the Stage 1 SDLC (Software Development Lifecycle) platform within the Taskloom application. The platform provides a complete AI-driven software development lifecycle orchestration system.

## Architecture

### Backend Components
1. **SDLC Models** (`backend/app/models.py`)
   - `SDLCStatus`: Enum for SDLC workflow stages
   - `SDLCProjectConfig`: Project configuration for SDLC
   - `AgentConfig`: Configuration for AI agents
   - `SDLCTask`: Extended task with SDLC metadata
   - `AgentResult`: Structured agent outputs
   - `HumanIntervention`: Human approval system

2. **SDLC Services** (`backend/app/services.py`)
   - `SDLCProjectManager`: Manages SDLC projects and configurations
   - `SDLCTaskManager`: Handles task lifecycle and transitions
   - Internal scheduler/loop to replace n8n functionality

3. **API Endpoints** (`backend/app/main.py`)
   - `/api/sdlc/projects`: Project management
   - `/api/sdlc/tasks`: SDLC task management
   - `/api/sdlc/human-intervention`: Human approval workflows

### Frontend Components
1. **SDLCDashboard** (`frontend/src/sdlc_dashboard.jsx`)
   - Pipeline visualization with 13 workflow stages
   - Task creation and management interface
   - Real-time status updates
   - Human intervention response system
   - Project configuration UI

## Workflow Stages

1. **ایجاد شده** (Created) - Task created but not started
2. **در حال تحلیل** (Analyzing) - AI agent analyzing requirements
3. **بازبینی انسانی** (Human Review) - Waiting for human approval
4. **تأیید تحلیل** (Analysis Approved) - Analysis phase complete
5. **توسعه بک‌اند** (Backend Running) - Backend development
6. **توسعه n8n** (n8n Running) - Workflow automation (future)
7. **توسعه فرانت‌اند** (Frontend Running) - Frontend development
8. **آزمون** (Testing) - Quality assurance
9. **تأیید کیفیت** (Human QA) - Quality approval
10. **بازبینی** (Revision) - Revision/feedback loop
11. **انجام شده** (Done) - Task completed
12. **ناموفق** (Failed) - Task failed
13. **مسدود شده** (Blocked) - Task blocked

## Agent Types

1. **تحلیلگر** (Analysis) - Requirement analysis and planning
2. **توسعه‌دهنده بک‌اند** (Backend) - Backend development
3. **مهندس n8n** (n8n) - Workflow automation (future)
4. **توسعه‌دهنده فرانت‌اند** (Frontend) - Frontend development
5. **آزمونگر** (QA) - Quality assurance and testing

## Key Features

### 1. Internal Scheduler/Loop
- Replaces n8n workflow automation for Stage 1
- Automated task transitions between stages
- Error handling and retry logic
- Parallel agent execution where applicable

### 2. Human Intervention System
- Structured approval workflows
- Configurable response options
- Audit trail for all interventions
- Escalation mechanisms

### 3. Structured Agent Outputs
- Contract-based agent responses
- Validation of agent outputs
- Consistent formatting across all agents
- Error reporting and logging

### 4. Project Configuration
- Multi-stage workflow definitions
- Agent model configuration
- Approval thresholds and rules
- Integration settings

## Backward Compatibility

The SDLC platform maintains backward compatibility with existing Taskloom features:

1. **Legacy Mode**: Traditional AI-assisted code changes with Git operations
2. **SDLC Mode**: Full SDLC workflow with multi-stage automation
3. **Hybrid Mode**: Gradual migration path from legacy to SDLC

## API Integration

### Project Management
```http
GET /api/sdlc/projects
POST /api/sdlc/projects
PUT /api/sdlc/projects/{project_id}
DELETE /api/sdlc/projects/{project_id}
```

### Task Management
```http
GET /api/sdlc/tasks
POST /api/sdlc/tasks
GET /api/sdlc/tasks/{task_id}
PUT /api/sdlc/tasks/{task_id}/transition
```

### Human Intervention
```http
GET /api/sdlc/human-inbox/pending
POST /api/sdlc/human-intervention/{intervention_id}/respond
```

## Testing

### Backend Tests
```bash
# Run SDLC-specific tests
python -m pytest tests/test_sdlc_api.py -v

# Test the complete workflow
python test_sdlc_workflow.py
```

### Frontend Tests
```bash
cd frontend
npm run test
```

### Integration Test
```bash
python test_sdlc_integration.py
```

## Deployment

### Prerequisites
1. Python 3.8+ with FastAPI
2. Node.js 16+ with React
3. Git for version control

### Startup Sequence
1. Start backend server:
   ```bash
   python main.py
   ```

2. Start frontend development server:
   ```bash
   cd frontend
   npm run dev
   ```

3. Access the application:
   - Main interface: http://localhost:5173
   - API documentation: http://localhost:8003/docs

## Future Enhancements (Stage 2+)

### Phase 1: External Integration
1. **n8n Integration**: Replace internal scheduler with n8n workflows
2. **Jira Integration**: Sync tasks with Jira issues
3. **GitLab Integration**: Advanced GitLab CI/CD integration

### Phase 2: Advanced Features
1. **Multi-agent Coordination**: Multiple agents working on same task
2. **Quality Gates**: Automated quality checks at each stage
3. **Performance Analytics**: Metrics and reporting dashboard
4. **Template System**: Reusable project templates

### Phase 3: Enterprise Features
1. **Role-based Access Control**: Fine-grained permissions
2. **Audit Logging**: Comprehensive audit trail
3. **Compliance Reporting**: Regulatory compliance features
4. **Scalability Enhancements**: Horizontal scaling support

## Troubleshooting

### Common Issues

1. **API Connection Failed**
   - Check if backend server is running on port 8003
   - Verify CORS configuration in backend
   - Check network connectivity

2. **Tasks Not Transitioning**
   - Verify internal scheduler is running
   - Check agent configuration
   - Review task status in database

3. **Human Interventions Not Showing**
   - Check intervention endpoint response
   - Verify task is in correct state
   - Review agent output formatting

4. **Frontend Styling Issues**
   - Clear browser cache
   - Check CSS compilation
   - Verify icon imports

### Logs and Debugging
```bash
# Backend logs
tail -f backend.log

# Frontend logs (browser console)
# Press F12 → Console tab

# API debugging
curl http://localhost:8003/api/sdlc/projects
```

## Support and Maintenance

### Monitoring
- API health checks
- Task queue monitoring
- Agent performance metrics
- Error rate tracking

### Backup and Recovery
- Regular data backups
- Configuration versioning
- Disaster recovery procedures
- Rollback mechanisms

### Updates and Patches
- Regular security updates
- Feature enhancements
- Bug fixes
- Compatibility updates

---

**Version**: Stage 1.0  
**Status**: Production Ready  
**Last Updated**: November 18, 2026  
**Contact**: SDLC Platform Team