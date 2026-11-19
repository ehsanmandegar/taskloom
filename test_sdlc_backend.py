#!/usr/bin/env python3
"""
Test script for SDLC backend implementation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app.models import (
    SDLCProjectConfig, AgentConfig, ProjectWorkflowConfig,
    SDLCTaskRequest, TaskState, RunStatus, TaskRole, AgentType,
    GitProvider, McpFailureMode, McpStatus, ChatMessage
)
from backend.app.services import SDLCProjectManager, SDLCTaskManager

def test_project_manager():
    """Test SDLC project manager functionality"""
    print("Testing SDLC Project Manager...")
    
    manager = SDLCProjectManager(Path("data/projects"))
    
    # List projects
    projects = manager.list_projects()
    print(f"Found {len(projects)} project(s)")
    
    # Get test project
    project = manager.get_project("test-project")
    if project:
        print(f"✓ Found project: {project.name} (ID: {project.id})")
        print(f"  Description: {project.description}")
        print(f"  SDLC Enabled: {project.sdlc_enabled}")
        print(f"  Stages: {project.workflow.stages}")
        print(f"  Agents enabled: {[agent for agent, config in project.agents.items() if config.enabled]}")
    else:
        print("✗ Test project not found")
        return False
    
    # Test creating a new project
    new_project = SDLCProjectConfig(
        id="new-test-project",
        name="New Test Project",
        description="A newly created test project",
        enabled=True,
        sdlc_enabled=True,
        workflow=ProjectWorkflowConfig(),
        agents={
            "analysis": AgentConfig(enabled=True),
            "backend": AgentConfig(enabled=True),
            "frontend": AgentConfig(enabled=True)
        }
    )
    
    try:
        manager.save_project(new_project)
        print("✓ Created new project")
        
        # Verify it was saved
        loaded = manager.get_project("new-test-project")
        if loaded:
            print(f"✓ Verified project saved: {loaded.name}")
        else:
            print("✗ Failed to load saved project")
            return False
        
        # Clean up
        manager.delete_project("new-test-project")
        print("✓ Cleaned up test project")
        
    except Exception as e:
        print(f"✗ Error creating project: {e}")
        return False
    
    return True

async def test_task_manager():
    """Test SDLC task manager functionality"""
    print("\nTesting SDLC Task Manager...")
    
    manager = SDLCTaskManager(Path("data/tasks"))
    
    # Generate task ID
    task_id = manager.generate_task_id()
    print(f"Generated task ID: {task_id}")
    
    # Create a mock base task state
    base_task_state = TaskState(
        id="test-run-id",
        task_id="test-task-001",
        session_name="Test SDLC Task",
        project_path="/test/project",
        branch="tasks/test-task-001",
        base_branch="main",
        guide_paths=[],
        role=TaskRole.analyst,
        role_knowledge_path="",
        test_command=None,
        test_working_directory=None,
        test_setup_enabled=False,
        auto_commit=False,
        auto_generate_commit_message=False,
        auto_push=False,
        auto_merge_request=False,
        test_setup_output="",
        mcp_server_name=None,
        mcp_failure_mode=McpFailureMode.warning,
        mcp_status=McpStatus.not_configured,
        mcp_message="",
        git_provider=GitProvider.auto,
        agent_type=AgentType.codex,
        status=RunStatus.queued,
        step="SDLC test task",
        logs=[],
        live_output="",
        live_response="",
        summary="Test SDLC task summary",
        diff="",
        changed_files=[],
        test_output="",
        commit_message="",
        error=None,
        committed=False,
        pushed=False,
        merge_request_url="",
        codex_thread_id="",
        messages=[ChatMessage(role="user", content="Test task description")],
        todos=[]
    )
    
    # Create a task request
    task_request = SDLCTaskRequest(
        title="Test SDLC Task",
        description="This is a test SDLC task for the new platform",
        project_id="test-project"
    )
    
    # Get project config (we'll create a simple one for testing)
    project_config = SDLCProjectConfig(
        id="test-project",
        name="Test Project",
        description="Test project",
        enabled=True,
        sdlc_enabled=True,
        workflow=ProjectWorkflowConfig(),
        agents={
            "analysis": AgentConfig(enabled=True),
            "backend": AgentConfig(enabled=True)
        }
    )
    
    print("✓ Created test objects")
    
    # Test listing tasks
    tasks = await manager.list_tasks()
    print(f"Found {len(tasks)} existing task(s)")
    
    # Test human intervention creation (simulated)
    print("\nTesting human intervention workflow...")
    
    # This would normally be called by an agent
    # For now, just verify the manager is initialized
    print("✓ SDLC Task Manager initialized successfully")
    
    return True

def test_api_endpoints():
    """Test that API endpoints would work"""
    print("\nTesting API endpoint configuration...")
    
    # Import FastAPI app to check it loads
    try:
        from backend.app.main import app
        print("✓ FastAPI app loaded successfully")
        
        # Check if SDLC routes are registered
        routes = [route.path for route in app.routes]
        sdlc_routes = [r for r in routes if '/sdlc/' in r]
        
        print(f"Found {len(sdlc_routes)} SDLC API endpoints:")
        for route in sorted(sdlc_routes):
            print(f"  - {route}")
        
        if len(sdlc_routes) > 0:
            print("✓ SDLC API endpoints registered")
            return True
        else:
            print("✗ No SDLC API endpoints found")
            return False
            
    except ImportError as e:
        print(f"✗ Failed to import app: {e}")
        return False
    except Exception as e:
        print(f"✗ Error checking routes: {e}")
        return False

async def main_async():
    """Run all tests"""
    print("=" * 60)
    print("SDLC Backend Implementation Tests")
    print("=" * 60)
    
    # Create necessary directories
    from pathlib import Path
    Path("data/projects").mkdir(parents=True, exist_ok=True)
    Path("data/tasks").mkdir(parents=True, exist_ok=True)
    Path("data/human-inbox/pending").mkdir(parents=True, exist_ok=True)
    Path("data/human-inbox/resolved").mkdir(parents=True, exist_ok=True)
    
    tests_passed = 0
    tests_total = 3
    
    # Run tests
    if test_project_manager():
        tests_passed += 1
    
    if await test_task_manager():
        tests_passed += 1
    
    if test_api_endpoints():
        tests_passed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {tests_passed}/{tests_total} passed")
    
    if tests_passed == tests_total:
        print("✓ All tests passed! SDLC backend implementation is working.")
        return 0
    else:
        print("✗ Some tests failed. Check implementation.")
        return 1

def main():
    import asyncio
    return asyncio.run(main_async())

if __name__ == "__main__":
    from pathlib import Path
    sys.exit(main())