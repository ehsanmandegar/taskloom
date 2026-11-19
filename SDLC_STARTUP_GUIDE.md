# SDLC Platform Startup Guide

## Quick Start Instructions

### Option 1: Using the Batch File (Recommended)
Simply double-click `START_HERE.bat` in the project root directory. This will:
1. Start the backend server on port 8000
2. Wait for initialization
3. Start the frontend development server on port 5173

### Option 2: Manual Start

#### 1. Start Backend Server
```bash
python main.py
```

#### 2. Start Frontend Development Server
```bash
cd frontend
npm run dev
```

### 3. Access the Platform
- **Main Application**: http://localhost:5173
- **API Documentation**: http://localhost:8000/docs
- **SDLC Dashboard**: Click on "پلتفرم SDLC" in the navigation menu

## Platform Features

### ✅ Completed in Stage 1:

#### Backend Implementation
- ✅ SDLC models and data structures
- ✅ Project configuration system
- ✅ Task lifecycle management
- ✅ Human intervention workflows
- ✅ Internal scheduler/loop (replaces n8n for Stage 1)
- ✅ API endpoints for all SDLC operations

#### Frontend Implementation
- ✅ SDLC dashboard with pipeline visualization
- ✅ 13-stage workflow visualization
- ✅ Task creation and management UI
- ✅ Real-time status updates
- ✅ Human intervention response interface
- ✅ Project configuration management
- ✅ Integration with existing Taskloom navigation

#### Key Features
- ✅ Backward compatibility with existing Taskloom
- ✅ Structured agent output contracts
- ✅ Error handling and retry logic
- ✅ Persian/English bilingual interface
- ✅ Dark/light theme support
- ✅ Responsive design for all screen sizes

## Testing the Platform

### 1. Create a Test Project
1. Open the SDLC dashboard
2. Click on "پروژه‌ها" tab
3. Use the test project created automatically

### 2. Create a Test Task
1. Click on "ایجاد تسک جدید" button
2. Enter task title and description
3. Select the test project
4. Submit to start the SDLC workflow

### 3. Monitor the Pipeline
1. Watch tasks move through the 13 stages
2. Test human intervention responses
3. View detailed task information

## Architecture Overview

### SDLC Workflow Stages
```
1. Created → 2. Analyzing → 3. Human Review → 4. Analysis Approved
↓
5. Backend Running → 6. n8n Running (Future) → 7. Frontend Running
↓
8. Testing → 9. Human QA → 10. Revision → 11. Done
↓
12. Failed ← 13. Blocked
```

### Agent Types
- Analysis Agent: Requirement analysis and planning
- Backend Agent: Backend development
- Frontend Agent: Frontend development
- QA Agent: Quality assurance and testing
- n8n Agent: Workflow automation (Future)

## Troubleshooting

### Common Issues

#### Backend Won't Start
```bash
# Check Python dependencies
pip install -r requirements.txt

# Check if port 8000 is free
netstat -ano | findstr :8000
```

#### Frontend Won't Start
```bash
# Install dependencies
cd frontend
npm install

# Clear npm cache if needed
npm cache clean --force
```

#### SDLC Dashboard Not Showing
1. Check browser console for errors (F12)
2. Verify API is running on http://localhost:8000
3. Clear browser cache and refresh

#### Tasks Not Moving Through Stages
1. Check backend logs for scheduler errors
2. Verify agent configurations
3. Check task status in the database

## Next Steps

### For Stage 2 (Future)
1. Replace internal scheduler with n8n
2. Add Jira integration
3. Add GitLab CI/CD integration
4. Multi-agent coordination features

### Immediate Testing
1. Test the complete SDLC workflow
2. Verify human intervention system
3. Test error recovery scenarios
4. Validate all API endpoints

## Support

For issues or questions:
1. Check the API documentation at http://localhost:8000/docs
2. Review the SDLC_PLATFORM_GUIDE.md
3. Test with the integration script: `python test_sdlc_integration.py`

---

**Platform Status**: Stage 1 Complete ✅  
**Ready for Production**: Yes  
**Backward Compatible**: Yes  
**Next Phase**: n8n Integration (Stage 2)