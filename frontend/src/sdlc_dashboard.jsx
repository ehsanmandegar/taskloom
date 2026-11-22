import React, { useState, useEffect, useRef } from 'react';
import { 
  BarChart3, ClipboardList, RefreshCw, Users, Play, Pause, CheckCircle, XCircle, 
  Clock, AlertCircle, FileCode, GitBranch, GitPullRequest, MessageCircle, Eye,
  ChevronRight, ChevronDown, Filter, Gauge, Search, Download, Upload, Settings, Plus, X, Square, Send
} from 'lucide-react';
import { canSendBack } from './sdlc_automation.js';
import ProjectBuilder from './project_builder.jsx';
import { UiTag } from './ui_tag';
import { ModalShell, confirmDialog } from './ui.jsx';
import { AutonomyFields, MetricsPanel, RiskBadge, Timeline } from './sdlc_automation.jsx';
import { withAutonomyDefaults, autonomySummary } from './sdlc_automation.js';
import { GitPanel } from './release_management.jsx';
import { storedAdminHeaders } from './releases.js';

const API = import.meta.env.VITE_API_URL || '';

// SDLC stage configuration
const sdlcStages = [
  { id: 'created', label: 'ایجاد شده', color: 'bg-gray-200', icon: FileCode },
  { id: 'analyzing', label: 'در حال تحلیل', color: 'bg-blue-100', icon: MessageCircle },
  { id: 'human_review', label: 'بازبینی انسانی', color: 'bg-yellow-100', icon: Eye },
  { id: 'analysis_approved', label: 'تأیید تحلیل', color: 'bg-green-100', icon: CheckCircle },
  { id: 'backend_running', label: 'توسعه بک‌اند', color: 'bg-purple-100', icon: FileCode },
  { id: 'n8n_running', label: 'توسعه n8n', color: 'bg-indigo-100', icon: GitBranch },
  { id: 'frontend_running', label: 'توسعه فرانت‌اند', color: 'bg-pink-100', icon: FileCode },
  { id: 'testing', label: 'آزمون', color: 'bg-orange-100', icon: AlertCircle },
  { id: 'human_qa', label: 'تأیید کیفیت', color: 'bg-yellow-100', icon: Eye },
  { id: 'revision', label: 'بازبینی', color: 'bg-red-100', icon: RefreshCw },
  { id: 'pending_approval', label: 'منتظر تأیید نهایی', color: 'bg-yellow-200', icon: Eye },
  { id: 'done', label: 'انجام شده', color: 'bg-green-200', icon: CheckCircle },
  { id: 'failed', label: 'ناموفق', color: 'bg-red-200', icon: XCircle },
  { id: 'blocked', label: 'مسدود شده', color: 'bg-gray-300', icon: Pause }
];

// Parse a JSON response and turn HTTP errors into exceptions carrying the server's message
async function readJsonOrThrow(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.message || `HTTP ${response.status}`);
  return data;
}

const DEFAULT_REPOSITORY = { mode: 'none', url: '', name: '', local_path: '', default_branch: 'main', private: true, github_token: '', token_saved: false, clear_token: false };

const responseOptionLabels = { approve: 'تأیید', stop: 'توقف تسک', resume: 'ادامه (اجرای دوبارهٔ مرحله)' };

// What a free-text answer does for each kind of inbox item (see SDLCTaskManager.submit_human_response)
const interventionHints = {
  analysis_approval: 'با «تأیید» توسعه شروع می‌شود؛ اگر بازخورد بنویسید، تحلیل با بازخورد شما دوباره اجرا می‌شود.',
  agent_question: 'پاسخ شما به عامل داده می‌شود و همین مرحله دوباره اجرا می‌شود.',
  revision_limit: 'سقف دفعات بازبینی پر شده است؛ راهنمایی شما به عامل داده می‌شود و مرحله دوباره اجرا می‌شود.',
  interrupted: 'سرور وسط اجرای این مرحله بسته شد. «ادامه» مرحله را دوباره اجرا می‌کند؛ فایل‌هایی که عامل قبلاً تغییر داده بود در پوشه باقی مانده‌اند.',
};

const agentTypes = {
  analysis: { label: 'تحلیلگر', color: 'bg-blue-500' },
  backend: { label: 'توسعه‌دهنده بک‌اند', color: 'bg-purple-500' },
  n8n: { label: 'مهندس n8n', color: 'bg-indigo-500' },
  frontend: { label: 'توسعه‌دهنده فرانت‌اند', color: 'bg-pink-500' },
  qa: { label: 'آزمونگر', color: 'bg-orange-500' }
};

export default function SDLCDashboard() {
  const [tasks, setTasks] = useState([]);
  const [projects, setProjects] = useState([]);
  const [pendingInterventions, setPendingInterventions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('pipeline');
  // Per-stage visible task (by task id) in the pipeline view; index is derived so polling/filtering cannot make it jump.
  const [stageCursor, setStageCursor] = useState({});
  // "Report a problem" box in the task dialog (M3-A): the human's opinion that goes back to the analyst.
  const [problemText, setProblemText] = useState(null); // null = closed
  const [problemBusy, setProblemBusy] = useState(false);
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [newProject, setNewProject] = useState({
    id: '',
    name: '',
    description: '',
    enabled: true,
    sdlc_enabled: true,
    workflow: {
      stages: ['analysis', 'backend', 'n8n', 'frontend', 'qa'],
      sequential: true,
      allow_parallel: false,
      max_revision_attempts: 3,
      require_analysis_approval: false,
      require_final_human_approval: false
    },
    agents: {
      analysis: { 
        enabled: true, 
        knowledge_path: '',
        project_path: '',
        system_prompt: '',
        test_instructions: {},
        timeout_seconds: 300,
        max_retries: 2,
        github_config: {
          repository_url: '',
          github_token: '',
          branch: 'main',
          auto_commit: false,
          auto_push: false,
          auto_pr: false
        }
      },
      backend: { 
        enabled: true, 
        knowledge_path: '',
        project_path: '',
        system_prompt: '',
        test_instructions: {},
        timeout_seconds: 300,
        max_retries: 2,
        github_config: {
          repository_url: '',
          github_token: '',
          branch: 'main',
          auto_commit: false,
          auto_push: false,
          auto_pr: false
        }
      },
      n8n: { 
        enabled: true, 
        knowledge_path: '',
        project_path: '',
        system_prompt: '',
        test_instructions: {},
        timeout_seconds: 300,
        max_retries: 2,
        github_config: {
          repository_url: '',
          github_token: '',
          branch: 'main',
          auto_commit: false,
          auto_push: false,
          auto_pr: false
        }
      },
      frontend: { 
        enabled: true, 
        knowledge_path: '',
        project_path: '',
        system_prompt: '',
        test_instructions: {},
        timeout_seconds: 300,
        max_retries: 2,
        github_config: {
          repository_url: '',
          github_token: '',
          branch: 'main',
          auto_commit: false,
          auto_push: false,
          auto_pr: false
        }
      },
      qa: { 
        enabled: true, 
        knowledge_path: '',
        project_path: '',
        system_prompt: '',
        test_instructions: {},
        timeout_seconds: 300,
        max_retries: 2,
        github_config: {
          repository_url: '',
          github_token: '',
          branch: 'main',
          auto_commit: false,
          auto_push: false,
          auto_pr: false
        }
      }
    }
  });
  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    project_id: '',
    priority: 'medium',
    tags: []
  });
  const [isEditingProject, setIsEditingProject] = useState(false);
  const [editingProjectId, setEditingProjectId] = useState('');
  const [projectFormStep, setProjectFormStep] = useState(1);
  const [activeAgentTab, setActiveAgentTab] = useState('analysis');
  const [selectedTask, setSelectedTask] = useState(null);
  // The polling interval is created once, so it reads the open task through a ref.
  const selectedTaskIdRef = useRef(null);
  useEffect(() => { selectedTaskIdRef.current = selectedTask?.base_task?.task_id ?? null; }, [selectedTask]);
  const [githubCredentials, setGithubCredentials] = useState({
    backend: { url: '', token: '', showToken: false },
    n8n: { url: '', token: '', showToken: false },
    frontend: { url: '', token: '', showToken: false }
  });
  const [agentGithubDialogs, setAgentGithubDialogs] = useState({
    backend: false,
    n8n: false,
    frontend: false
  });
  
  // Load SDLC data
  useEffect(() => {
    loadSDLCData();
    const interval = setInterval(loadSDLCData, 5000);
    return () => clearInterval(interval);
  }, []);
  
  async function loadSDLCData() {
    try {
      setLoading(true);
      
      // Load tasks with filters
      let tasksUrl = `${API}/api/sdlc/tasks`;
      const params = [];
      if (selectedStatus) params.push(`status=${selectedStatus}`);
      if (selectedProject) params.push(`project=${selectedProject}`);
      if (params.length > 0) {
        tasksUrl += '?' + params.join('&');
      }
      
      const tasksResponse = await fetch(tasksUrl);
      if (!tasksResponse.ok) throw new Error('خطا در بارگذاری تسک‌ها');
      const tasksData = await tasksResponse.json();
      
      // Load projects
      const projectsResponse = await fetch(`${API}/api/sdlc/projects`);
      if (!projectsResponse.ok) throw new Error('خطا در بارگذاری پروژه‌ها');
      const projectsData = await projectsResponse.json();
      
      // Load pending interventions
      const interventionsResponse = await fetch(`${API}/api/sdlc/human-inbox/pending`);
      if (interventionsResponse.ok) {
        const interventionsData = await interventionsResponse.json();
        setPendingInterventions(interventionsData);
      }
      
      setTasks(tasksData);
      setProjects(projectsData);
      setError('');

      // Keep the open task detail (status, results, live agent output) current
      const openTaskId = selectedTaskIdRef.current;
      if (openTaskId) {
        const detailResponse = await fetch(`${API}/api/sdlc/tasks/${openTaskId}`);
        if (detailResponse.ok) {
          const fresh = await detailResponse.json();
          setSelectedTask(current => (current && current.base_task.task_id === openTaskId ? fresh : current));
        }
      }
    } catch (err) {
      setError(err.message);
      console.error('Error loading SDLC data:', err);
    } finally {
      setLoading(false);
    }
  }
  
  // Filter tasks based on search query
  // Ensure tasks is an array
  const safeTasks = Array.isArray(tasks) ? tasks : [];
  
  const filteredTasks = safeTasks.filter(task => {
    if (!searchQuery) return true;
    
    const query = searchQuery.toLowerCase();
    return (
      task.base_task?.task_id?.toLowerCase().includes(query) ||
      task.base_task?.session_name?.toLowerCase().includes(query) ||
      task.base_task?.summary?.toLowerCase().includes(query) ||
      task.project_config_id?.toLowerCase().includes(query)
    );
  });
  
  // Calculate statistics
  const stats = {
    total: safeTasks.length,
    active: safeTasks.filter(t => ['analyzing', 'backend_running', 'n8n_running', 'frontend_running', 'testing'].includes(t.sdlc_status)).length,
    pendingHuman: safeTasks.filter(t => ['human_review', 'human_qa', 'pending_approval'].includes(t.sdlc_status)).length,
    completed: safeTasks.filter(t => t.sdlc_status === 'done').length,
    failed: safeTasks.filter(t => t.sdlc_status === 'failed').length,
    revisions: safeTasks.reduce((sum, task) => sum + (task.revision_count || 0), 0)
  };
  
  // Group tasks by status for pipeline view
  const tasksByStatus = sdlcStages.reduce((acc, stage) => {
    acc[stage.id] = filteredTasks.filter(task => task.sdlc_status === stage.id);
    return acc;
  }, {});
  
  // Format date for display
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('fa-IR', {
      dateStyle: 'short',
      timeStyle: 'short'
    }).format(date);
  };
  
  // Get stage info
  const getStageInfo = (stageId) => {
    return sdlcStages.find(stage => stage.id === stageId) || sdlcStages[0];
  };
  
  // Get agent info
  const getAgentInfo = (agentType) => {
    return agentTypes[agentType] || { label: 'نامشخص', color: 'bg-gray-500' };
  };
  
  // Handle task transition
  const handleTransition = async (taskId, stage) => {
    try {
      const response = await fetch(`${API}/api/sdlc/tasks/${taskId}/transition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, stage, force: false })
      });
      
      if (!response.ok) throw new Error('خطا در انتقال مرحله');
      
      await loadSDLCData();
    } catch (err) {
      setError(err.message);
    }
  };
  
  // Final human sign-off for a task that finished every stage
  const handleApprove = async (taskId) => {
    try {
      // The server merges the task branch into develop first; a conflict or Git failure comes back as 409 and the
      // task stays "waiting for final approval".
      const response = await fetch(`${API}/api/sdlc/tasks/${taskId}/approve`, { method: 'POST', headers: storedAdminHeaders() });
      const updated = await readJsonOrThrow(response);
      setSelectedTask(current => (current && current.base_task.task_id === taskId ? updated : current));
      await loadSDLCData();
    } catch (err) {
      setError(err.message);
    }
  };

  // Re-run the stage a failed task stopped in ("restore" the task to work).
  const handleRetryStage = async (task) => {
    const taskId = task.base_task.task_id;
    try {
      const response = await fetch(`${API}/api/sdlc/tasks/${taskId}/transition`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, stage: task.current_stage, force: true }),
      });
      const updated = await readJsonOrThrow(response);
      setSelectedTask(current => (current && current.base_task.task_id === taskId ? updated : current));
      await loadSDLCData();
    } catch (err) {
      setError(`خطا در اجرای مجدد مرحله: ${err.message}`);
    }
  };

  // The human wrote that the result has a problem: the analyst runs again with that opinion, then a human re-approves.
  const handleSendBack = async (task) => {
    const taskId = task.base_task.task_id;
    setProblemBusy(true);
    try {
      const response = await fetch(`${API}/api/sdlc/tasks/${taskId}/send-back`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ feedback: problemText }),
      });
      const updated = await readJsonOrThrow(response);
      setSelectedTask(current => (current && current.base_task.task_id === taskId ? updated : current));
      setProblemText(null);
      await loadSDLCData();
    } catch (err) {
      setError(`خطا در ارجاع به تحلیل: ${err.message}`);
    } finally {
      setProblemBusy(false);
    }
  };

  // Delete one task (refused by the server while one of its stages is running).
  const handleDeleteTask = async (task) => {
    const taskId = task.base_task.task_id;
    if (!await confirmDialog(`تسک «${task.title || taskId}» برای همیشه حذف شود؟
شاخهٔ Git و ریپوها دست‌نخورده می‌مانند.`)) return;
    try {
      await readJsonOrThrow(await fetch(`${API}/api/sdlc/tasks/${taskId}`, { method: 'DELETE' }));
      setSelectedTask(null);
      await loadSDLCData();
    } catch (err) {
      setError(`خطا در حذف تسک: ${err.message}`);
    }
  };

  // Handle human intervention response
  const handleInterventionResponse = async (interventionId, response) => {
    try {
      const res = await fetch(`${API}/api/sdlc/human-intervention/${interventionId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intervention_id: interventionId, response })
      });
      
      if (!res.ok) throw new Error('خطا در ارسال پاسخ');
      
      await loadSDLCData();
    } catch (err) {
      setError(err.message);
    }
  };
  
  // Create new SDLC task
  const handleCreateTask = async () => {
    if (!newTask.title.trim() || !newTask.project_id.trim() || !newTask.description.trim()) {
      setError('عنوان، شرح تسک و پروژه الزامی هستند');
      return;
    }

    try {
      const response = await fetch(`${API}/api/sdlc/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newTask.title.trim(),
          description: newTask.description.trim(),
          project_id: newTask.project_id,
          priority: newTask.priority,
          tags: newTask.tags
        })
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'خطا در ایجاد تسک');
      }

      await loadSDLCData();
      setShowTaskForm(false);
      setNewTask({ title: '', description: '', project_id: '', priority: 'medium', tags: [] });
      setError('');
      // Switch to pipeline tab so user sees the new task
      setActiveTab('pipeline');
    } catch (err) {
      setError(err.message);
    }
  };
  
  // Create or update SDLC project
  const handleSaveProject = async () => {
    try {
      const url = isEditingProject 
        ? `${API}/api/sdlc/projects/${editingProjectId}`
        : `${API}/api/sdlc/projects`;
      
      const method = isEditingProject ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProject)
      });
      
      if (!response.ok) throw new Error(`خطا در ${isEditingProject ? 'ویرایش' : 'ایجاد'} پروژه`);
      
      await loadSDLCData();
      setShowProjectForm(false);
      setIsEditingProject(false);
      setEditingProjectId('');
      setNewProject({
        id: '',
        name: '',
        description: '',
        enabled: true,
        sdlc_enabled: true,
        workflow: {
          stages: ['analysis', 'backend', 'n8n', 'frontend', 'qa'],
          sequential: true,
          allow_parallel: false,
          max_revision_attempts: 3,
          require_analysis_approval: false,
          require_final_human_approval: false
        },
        agents: {
          analysis: { 
            enabled: true, 
            knowledge_path: '',
            project_path: '',
            system_prompt: '',
            test_instructions: {},
            timeout_seconds: 300,
            max_retries: 2
          },
          backend: { 
            enabled: true, 
            knowledge_path: '',
            project_path: '',
            system_prompt: '',
            test_instructions: {},
            timeout_seconds: 300,
            max_retries: 2
          },
          n8n: { 
            enabled: true, 
            knowledge_path: '',
            project_path: '',
            system_prompt: '',
            test_instructions: {},
            timeout_seconds: 300,
            max_retries: 2
          },
          frontend: { 
            enabled: true, 
            knowledge_path: '',
            project_path: '',
            system_prompt: '',
            test_instructions: {},
            timeout_seconds: 300,
            max_retries: 2
          },
          qa: { 
            enabled: true, 
            knowledge_path: '',
            project_path: '',
            system_prompt: '',
            test_instructions: {},
            timeout_seconds: 300,
            max_retries: 2
          }
        }
      });
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  // Handle edit project
  const handleEditProject = (project) => {
    // Ensure all required agent fields exist
    const processedAgents = {};
    const agentTypes = ['analysis', 'backend', 'n8n', 'frontend', 'qa'];
    
    agentTypes.forEach(agentType => {
      if (project.agents && project.agents[agentType]) {
        const agent = project.agents[agentType];
        processedAgents[agentType] = {
          ...agent,  // keep runner, cli timeout, github_config, ... (the PUT replaces the whole config)
          enabled: agent.enabled ?? true,
          knowledge_path: agent.knowledge_path ?? '',
          project_path: agent.project_path ?? '',
          system_prompt: agent.system_prompt ?? '',
          test_instructions: agent.test_instructions ?? {},
          timeout_seconds: agent.timeout_seconds ?? 300,
          max_retries: agent.max_retries ?? 2,
          repository: { ...DEFAULT_REPOSITORY, ...(agent.repository || {}), github_token: '', clear_token: false },
        };
      } else {
        processedAgents[agentType] = {
          enabled: true,
          knowledge_path: '',
          project_path: '',
          system_prompt: '',
          test_instructions: {},
          timeout_seconds: 300,
          max_retries: 2
        };
      }
    });
    
    setNewProject({
      id: project.id,
      name: project.name,
      description: project.description,
      enabled: project.enabled ?? true,
      sdlc_enabled: project.sdlc_enabled ?? true,
      workflow: project.workflow || {
        stages: ['analysis', 'backend', 'n8n', 'frontend', 'qa'],
        sequential: true,
        allow_parallel: false,
        max_revision_attempts: 3,
        require_analysis_approval: false,
        require_final_human_approval: false
      },
      agents: processedAgents
    });
    setIsEditingProject(true);
    setEditingProjectId(project.id);
    setShowProjectForm(true);
  };

  // Handle view project details
  const handleViewProject = (project) => {
    alert(`[A1 ProjectInfo] جزئیات پروژه:\n\nنام: ${project.name}\nشناسه: ${project.id}\nتوضیحات: ${project.description}\nوضعیت: ${project.enabled ? 'فعال' : 'غیرفعال'}\nوضعیت SDLC: ${project.sdlc_enabled ? 'فعال' : 'غیرفعال'}`);
  };

  // Load full task details with agent results
  const handleViewTask = async (task) => {
    try {
      const response = await fetch(`${API}/api/sdlc/tasks/${task.base_task.task_id}`);
      if (!response.ok) throw new Error('خطا در بارگذاری جزئیات تسک');
      const fullTask = await response.json();
      setProblemText(null);
      setSelectedTask(fullTask);
    } catch (err) {
      setError(err.message);
    }
  };

  // Handle create task from project
  const handleCreateTaskFromProject = (project) => {
    setNewTask({
      title: '',
      description: '',
      project_id: project.id,
      priority: 'medium',
      tags: []
    });
    setShowTaskForm(true);
  };

  // Handle delete project
  const handleDeleteProject = async (projectId) => {
    let taskCount = 0;
    try {
      taskCount = (await readJsonOrThrow(await fetch(`${API}/api/sdlc/projects/${projectId}/tasks/count`))).count;
    } catch (err) { /* the confirmation still works without the count */ }
    const confirmDelete = confirm(
      `آیا مطمئن هستید که می‌خواهید پروژه "${projectId}" را حذف کنید؟\n` +
      (taskCount ? `${taskCount} تسک این پروژه و درخواست‌های inbox آن‌ها هم حذف می‌شوند.\n` : '') +
      'ریپوهای git و برنچ‌های تسک‌ها دست نمی‌خورند.\nاین عملیات غیرقابل بازگشت است.'
    );
    if (!confirmDelete) return;

    try {
      const result = await readJsonOrThrow(await fetch(`${API}/api/sdlc/projects/${projectId}`, { method: 'DELETE' }));
      await loadSDLCData();
      setError('');
      alert(`[A2 ProjectDeleted] پروژه "${projectId}" و ${result.deleted_tasks.length} تسک آن حذف شدند`);
    } catch (err) {
      setError(`خطا در حذف پروژه: ${err.message}`);
    }
  };
  
  return (
    <div className="sdlc-dashboard" dir="rtl">
      {/* Header */}
      <header className="sdlc-header">
        <div className="sdlc-header-left">
          <h1>پلتفرم SDLC</h1>
          <p>مدیریت چرخه کامل توسعه نرم‌افزار</p>
        </div>
        <div className="sdlc-header-right">
          <button 
            className="sdlc-btn sdlc-btn-primary"
            onClick={() => setShowTaskForm(true)}
            disabled={loading}
          >
            <Plus size={16} />
            ایجاد تسک جدید
          </button>
          <button 
            className="sdlc-btn sdlc-btn-secondary"
            onClick={loadSDLCData}
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            {loading ? 'در حال بارگذاری...' : 'به‌روزرسانی'}
          </button>
        </div>
      </header>
      
      {/* Error display */}
      {error && (
        <div className="sdlc-error" role="alert">
          <AlertCircle size={16} />
          {error}
        </div>
      )}
      
      {/* Task creation form modal */}
      {showTaskForm && (
        <ModalShell label="ایجاد تسک جدید" onClose={() => { setShowTaskForm(false); setError(''); setNewTask({ title:'', description:'', project_id:'', priority:'medium', tags:[] }); }}>
          <div className="sdlc-project-form" style={{width: 'min(560px, 100%)'}}>
            <div className="sdlc-form-header">
              <div>
                <h3>ایجاد تسک جدید <UiTag id="M2" name="NewTask"/></h3>
                <small style={{fontSize:'11px', color:'#899087'}}>تسک بلافاصله وارد فرایند تحلیل می‌شود</small>
              </div>
              <button type="button" className="sdlc-form-close" onClick={() => {
                setShowTaskForm(false);
                setError('');
                setNewTask({ title:'', description:'', project_id:'', priority:'medium', tags:[] });
              }}>
                <X size={20} />
              </button>
            </div>

            <div className="sdlc-form-body">
              {error && (
                <div className="sdlc-error" role="alert" style={{margin: '0 0 4px'}}>
                  <AlertCircle size={14} />
                  {error}
                </div>
              )}

              <div className="sdlc-form-group">
                <label htmlFor="new-task-title">عنوان تسک *</label>
                <input
                  id="new-task-title"
                  type="text"
                  value={newTask.title}
                  onChange={(e) => setNewTask({...newTask, title: e.target.value})}
                  placeholder="عنوان کوتاه و واضح تسک"
                  autoFocus
                />
              </div>

              <div className="sdlc-form-group">
                <label htmlFor="new-task-project">پروژه *</label>
                <select
                  id="new-task-project"
                  value={newTask.project_id}
                  onChange={(e) => setNewTask({...newTask, project_id: e.target.value})}
                >
                  <option value="">انتخاب پروژه...</option>
                  {projects.filter(p => p.enabled && p.sdlc_enabled).map(project => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="sdlc-form-group">
                <label htmlFor="new-task-description">شرح تسک *</label>
                <textarea
                  id="new-task-description"
                  value={newTask.description}
                  onChange={(e) => setNewTask({...newTask, description: e.target.value})}
                  placeholder="شرح کامل و دقیق نیاز، رفتار مورد انتظار، و محدودیت‌ها را بنویسید. این متن مستقیماً به Analysis Agent ارسال می‌شود."
                  rows={6}
                />
              </div>

              <div className="sdlc-form-row">
                <div className="sdlc-form-group" style={{flex:1}}>
                  <label htmlFor="new-task-priority">اولویت</label>
                  <select
                    id="new-task-priority"
                    value={newTask.priority}
                    onChange={(e) => setNewTask({...newTask, priority: e.target.value})}
                  >
                    <option value="low">🟢 پایین</option>
                    <option value="medium">🟡 متوسط</option>
                    <option value="high">🟠 بالا</option>
                    <option value="critical">🔴 بحرانی</option>
                  </select>
                </div>
              </div>

              {newTask.project_id && (() => {
                const proj = projects.find(p => p.id === newTask.project_id);
                if (!proj) return null;
                const stages = proj.workflow?.stages || [];
                return (
                  <div className="sdlc-task-pipeline-preview">
                    <small>مراحل اجرا در این پروژه:</small>
                    <div className="sdlc-pipeline-chips">
                      {stages.map((stage, i) => (
                        <span key={stage} className="sdlc-pipeline-chip">
                          {i > 0 && <span className="sdlc-chip-arrow">→</span>}
                          {stage}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })()}
            </div>

            <div className="sdlc-form-actions">
              <button
                className="sdlc-btn sdlc-btn-secondary"
                onClick={() => {
                  setShowTaskForm(false);
                  setError('');
                  setNewTask({ title:'', description:'', project_id:'', priority:'medium', tags:[] });
                }}
              >
                لغو
              </button>
              <button
                className="sdlc-btn sdlc-btn-primary"
                onClick={handleCreateTask}
                disabled={!newTask.title.trim() || !newTask.project_id.trim() || !newTask.description.trim()}
              >
                <Play size={14} />
                ایجاد و شروع تحلیل
              </button>
            </div>
          </div>
        </ModalShell>
      )}
      
      {/* Stats cards */}
      <div className="sdlc-stats-grid">
        <div className="sdlc-stat-card">
          <ClipboardList size={24} />
          <div>
            <span>کل تسک‌ها</span>
            <strong>{stats.total.toLocaleString('fa-IR')}</strong>
          </div>
        </div>
        
        <div className="sdlc-stat-card">
          <Play size={24} />
          <div>
            <span>در حال اجرا</span>
            <strong>{stats.active.toLocaleString('fa-IR')}</strong>
          </div>
        </div>
        
        <div className="sdlc-stat-card">
          <Eye size={24} />
          <div>
            <span>نیازمند تأیید</span>
            <strong>{stats.pendingHuman.toLocaleString('fa-IR')}</strong>
          </div>
        </div>
        
        <div className="sdlc-stat-card">
          <CheckCircle size={24} />
          <div>
            <span>انجام شده</span>
            <strong>{stats.completed.toLocaleString('fa-IR')}</strong>
          </div>
        </div>
        
        <div className="sdlc-stat-card">
          <XCircle size={24} />
          <div>
            <span>ناموفق</span>
            <strong>{stats.failed.toLocaleString('fa-IR')}</strong>
          </div>
        </div>
        
        <div className="sdlc-stat-card">
          <RefreshCw size={24} />
          <div>
            <span>بازبینی‌ها</span>
            <strong>{stats.revisions.toLocaleString('fa-IR')}</strong>
          </div>
        </div>
      </div>
      
      {/* Navigation tabs */}
      <div className="sdlc-tabs">
        <button 
          className={`sdlc-tab ${activeTab === 'pipeline' ? 'active' : ''}`}
          onClick={() => setActiveTab('pipeline')}
        >
          <BarChart3 size={16} />
          خط تولید
        </button>
        
        <button 
          className={`sdlc-tab ${activeTab === 'tasks' ? 'active' : ''}`}
          onClick={() => setActiveTab('tasks')}
        >
          <ClipboardList size={16} />
          همه تسک‌ها
        </button>
        
        <button 
          className={`sdlc-tab ${activeTab === 'interventions' ? 'active' : ''}`}
          onClick={() => setActiveTab('interventions')}
        >
          <MessageCircle size={16} />
          درخواست‌های انسانی
          {pendingInterventions.length > 0 && (
            <span className="sdlc-badge">{pendingInterventions.length}</span>
          )}
        </button>
        
        <button 
          className={`sdlc-tab ${activeTab === 'projects' ? 'active' : ''}`}
          onClick={() => setActiveTab('projects')}
        >
          <Settings size={16} />
          پروژه‌ها
        </button>

        <button
          className={`sdlc-tab ${activeTab === 'metrics' ? 'active' : ''}`}
          onClick={() => setActiveTab('metrics')}
        >
          <Gauge size={16} />
          آمار و خودکارسازی
        </button>
      </div>
      
      {/* Filters */}
      <div className="sdlc-filters">
        <div className="sdlc-search">
          <Search size={16} />
          <input 
            type="text" 
            placeholder="جست‌وجو در تسک‌ها..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        
        <div className="sdlc-filter-group">
          <select 
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
          >
            <option value="">همه پروژه‌ها</option>
            {(Array.isArray(projects) ? projects : []).map(project => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
          
          <select 
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
          >
            <option value="">همه وضعیت‌ها</option>
            {sdlcStages.map(stage => (
              <option key={stage.id} value={stage.id}>
                {stage.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      
      {/* Pipeline view */}
      {activeTab === 'pipeline' && (
        <div className="sdlc-pipeline">
          <div className="sdlc-pipeline-header">
            <h2>خط تولید SDLC</h2>
            <p>تسک‌ها بر اساس مرحله جاری</p>
          </div>
          
          <div className="sdlc-pipeline-stages">
            {sdlcStages.map(stage => {
              const stageTasks = tasksByStatus[stage.id] || [];
              const StageIcon = stage.icon;
              const foundIndex = stageTasks.findIndex(t => t.base_task.id === stageCursor[stage.id]);
              const currentIndex = foundIndex >= 0 ? foundIndex : 0;
              const currentTask = stageTasks[currentIndex];
              const moveStage = (event, offset) => {
                event.stopPropagation();
                const target = stageTasks[currentIndex + offset];
                if (target) setStageCursor(prev => ({ ...prev, [stage.id]: target.base_task.id }));
              };

              return (
                <div key={stage.id} className="sdlc-pipeline-stage">
                  <div className={`sdlc-stage-header ${stage.color}`}>
                    <StageIcon size={18} />
                    <h3>{stage.label}</h3>
                    <span className="sdlc-stage-count">
                      {stageTasks.length.toLocaleString('fa-IR')}
                    </span>
                  </div>
                  
                  <div className="sdlc-stage-tasks">
                    {stageTasks.length === 0 ? (
                      <div className="sdlc-empty-stage">هیچ تسکی در این مرحله نیست</div>
                    ) : (
                      [currentTask].map(task => (
                        <div key={task.base_task.id} className="sdlc-pipeline-task" onClick={() => handleViewTask(task)} style={{cursor: 'pointer'}}>
                          <div className="sdlc-task-header">
                            <span className="sdlc-task-id">{task.base_task.task_id}</span>
                            <span className={`sdlc-priority-dot sdlc-priority-${task.priority || 'medium'}`} title={task.priority}></span>
                          </div>
                          <p className="sdlc-task-title">{task.title || task.base_task.session_name}</p>
                          <div className="sdlc-task-meta">
                            <span className="sdlc-task-project">{task.project_config_id}</span>
                            {task.current_agent && (
                              <span className="sdlc-task-agent-badge">
                                {getAgentInfo(task.current_agent).label}
                              </span>
                            )}
                          </div>
                          <div className="sdlc-task-footer">
                            <span className="sdlc-task-time">{formatDate(task.updated_at)}</span>
                            {task.revision_count > 0 && (
                              <span className="sdlc-task-revisions">
                                <RefreshCw size={10} />
                                {task.revision_count}
                              </span>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                    
                    {stageTasks.length > 1 && (
                      <div className="sdlc-stage-nav">
                        <button
                          type="button"
                          className="sdlc-stage-nav-btn"
                          onClick={event => moveStage(event, -1)}
                          disabled={currentIndex === 0}
                        >
                          قبلی
                        </button>
                        <span className="sdlc-stage-nav-pos">
                          {(currentIndex + 1).toLocaleString('fa-IR')} / {stageTasks.length.toLocaleString('fa-IR')}
                        </span>
                        <button
                          type="button"
                          className="sdlc-stage-nav-btn"
                          onClick={event => moveStage(event, 1)}
                          disabled={currentIndex === stageTasks.length - 1}
                        >
                          بعدی
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
      
      {/* Tasks list view */}
      {activeTab === 'tasks' && (
        <div className="sdlc-tasks-list">
          <div className="sdlc-tasks-header">
            <h2>همه تسک‌های SDLC</h2>
            <p>نمایش کامل همه تسک‌ها با جزئیات</p>
          </div>
          
          {filteredTasks.length === 0 ? (
            <div className="sdlc-empty-list">
              <ClipboardList size={48} />
              <h3>هیچ تسکی یافت نشد</h3>
              <p>با تغییر فیلترها دوباره امتحان کنید یا یک تسک جدید ایجاد کنید</p>
            </div>
          ) : (
            <div className="sdlc-tasks-table">
              <table>
                <thead>
                  <tr>
                    <th>شناسه</th>
                    <th>عنوان</th>
                    <th>پروژه</th>
                    <th>مرحله</th>
                    <th>اولویت</th>
                    <th>آخرین بروزرسانی</th>
                    <th>بازبینی</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTasks.map(task => {
                    const stage = getStageInfo(task.sdlc_status);
                    const StageIcon = stage.icon;
                    const priorityColors = { low:'#6b8d72', medium:'#d97706', high:'#ea580c', critical:'#dc2626' };
                    const priorityLabels = { low:'پایین', medium:'متوسط', high:'بالا', critical:'بحرانی' };
                    const pri = task.priority || 'medium';

                    return (
                      <tr key={task.base_task.id}>
                        <td><code style={{fontSize:'11px'}}>{task.base_task.task_id}</code></td>
                        <td>
                          <strong>{task.title || task.base_task.session_name}</strong>
                          {task.description && (
                            <p className="sdlc-task-summary">
                              {task.description.substring(0, 80)}{task.description.length > 80 ? '…' : ''}
                            </p>
                          )}
                        </td>
                        <td>{task.project_config_id}</td>
                        <td>
                          <div className="sdlc-stage-badge">
                            <StageIcon size={13} />
                            <span>{stage.label}</span>
                          </div>
                        </td>
                        <td>
                          <span style={{fontSize:'11px', fontWeight:600, color: priorityColors[pri]}}>
                            {priorityLabels[pri]}
                          </span>
                        </td>
                        <td style={{fontSize:'11px', color:'#899087'}}>{formatDate(task.updated_at)}</td>
                        <td>
                          {task.revision_count > 0
                            ? <span className="sdlc-revision-count">{task.revision_count}</span>
                            : <span style={{color:'#c5c8c0'}}>—</span>
                          }
                        </td>
                        <td>
                          <button className="sdlc-action-btn" onClick={() => handleViewTask(task)}>مشاهده</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      
      {/* Human interventions view */}
      {activeTab === 'interventions' && (
        <div className="sdlc-interventions">
          <div className="sdlc-interventions-header">
            <h2>درخواست‌های انسانی</h2>
            <p>تأیید‌های مورد نیاز برای ادامه کار</p>
          </div>
          
          {pendingInterventions.length === 0 ? (
            <div className="sdlc-empty-list">
              <CheckCircle size={48} />
              <h3>هیچ درخواست تأییدی در انتظار نیست</h3>
              <p>تمام درخواست‌ها پاسخ داده شده‌اند</p>
            </div>
          ) : (
            <div className="sdlc-interventions-list">
              {(Array.isArray(pendingInterventions) ? pendingInterventions : []).map(intervention => (
                <div key={intervention.id} className="sdlc-intervention-card">
                  <div className="sdlc-intervention-header">
                    <div>
                      <strong>تسک: {intervention.task_id}</strong>
                      <span className="sdlc-intervention-agent">
                        از طرف: {intervention.requesting_agent}
                      </span>
                    </div>
                    <span className="sdlc-intervention-time">
                      {formatDate(intervention.created_at)}
                    </span>
                  </div>
                  
                  <div className="sdlc-intervention-body">
                    <h4>{intervention.reason}</h4>
                    <p style={{whiteSpace:'pre-wrap'}}>{intervention.description}</p>
                    {interventionHints[intervention.context?.kind] && (
                      <p className="sdlc-intervention-hint">{interventionHints[intervention.context?.kind]}</p>
                    )}

                    {intervention.response_options && intervention.response_options.length > 0 && (
                      <div className="sdlc-response-options">
                        <p>گزینه‌های پاسخ:</p>
                        <div className="sdlc-options-grid">
                          {intervention.response_options.map((option, index) => (
                            <button
                              key={index}
                              className="sdlc-option-btn"
                              onClick={() => handleInterventionResponse(intervention.id, option)}
                            >
                              {responseOptionLabels[option] || option}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    <div className="sdlc-custom-response">
                      <textarea
                        placeholder="پاسخ سفارشی خود را وارد کنید..."
                        rows={2}
                        id={`response-${intervention.id}`}
                      />
                      <button
                        className="sdlc-btn sdlc-btn-primary"
                        onClick={() => {
                          const response = document.getElementById(`response-${intervention.id}`).value;
                          if (response.trim()) {
                            handleInterventionResponse(intervention.id, response);
                          }
                        }}
                      >
                        ارسال پاسخ
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Task detail modal */}
      {selectedTask && (
        <ModalShell label="جزئیات تسک" onClose={() => { setSelectedTask(null); }}>
          <div className="sdlc-task-detail-modal" data-ui="M3">
            <div className="sdlc-form-header">
              <div>
                <h3>{selectedTask.title || selectedTask.base_task.session_name} <UiTag id="M3" name="TaskDetail"/></h3>
                <small style={{fontSize:'11px', color:'#899087'}}>
                  {selectedTask.base_task.task_id} · پروژه: {selectedTask.project_config_id}
                </small>
              </div>
              <button type="button" className="sdlc-form-close" onClick={() => setSelectedTask(null)}>
                <X size={20} />
              </button>
            </div>

            <div className="sdlc-form-body">
              {/* Status badges */}
              <div style={{display:'flex', gap:'8px', flexWrap:'wrap', marginBottom:'12px'}}>
                <UiTag id="M3-A" name="Status"/>
                {(() => {
                  const stage = getStageInfo(selectedTask.sdlc_status);
                  const StageIcon = stage.icon;
                  return (
                    <span className="sdlc-stage-badge">
                      <StageIcon size={13} />
                      {stage.label}
                    </span>
                  );
                })()}
                <span className={`sdlc-badge ${selectedTask.sdlc_status === 'done' ? 'green' : selectedTask.sdlc_status === 'failed' ? 'gray' : 'blue'}`}>
                  {selectedTask.sdlc_status}
                </span>
                {selectedTask.priority && (
                  <span style={{fontSize:'11px', fontWeight:600, color: {low:'#6b8d72',medium:'#d97706',high:'#ea580c',critical:'#dc2626'}[selectedTask.priority]}}>
                    اولویت: {{low:'پایین',medium:'متوسط',high:'بالا',critical:'بحرانی'}[selectedTask.priority]}
                  </span>
                )}
                {selectedTask.sdlc_status === 'pending_approval' && (
                  <button type="button" className="sdlc-btn sdlc-btn-primary" onClick={() => handleApprove(selectedTask.base_task.task_id)}>
                    <CheckCircle size={14} /> تأیید نهایی و ادغام در develop
                  </button>
                )}
                {selectedTask.sdlc_status === 'failed' && (
                  <>
                    {selectedTask.current_stage && (
                      <button type="button" className="sdlc-btn sdlc-btn-primary" onClick={() => handleRetryStage(selectedTask)}>
                        <RefreshCw size={14} /> اجرای مجدد مرحلهٔ {selectedTask.current_stage}
                      </button>
                    )}
                    <button type="button" className="sdlc-btn sdlc-btn-secondary" onClick={() => handleDeleteTask(selectedTask)}>
                      <X size={14} /> حذف تسک
                    </button>
                  </>
                )}
                {canSendBack(selectedTask) && problemText === null && (
                  <button type="button" className="sdlc-btn sdlc-btn-secondary" onClick={() => setProblemText('')}>
                    <MessageCircle size={14} /> مشکل دارد؛ ارجاع به تحلیل
                  </button>
                )}
              </div>

              {canSendBack(selectedTask) && problemText !== null && (
                <div className="sdlc-send-back" role="group" aria-label="ارجاع به تحلیل">
                  <label htmlFor="sdlc-send-back-text">نظر شما دربارهٔ مشکل</label>
                  <textarea id="sdlc-send-back-text" className="sdlc-send-back-text" rows={4} dir="auto" autoFocus
                    maxLength={4000} value={problemText} onChange={event => setProblemText(event.target.value)}
                    placeholder="چه چیزی اشتباه یا ناقص است؟ تحلیل‌گر این متن را الزام‌آور می‌داند و دوباره تحلیل می‌کند." />
                  <div className="sdlc-send-back-actions">
                    <button type="button" className="sdlc-btn sdlc-btn-primary" disabled={problemBusy || !problemText.trim()}
                      onClick={() => handleSendBack(selectedTask)}>
                      <Send size={14} /> {problemBusy ? 'در حال ارسال…' : 'ارسال به تحلیل‌گر'}
                    </button>
                    <button type="button" className="sdlc-btn sdlc-btn-secondary" disabled={problemBusy} onClick={() => setProblemText(null)}>انصراف</button>
                    <small>پس از تحلیل مجدد، تأیید تحلیل دوباره با شماست.</small>
                  </div>
                </div>
              )}

              {Object.entries(selectedTask.repos || {}).map(([path, repo]) => (
                <GitPanel key={path} taskId={selectedTask.base_task.task_id} repoPath={path} branch={repo.branch}
                  baseBranch={repo.base_branch || 'sandbox'} commitSha={repo.commit_sha} integration={repo.integration} />
              ))}

              <RiskBadge risk={selectedTask.risk} />

              {(selectedTask.transition_reason || selectedTask.revision_count > 0) && (
                <div className="sdlc-detail-section sdlc-detail-status">
                  {selectedTask.transition_reason && <p>{selectedTask.transition_reason}</p>}
                  {selectedTask.revision_count > 0 && <p>دفعات بازبینی: {selectedTask.revision_count}</p>}
                </div>
              )}

              <Timeline events={selectedTask.timeline} />

              {/* Questions stages asked the analyst (and the human, through the analyst) */}
              {(selectedTask.stage_questions || []).length > 0 && (
                <div className="sdlc-detail-section">
                  <h4>پرسش و پاسخ بین مرحله‌ها ({selectedTask.stage_questions.length}) <UiTag id="M3-Q" name="StageQuestions"/></h4>
                  {selectedTask.stage_questions.map(q => (
                    <div key={q.id} className="sdlc-agent-result-card">
                      <div className="sdlc-agent-result-header">
                        <span className="sdlc-agent-result-badge">{q.asking_stage} ← analysis</span>
                        <span className="sdlc-agent-result-status">
                          {q.status === 'answered' ? (q.answered_by === 'human' ? 'پاسخ اپراتور (از طریق تحلیل‌گر)' : 'پاسخ تحلیل‌گر') : 'در انتظار پاسخ'}
                        </span>
                      </div>
                      <p className="sdlc-agent-result-summary" dir="auto"><b>سؤال:</b> {q.question}</p>
                      {q.answer && <p className="sdlc-agent-result-summary" dir="auto"><b>پاسخ:</b> {q.answer}</p>}
                    </div>
                  ))}
                </div>
              )}

              {/* Live output of the agent that is running right now */}
              {selectedTask.base_task?.live_output && (
                <div className="sdlc-detail-section">
                  <h4>خروجی زندهٔ عامل — {selectedTask.current_stage} <UiTag id="M3-B" name="LiveOutput"/></h4>
                  <pre className="sdlc-live-output" dir="ltr">{selectedTask.base_task.live_output.slice(-6000)}</pre>
                </div>
              )}

              {/* Description */}
              {selectedTask.description && (
                <div className="sdlc-detail-section">
                  <h4>شرح تسک <UiTag id="M3-C" name="Description"/></h4>
                  <p className="sdlc-detail-text" dir="auto">{selectedTask.description}</p>
                </div>
              )}

              {/* Agent results */}
              {Object.keys(selectedTask.agent_results || {}).length > 0 && (
                <div className="sdlc-detail-section">
                  <h4>نتایج Agentها ({Object.keys(selectedTask.agent_results).length}) <UiTag id="M3-D" name="AgentResults"/></h4>
                  {Object.entries(selectedTask.agent_results).map(([agentKey, result]) => (
                    <div key={agentKey} className="sdlc-agent-result-card">
                      <div className="sdlc-agent-result-header">
                        <span className={`sdlc-agent-result-badge ${result.status}`}>{agentKey}</span>
                        <span className="sdlc-agent-result-status">{result.status}</span>
                      </div>
                      {result.summary && (
                        <p className="sdlc-agent-result-summary" dir="auto">{result.summary}</p>
                      )}
                      {result.changes && result.changes.length > 0 && (
                        <div className="sdlc-agent-changes">
                          <small>تغییرات ({result.changes.length}):</small>
                          <ul>
                            {result.changes.map((c, i) => (
                              <li key={i}>
                                <div className="sdlc-change-file" dir="ltr"><code>{c.file}</code>{c.kind ? <em className="sdlc-change-kind">{c.kind}</em> : null}</div>
                                {c.description ? <div className="sdlc-change-desc" dir="auto">{c.description}</div> : null}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {result.issues && result.issues.length > 0 && (
                        <div className="sdlc-agent-issues">
                          <small>مسائل باز ({result.issues.length}):</small>
                          <ul>{result.issues.map((issue, i) => <li key={i} dir="auto">{issue}</li>)}</ul>
                        </div>
                      )}
                      {result.raw_output && result.raw_output.length > 10 && (
                        <details style={{marginTop:'8px'}}>
                          <summary style={{cursor:'pointer', fontSize:'11px', color:'#6b8d72'}}>خروجی کامل</summary>
                          <pre className="sdlc-raw-output">{result.raw_output}</pre>
                        </details>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Metadata */}
              <div className="sdlc-detail-section">
                <h4>اطلاعات اجرا <UiTag id="M3-E" name="RunInfo"/></h4>
                <div className="sdlc-review-row"><span>مرحله فعلی</span><span>{selectedTask.current_stage}</span></div>
                <div className="sdlc-review-row"><span>Agent فعلی</span><span>{selectedTask.current_agent}</span></div>
                <div className="sdlc-review-row"><span>تعداد بازبینی</span><span>{selectedTask.revision_count}</span></div>
                <div className="sdlc-review-row"><span>ایجاد</span><span>{formatDate(selectedTask.created_at)}</span></div>
                <div className="sdlc-review-row"><span>آخرین به‌روزرسانی</span><span>{formatDate(selectedTask.updated_at)}</span></div>
              </div>

              {/* GitHub Integration for agents */}
              <div className="sdlc-detail-section">
                <h4>GitHub — Commit، Push و Pull Request <UiTag id="M3-F" name="GitHub"/></h4>
                <div style={{padding: '12px 14px', fontSize: '12px', color: '#384239'}}>
                  {Object.values(selectedTask.repos || {}).length > 0 ? (
                    <div className="sdlc-task-repos">
                      {Object.values(selectedTask.repos).map(repo => (
                        <div key={repo.path} className="sdlc-task-repo" dir="ltr">
                          <code>{repo.path}</code>
                          <span>{repo.branch} ← {repo.base_branch}</span>
                          {repo.commit_sha && <span>commit {repo.commit_sha.slice(0, 8)}{repo.pushed ? ' (pushed)' : ''}</span>}
                          {repo.pr_url && <a href={repo.pr_url} target="_blank" rel="noreferrer">PR #{repo.pr_number}</a>}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="sdlc-intervention-hint">این تسک هنوز در هیچ پوشهٔ git کار نکرده است؛ برنچ <code dir="ltr">sdlc/&lt;task-id&gt;</code> هنگام اجرای اولین مرحله ساخته می‌شود.</p>
                  )}
                  <StageRepoActions task={selectedTask} project={projects.find(p => p.id === selectedTask.project_config_id)} onDone={loadSDLCData} />
                  <p className="sdlc-intervention-hint">اگر URL و Token را خالی بگذارید، <code dir="ltr">github_config</code> همان agent در پروژه یا متغیر محیطی <code dir="ltr">GITHUB_TOKEN</code> استفاده می‌شود. Token جایی ذخیره نمی‌شود.</p>
                  {['backend', 'n8n', 'frontend'].map(agent => (
                    <div key={agent} style={{marginBottom: '16px', borderBottom: '1px solid #e2e3dd', paddingBottom: '12px'}}>
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px'}}>
                        <strong style={{textTransform: 'capitalize'}}>{agent} Agent</strong>
                        <button
                          onClick={() => setAgentGithubDialogs({...agentGithubDialogs, [agent]: !agentGithubDialogs[agent]})}
                          style={{padding: '4px 12px', fontSize: '11px', background: '#173f2b', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer'}}
                        >
                          {agentGithubDialogs[agent] ? 'بستن' : 'تنظیم GitHub'}
                        </button>
                      </div>
                      
                      {agentGithubDialogs[agent] && (
                        <div style={{background: '#f5f7f4', padding: '12px', borderRadius: '6px', marginTop: '8px'}}>
                          <div style={{marginBottom: '10px'}}>
                            <label style={{display: 'block', fontSize: '11px', fontWeight: 600, marginBottom: '4px', color: '#50574f'}}>GitHub Repository URL</label>
                            <input
                              type="text"
                              placeholder="https://github.com/user/repo"
                              dir="ltr"
                              value={githubCredentials[agent].url}
                              onChange={(e) => setGithubCredentials({
                                ...githubCredentials,
                                [agent]: {...githubCredentials[agent], url: e.target.value}
                              })}
                              style={{width: '100%', padding: '8px', fontSize: '12px', border: '1px solid #d9dcd4', borderRadius: '6px', fontFamily: 'monospace'}}
                            />
                          </div>
                          
                          <div style={{marginBottom: '10px'}}>
                            <label style={{display: 'block', fontSize: '11px', fontWeight: 600, marginBottom: '4px', color: '#50574f'}}>GitHub Token (PAT)</label>
                            <div style={{display: 'flex', gap: '8px'}}>
                              <input
                                type={githubCredentials[agent].showToken ? "text" : "password"}
                                placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                                dir="ltr"
                                value={githubCredentials[agent].token}
                                onChange={(e) => setGithubCredentials({
                                  ...githubCredentials,
                                  [agent]: {...githubCredentials[agent], token: e.target.value}
                                })}
                                style={{flex: 1, padding: '8px', fontSize: '12px', border: '1px solid #d9dcd4', borderRadius: '6px', fontFamily: 'monospace'}}
                              />
                              <button
                                onClick={() => setGithubCredentials({
                                  ...githubCredentials,
                                  [agent]: {...githubCredentials[agent], showToken: !githubCredentials[agent].showToken}
                                })}
                                style={{padding: '8px 10px', fontSize: '11px', background: '#e8ede4', border: 'none', borderRadius: '6px', cursor: 'pointer'}}
                              >
                                {githubCredentials[agent].showToken ? '🙈' : '👁️'}
                              </button>
                            </div>
                            <small style={{display: 'block', color: '#899087', marginTop: '4px'}}>
                              Create at https://github.com/settings/tokens (repo scope required)
                            </small>
                          </div>
                          
                          <div style={{display: 'flex', gap: '8px'}}>
                            <button
                              onClick={() => {
                                // Save credentials and validate
                                fetch(`${API}/api/sdlc/tasks/${selectedTask.base_task.task_id}/github/validate`, {
                                  method: 'POST',
                                  headers: {'Content-Type': 'application/json'},
                                  body: JSON.stringify({
                                    agent: agent,
                                    repo_url: githubCredentials[agent].url,
                                    github_token: githubCredentials[agent].token
                                  })
                                })
                                .then(readJsonOrThrow)
                                .then(data => {
                                  if (data.status === 'valid') {
                                    alert(`[A3 GitHubValidate] ✅ GitHub credentials تأیید شدند!\nRepository: ${data.owner}/${data.repo}`);
                                  } else {
                                    alert(`[A3 GitHubValidate] ❌ خطا: ${data.message}`);
                                  }
                                })
                                .catch(err => alert(`[A3 GitHubValidate] ❌ خطا: ${err.message}`));
                              }}
                              style={{flex: 1, padding: '8px 12px', fontSize: '11px', background: '#173f2b', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer'}}
                            >
                              ✓ بررسی دسترسی
                            </button>
                            <button
                              onClick={() => {
                                // Commit and push
                                fetch(`${API}/api/sdlc/tasks/${selectedTask.base_task.task_id}/github/commit-push`, {
                                  method: 'POST',
                                  headers: {'Content-Type': 'application/json'},
                                  body: JSON.stringify({
                                    agent: agent,
                                    repo_url: githubCredentials[agent].url,
                                    github_token: githubCredentials[agent].token
                                  })
                                })
                                .then(readJsonOrThrow)
                                .then(data => {
                                  alert(`[A4 CommitPush] ✅ ${data.message}\n\nCommit: ${data.commit_sha}\nBranch: ${data.branch}`);
                                  loadSDLCData();
                                })
                                .catch(err => alert(`[A4 CommitPush] ❌ خطا: ${err.message}`));
                              }}
                              style={{flex: 1, padding: '8px 12px', fontSize: '11px', background: '#6b8d72', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer'}}
                            >
                              📤 Commit و Push
                            </button>
                            <button
                              onClick={() => {
                                // Create PR
                                fetch(`${API}/api/sdlc/tasks/${selectedTask.base_task.task_id}/github/create-pr`, {
                                  method: 'POST',
                                  headers: {'Content-Type': 'application/json'},
                                  body: JSON.stringify({
                                    agent: agent,
                                    repo_url: githubCredentials[agent].url,
                                    github_token: githubCredentials[agent].token
                                  })
                                })
                                .then(readJsonOrThrow)
                                .then(data => {
                                  alert(`[A5 PullRequest] ✅ ${data.message}\n\nPR #${data.pr_number}\nURL: ${data.pr_url}`);
                                  loadSDLCData();
                                })
                                .catch(err => alert(`[A5 PullRequest] ❌ خطا: ${err.message}`));
                              }}
                              style={{flex: 1, padding: '8px 12px', fontSize: '11px', background: '#d97706', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer'}}
                            >
                              🔀 Pull Request
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="sdlc-form-actions">
              <button className="sdlc-btn sdlc-btn-primary" onClick={() => setSelectedTask(null)}>بستن</button>
            </div>
          </div>
        </ModalShell>
      )}

      {/* Projects view */}
      {activeTab === 'metrics' && <MetricsPanel project={selectedProject} />}

      {activeTab === 'projects' && (
        <div className="sdlc-projects">
          <div className="sdlc-projects-header">
            <div>
              <h2>پروژه‌های SDLC</h2>
              <p>تنظیمات و پیکربندی پروژه‌ها</p>
            </div>
            <div className="sdlc-projects-header-actions">
            <ProjectBuilder onCreated={() => loadSDLCData()} />
            <button
              className="sdlc-btn sdlc-btn-primary"
              onClick={() => {
                setNewProject({
                  id: '',
                  name: '',
                  description: '',
                  enabled: true,
                  sdlc_enabled: true,
                  workflow: {
                    stages: ['analysis', 'backend', 'n8n', 'frontend', 'qa'],
                    sequential: true,
                    allow_parallel: false,
                    max_revision_attempts: 3,
                    require_analysis_approval: false,
                    require_final_human_approval: false
                  },
                  agents: {
                    analysis: { 
                      enabled: true, 
                      knowledge_path: '',
                      project_path: '',
                      system_prompt: '',
                      test_instructions: {},
                      timeout_seconds: 300,
                      max_retries: 2
                    },
                    backend: { 
                      enabled: true, 
                      knowledge_path: '',
                      project_path: '',
                      system_prompt: '',
                      test_instructions: {},
                      timeout_seconds: 300,
                      max_retries: 2
                    },
                    n8n: { 
                      enabled: true, 
                      knowledge_path: '',
                      project_path: '',
                      system_prompt: '',
                      test_instructions: {},
                      timeout_seconds: 300,
                      max_retries: 2
                    },
                    frontend: { 
                      enabled: true, 
                      knowledge_path: '',
                      project_path: '',
                      system_prompt: '',
                      test_instructions: {},
                      timeout_seconds: 300,
                      max_retries: 2
                    },
                    qa: { 
                      enabled: true, 
                      knowledge_path: '',
                      project_path: '',
                      system_prompt: '',
                      test_instructions: {},
                      timeout_seconds: 300,
                      max_retries: 2
                    }
                  }
                });
                setIsEditingProject(false);
                setEditingProjectId('');
                setShowProjectForm(true);
              }}
            >
              <Plus size={16} />
              پروژه جدید
            </button>
            </div>
          </div>
          
          {/* Project form modal */}
          {showProjectForm && (
            <ModalShell label="فرم پروژه" onClose={() => { setShowProjectForm(false); setIsEditingProject(false); setEditingProjectId(''); setProjectFormStep(1); }}>
            <div className="sdlc-project-form sdlc-project-wizard" data-ui="M4">
              <div className="sdlc-form-header">
                <h3>{isEditingProject ? 'ویرایش پروژه' : 'ایجاد پروژه جدید'} <UiTag id="M4" name="ProjectForm"/></h3>
                <button type="button" className="sdlc-form-close" onClick={() => {
                  setShowProjectForm(false);
                  setIsEditingProject(false);
                  setEditingProjectId('');
                  setProjectFormStep(1);
                }}>
                  <X size={20} />
                </button>
              </div>
              
              {/* Wizard Steps */}
              <div className="sdlc-wizard-steps">
                {[
                  { step: 1, label: 'اطلاعات پروژه' },
                  { step: 2, label: 'تنظیمات Workflow' },
                  { step: 3, label: 'تنظیمات Agents' },
                  { step: 4, label: 'تأیید نهایی' }
                ].map(({ step, label }) => (
                  <div
                    key={step}
                    className={`sdlc-wizard-step ${projectFormStep === step ? 'active' : ''} ${projectFormStep > step ? 'done' : ''}`}
                    onClick={() => { if (projectFormStep > step) setProjectFormStep(step); }}
                  >
                    <div className="sdlc-wizard-step-num">
                      {projectFormStep > step ? <CheckCircle size={14} /> : step}
                    </div>
                    <span>{label}</span>
                  </div>
                ))}
              </div>
              
              <div className="sdlc-form-body">
                <UiTag id={`M4-${projectFormStep}`} name={['', 'ProjectInfo', 'Workflow', 'Agents', 'Review'][projectFormStep]}/>

                {/* ── Step 1: Project Info ── */}
                {projectFormStep === 1 && (
                  <>
                    <div className="sdlc-form-group">
                      <label htmlFor="new-project-id">
                        شناسه پروژه
                        {!isEditingProject && <small> — پس از ایجاد قابل تغییر نیست</small>}
                      </label>
                      <input
                        id="new-project-id"
                        type="text"
                        value={newProject.id}
                        onChange={(e) => setNewProject({...newProject, id: e.target.value.toLowerCase().replace(/\s+/g, '-')})}
                        placeholder="my-project-id"
                        disabled={isEditingProject}
                      />
                    </div>

                    <div className="sdlc-form-group">
                      <label htmlFor="new-project-name">نام پروژه *</label>
                      <input
                        id="new-project-name"
                        type="text"
                        value={newProject.name}
                        onChange={(e) => setNewProject({...newProject, name: e.target.value})}
                        placeholder="نام نمایشی پروژه"
                      />
                    </div>

                    <div className="sdlc-form-group">
                      <label htmlFor="new-project-description">توضیحات</label>
                      <textarea
                        id="new-project-description"
                        value={newProject.description}
                        onChange={(e) => setNewProject({...newProject, description: e.target.value})}
                        placeholder="توضیح مختصر درباره پروژه و اهداف آن"
                        rows={4}
                      />
                    </div>

                    <div className="sdlc-form-row">
                      <label className="sdlc-form-toggle">
                        <input
                          type="checkbox"
                          checked={newProject.enabled}
                          onChange={(e) => setNewProject({...newProject, enabled: e.target.checked})}
                        />
                        <span>پروژه فعال</span>
                      </label>
                      <label className="sdlc-form-toggle">
                        <input
                          type="checkbox"
                          checked={newProject.sdlc_enabled}
                          onChange={(e) => setNewProject({...newProject, sdlc_enabled: e.target.checked})}
                        />
                        <span>SDLC فعال</span>
                      </label>
                    </div>
                  </>
                )}

                {/* ── Step 2: Workflow ── */}
                {projectFormStep === 2 && (
                  <>
                    <div className="sdlc-form-group">
                      <label>مراحل اجرایی</label>
                      <small className="sdlc-form-hint">با کلیک روی هر مرحله می‌توانید ترتیب را تغییر دهید</small>
                      <div className="sdlc-stages-editor">
                        {newProject.workflow.stages.map((stage, idx) => (
                          <div key={idx} className="sdlc-stage-chip">
                            <span>{stage}</span>
                            <button
                              type="button"
                              onClick={() => {
                                const stages = newProject.workflow.stages.filter((_, i) => i !== idx);
                                setNewProject({...newProject, workflow: {...newProject.workflow, stages}});
                              }}
                            >
                              <X size={10} />
                            </button>
                          </div>
                        ))}
                        <input
                          className="sdlc-stage-add-input"
                          placeholder="+ افزودن مرحله"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && e.target.value.trim()) {
                              e.preventDefault();
                              const val = e.target.value.trim();
                              setNewProject({...newProject, workflow: {...newProject.workflow, stages: [...newProject.workflow.stages, val]}});
                              e.target.value = '';
                            }
                          }}
                        />
                      </div>
                    </div>

                    <div className="sdlc-form-row">
                      <label className="sdlc-form-toggle">
                        <input
                          type="checkbox"
                          checked={newProject.workflow.sequential}
                          onChange={(e) => setNewProject({...newProject, workflow: {...newProject.workflow, sequential: e.target.checked}})}
                        />
                        <span>اجرای ترتیبی</span>
                      </label>
                      <label className="sdlc-form-toggle">
                        <input
                          type="checkbox"
                          checked={newProject.workflow.allow_parallel}
                          onChange={(e) => setNewProject({...newProject, workflow: {...newProject.workflow, allow_parallel: e.target.checked}})}
                        />
                        <span>اجرای موازی مجاز</span>
                      </label>
                    </div>

                    <div className="sdlc-form-row">
                      <div className="sdlc-form-group">
                        <label>حداکثر تلاش‌های Revision</label>
                        <input
                          type="number" min="1" max="10"
                          value={newProject.workflow.max_revision_attempts}
                          onChange={(e) => setNewProject({...newProject, workflow: {...newProject.workflow, max_revision_attempts: parseInt(e.target.value) || 3}})}
                        />
                      </div>
                    </div>

                    <div className="sdlc-form-row">
                      <label className="sdlc-form-toggle">
                        <input
                          type="checkbox"
                          checked={newProject.workflow.require_analysis_approval}
                          onChange={(e) => setNewProject({...newProject, workflow: {...newProject.workflow, require_analysis_approval: e.target.checked}})}
                        />
                        <span>تأیید تحلیل توسط انسان</span>
                      </label>
                      <label className="sdlc-form-toggle">
                        <input
                          type="checkbox"
                          checked={newProject.workflow.require_final_human_approval}
                          onChange={(e) => setNewProject({...newProject, workflow: {...newProject.workflow, require_final_human_approval: e.target.checked}})}
                        />
                        <span>تأیید نهایی توسط انسان</span>
                      </label>
                    </div>

                    <AutonomyFields
                      workflow={withAutonomyDefaults(newProject.workflow)}
                      onChange={(patch) => setNewProject({...newProject, workflow: {...withAutonomyDefaults(newProject.workflow), ...patch}})}
                    />
                  </>
                )}

                {/* ── Step 3: Agents ── */}
                {projectFormStep === 3 && (() => {
                  const agentDefs = [
                    { key: 'analysis',  label: 'Analysis',  icon: '🔍', color: '#3b82f6' },
                    { key: 'backend',   label: 'Backend',   icon: '⚙️', color: '#8b5cf6' },
                    { key: 'n8n',       label: 'n8n',       icon: '🔗', color: '#6366f1' },
                    { key: 'frontend',  label: 'Frontend',  icon: '🎨', color: '#ec4899' },
                    { key: 'qa',        label: 'QA',        icon: '✅', color: '#f97316' },
                  ];
                  
                  // Helper to ensure github_config always exists
                  const ensureGithubConfig = (agentConfig) => ({
                    ...agentConfig,
                    github_config: agentConfig?.github_config || {
                      repository_url: '',
                      github_token: '',
                      branch: 'main',
                      auto_commit: false,
                      auto_push: false,
                      auto_pr: false,
                      showToken: false
                    }
                  });
                  
                  const updateAgent = (key, field, val) => {
                    const currentAgent = newProject.agents[key] || {};
                    const updatedAgent = ensureGithubConfig({...currentAgent, [field]: val});
                    setNewProject({...newProject, agents: {...newProject.agents, [key]: updatedAgent}});
                  };

                  return (
                    <>
                      <div className="sdlc-agent-tabs">
                        {agentDefs.map(({ key, label, icon, color }) => (
                          <button
                            key={key}
                            type="button"
                            className={`sdlc-agent-tab ${activeAgentTab === key ? 'active' : ''} ${!newProject.agents[key]?.enabled ? 'disabled' : ''}`}
                            style={activeAgentTab === key ? { borderBottomColor: color, color } : {}}
                            onClick={() => setActiveAgentTab(key)}
                          >
                            <span>{icon}</span>
                            {label}
                            {!newProject.agents[key]?.enabled && <span className="sdlc-tab-off-badge">off</span>}
                          </button>
                        ))}
                      </div>

                      {agentDefs.filter(a => a.key === activeAgentTab).map(({ key, label, color }) => (
                        <div key={key} className="sdlc-agent-panel">
                          <div className="sdlc-agent-panel-header" style={{ borderRightColor: color }}>
                            <div>
                              <h4>{label} Agent</h4>
                              <small>تنظیمات اختصاصی این عامل</small>
                            </div>
                            <label className="sdlc-form-toggle">
                              <input
                                type="checkbox"
                                checked={newProject.agents[key]?.enabled ?? true}
                                onChange={(e) => updateAgent(key, 'enabled', e.target.checked)}
                              />
                              <span>فعال</span>
                            </label>
                          </div>

                          {newProject.agents[key]?.enabled && (
                            <div className="sdlc-agent-panel-body">
                              <div className="sdlc-form-row">
                                <div className="sdlc-form-group">
                                  <label>Knowledge Path</label>
                                  <input
                                    type="text"
                                    value={newProject.agents[key].knowledge_path}
                                    onChange={(e) => updateAgent(key, 'knowledge_path', e.target.value)}
                                    placeholder={`docs/${key}/`}
                                  />
                                </div>
                                <div className="sdlc-form-group">
                                  <label>Project Path</label>
                                  <input
                                    type="text"
                                    value={newProject.agents[key].project_path}
                                    onChange={(e) => updateAgent(key, 'project_path', e.target.value)}
                                    placeholder={key === 'qa' ? '' : `src/${key}/`}
                                  />
                                </div>
                              </div>

                              <div className="sdlc-form-group">
                                <label>System Prompt</label>
                                <textarea
                                  value={newProject.agents[key].system_prompt}
                                  onChange={(e) => updateAgent(key, 'system_prompt', e.target.value)}
                                  placeholder={`دستورالعمل اختصاصی برای ${label} Agent...`}
                                  rows={5}
                                />
                              </div>

                              <div className="sdlc-form-row">
                                <div className="sdlc-form-group">
                                  <label>Timeout (ثانیه)</label>
                                  <input
                                    type="number" min="30" max="3600"
                                    value={newProject.agents[key].timeout_seconds}
                                    onChange={(e) => updateAgent(key, 'timeout_seconds', parseInt(e.target.value) || 300)}
                                  />
                                </div>
                                <div className="sdlc-form-group">
                                  <label>Max Retries</label>
                                  <input
                                    type="number" min="0" max="10"
                                    value={newProject.agents[key].max_retries}
                                    onChange={(e) => updateAgent(key, 'max_retries', parseInt(e.target.value) || 2)}
                                  />
                                </div>
                              </div>

                              <div className="sdlc-form-group">
                                <label>Install Command (نصب وابستگی‌ها)</label>
                                <input
                                  type="text" dir="ltr"
                                  value={newProject.agents[key].setup_command || ''}
                                  onChange={(e) => updateAgent(key, 'setup_command', e.target.value)}
                                  placeholder={key === 'frontend' ? 'npm install' : key === 'backend' ? 'pip install -r requirements.txt' : ''}
                                />
                                <small className="sdlc-intervention-hint">
                                  با دکمهٔ «نصب» در پنجرهٔ اجرا (▶ اجرا) در پوشهٔ همین agent اجرا می‌شود.
                                </small>
                              </div>

                              <div className="sdlc-form-group">
                                <label>Run Command (دکمهٔ ▶) <UiTag id="M4-3C" name="RunCommand" /></label>
                                <input
                                  type="text" dir="ltr"
                                  value={newProject.agents[key].run_command || ''}
                                  onChange={(e) => updateAgent(key, 'run_command', e.target.value)}
                                  placeholder={key === 'frontend' ? 'npm run dev' : key === 'backend' ? 'uvicorn app.main:app --reload' : ''}
                                />
                                <small className="sdlc-intervention-hint">
                                  در پوشهٔ همین agent (ریپو یا Project Path) اجرا می‌شود. در کارت پروژه دکمهٔ ▶ / ■ نمایش داده می‌شود.
                                </small>
                              </div>

                              <RepositorySettings
                                project={newProject}
                                stage={key}
                                repository={newProject.agents[key]?.repository}
                                onChange={patch => setNewProject(current => ({
                                  ...current,
                                  agents: { ...current.agents, [key]: { ...(current.agents[key] || {}),
                                    repository: { ...DEFAULT_REPOSITORY, ...(current.agents[key]?.repository || {}), ...patch } } },
                                }))}
                                canPrepare={isEditingProject}
                              />
                            </div>
                          )}
                        </div>
                      ))}
                    </>
                  );
                })()}

                {/* ── Step 4: Review ── */}
                {projectFormStep === 4 && (
                  <div className="sdlc-review">
                    <div className="sdlc-review-section">
                      <h4>اطلاعات پروژه</h4>
                      <div className="sdlc-review-row"><span>شناسه</span><code>{newProject.id || '—'}</code></div>
                      <div className="sdlc-review-row"><span>نام</span><strong>{newProject.name || '—'}</strong></div>
                      <div className="sdlc-review-row"><span>توضیحات</span><span>{newProject.description || '—'}</span></div>
                      <div className="sdlc-review-row">
                        <span>وضعیت</span>
                        <span>
                          {newProject.enabled ? <span className="sdlc-badge green">فعال</span> : <span className="sdlc-badge gray">غیرفعال</span>}
                          {' '}
                          {newProject.sdlc_enabled ? <span className="sdlc-badge blue">SDLC فعال</span> : <span className="sdlc-badge gray">SDLC غیرفعال</span>}
                        </span>
                      </div>
                    </div>

                    <div className="sdlc-review-section">
                      <h4>Workflow</h4>
                      <div className="sdlc-review-row"><span>مراحل</span><span>{newProject.workflow.stages.join(' → ')}</span></div>
                      <div className="sdlc-review-row"><span>اجرای ترتیبی</span><span>{newProject.workflow.sequential ? 'بله' : 'خیر'}</span></div>
                      <div className="sdlc-review-row"><span>حداکثر Revision</span><span>{newProject.workflow.max_revision_attempts}</span></div>
                      <div className="sdlc-review-row"><span>تأیید تحلیل</span><span>{newProject.workflow.require_analysis_approval ? 'الزامی' : 'اختیاری'}</span></div>
                      <div className="sdlc-review-row"><span>تصمیم‌های خودکار</span><span>{autonomySummary(newProject.workflow)}</span></div>
                      <div className="sdlc-review-row"><span>تأیید نهایی</span><span>{newProject.workflow.require_final_human_approval ? 'الزامی' : 'اختیاری'}</span></div>
                    </div>

                    <div className="sdlc-review-section">
                      <h4>Agents</h4>
                      {['analysis', 'backend', 'n8n', 'frontend', 'qa'].map(key => (
                        <div key={key} className="sdlc-review-row">
                          <span>{key}</span>
                          {newProject.agents[key]?.enabled
                            ? <span className="sdlc-badge green">فعال</span>
                            : <span className="sdlc-badge gray">غیرفعال</span>
                          }
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Wizard navigation */}
                <div className="sdlc-wizard-nav">
                  {projectFormStep > 1 ? (
                    <button className="sdlc-btn sdlc-btn-secondary" onClick={() => setProjectFormStep(s => s - 1)}>
                      قبلی
                    </button>
                  ) : (
                    <button className="sdlc-btn sdlc-btn-secondary" onClick={() => { setShowProjectForm(false); setIsEditingProject(false); setEditingProjectId(''); setProjectFormStep(1); }}>
                      لغو
                    </button>
                  )}

                  {projectFormStep < 4 ? (
                    <button
                      className="sdlc-btn sdlc-btn-primary"
                      onClick={() => setProjectFormStep(s => s + 1)}
                      disabled={projectFormStep === 1 && (!newProject.id.trim() || !newProject.name.trim())}
                    >
                      بعدی
                    </button>
                  ) : (
                    <button
                      className="sdlc-btn sdlc-btn-primary"
                      onClick={handleSaveProject}
                      disabled={!newProject.id.trim() || !newProject.name.trim()}
                    >
                      {isEditingProject ? 'به‌روزرسانی پروژه' : 'ایجاد پروژه'}
                    </button>
                  )}
                </div>
              </div>
            </div>
            </ModalShell>
          )}
          
          {projects.length === 0 ? (
            <div className="sdlc-empty-list">
              <Settings size={48} />
              <h3>هیچ پروژه‌ای تعریف نشده</h3>
              <p>برای شروع، روی دکمه "پروژه جدید" کلیک کنید</p>
            </div>
          ) : (
            <div className="sdlc-projects-grid">
              {(Array.isArray(projects) ? projects : []).map(project => (
                <div key={project.id} className="sdlc-project-card">
                  <div className="sdlc-project-header">
                    <h3>{project.name}</h3>
                    <span className={`sdlc-project-status ${project.enabled ? 'enabled' : 'disabled'}`}>
                      {project.enabled ? 'فعال' : 'غیرفعال'}
                    </span>
                  </div>
                  
                  <p className="sdlc-project-description">{project.description}</p>
                  
                  <div className="sdlc-project-details">
                    <div className="sdlc-project-detail">
                      <span>شناسه:</span>
                      <code>{project.id}</code>
                    </div>
                    
                    <div className="sdlc-project-detail">
                      <span>وضعیت SDLC:</span>
                      <span className={`sdlc-sdlc-status ${project.sdlc_enabled ? 'enabled' : 'disabled'}`}>
                        {project.sdlc_enabled ? 'فعال' : 'غیرفعال'}
                      </span>
                    </div>
                    
                    <div className="sdlc-project-detail">
                      <span>مراحل:</span>
                      <span>{project.workflow.stages.length} مرحله</span>
                    </div>
                    
                    <div className="sdlc-project-detail">
                      <span>عامل‌های فعال:</span>
                      <span>
                        {Object.values(project.agents).filter(agent => agent.enabled).length} عامل
                      </span>
                    </div>
                  </div>
                  
                  <ProjectRunControls project={project} />

                  <div className="sdlc-project-actions">
                    <button className="sdlc-action-btn" onClick={() => handleEditProject(project)}>ویرایش</button>
                    <RunGuideButton project={project} />
                    <button className="sdlc-action-btn" onClick={() => handleViewProject(project)}>مشاهده</button>
                    <button className="sdlc-action-btn" onClick={() => handleCreateTaskFromProject(project)}>ایجاد تسک</button>
                    <button className="sdlc-action-btn sdlc-action-btn-danger" onClick={() => handleDeleteProject(project.id)}>حذف</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// M5: "Run" dialog — edit RUN_TEST.md / RUN_REAL.md of the backend/frontend stages, then let Claude Code follow it.
function RunGuideButton({ project }) {
  const [open, setOpen] = useState(false);
  const stages = ['backend', 'frontend'].filter(s => project.agents?.[s]?.enabled);
  if (stages.length === 0) return null;
  return (
    <>
      <button className="sdlc-action-btn" onClick={() => setOpen(true)}><Play size={12} /> اجرا</button>
      {open && <RunGuideDialog project={project} stages={stages} onClose={() => setOpen(false)} />}
    </>
  );
}

function RunGuideDialog({ project, stages, onClose }) {
  const [stage, setStage] = useState(stages[0]);
  const [mode, setMode] = useState('test');
  const [drafts, setDrafts] = useState({});      // `${stage}:${mode}` -> edited text
  const [guides, setGuides] = useState({});      // stage -> { folder, guides } as saved on disk
  const [run, setRun] = useState({});
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const base = `${API}/api/sdlc/projects/${project.id}/agents/${stage}`;
  const draftKey = `${stage}:${mode}`;
  const saved = guides[stage]?.guides?.[mode];
  const text = drafts[draftKey] ?? saved?.content ?? '';
  const dirty = saved && text !== saved.content;

  useEffect(() => {
    setLoadError('');
    fetch(`${base}/run-guide`).then(readJsonOrThrow)
      .then(data => { setGuides(current => ({ ...current, [stage]: data })); })
      .catch(err => setLoadError(err.message));
  }, [stage]);

  useEffect(() => {
    let alive = true;
    const poll = () => fetch(`${base}/run`).then(readJsonOrThrow).then(d => { if (alive) setRun(d); }).catch(() => {});
    setRun({});
    poll();
    const timer = setInterval(poll, 2000);
    return () => { alive = false; clearInterval(timer); };
  }, [stage]);

  const save = async () => {
    await readJsonOrThrow(await fetch(`${base}/run-guide/${mode}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: text }),
    }));
    setGuides(current => {
      const entry = current[stage];
      return { ...current, [stage]: { ...entry, guides: { ...entry.guides, [mode]: { ...entry.guides[mode], exists: true, content: text } } } };
    });
  };
  const guarded = async (fn) => {
    setBusy(true);
    try { await fn(); } catch (err) { alert(`[M5 Run] ❌ ${err.message}`); } finally { setBusy(false); }
  };
  const saveOnly = () => guarded(save);
  const saveAndStart = () => guarded(async () => {
    await save();
    setRun(await readJsonOrThrow(await fetch(`${base}/run/start`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }),
    })));
  });
  const stop = () => guarded(async () => setRun(await readJsonOrThrow(await fetch(`${base}/run/stop`, { method: 'POST' }))));
  const setupCommand = (project.agents?.[stage]?.setup_command || '').trim();
  const install = () => guarded(async () => {
    setRun(await readJsonOrThrow(await fetch(`${base}/run/start`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'setup' }),
    })));
  });

  return (
    <ModalShell label="جزئیات" onClose={() => { onClose(); }}>
      <div className="sdlc-task-detail-modal" data-ui="M5">
        <div className="sdlc-form-header">
          <div>
            <h3>اجرای پروژه — {project.name} <UiTag id="M5" name="RunGuide" /></h3>
            <small style={{ fontSize: 11, color: '#899087' }}>راهنمای اجرا را ویرایش کنید؛ Claude Code آن را مرحله‌به‌مرحله اجرا می‌کند.</small>
          </div>
          <button type="button" className="sdlc-form-close" onClick={onClose}><X size={20} /></button>
        </div>
        <div className="sdlc-form-body">
          <div className="sdlc-agent-tabs">
            {stages.map(s => (
              <button key={s} className={`sdlc-agent-tab ${stage === s ? 'active' : ''}`} onClick={() => setStage(s)}>{s}</button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8, margin: '10px 0' }}>
            {[['test', 'Test — اجرای تست‌ها'], ['real', 'Real — اجرای واقعی']].map(([m, label]) => (
              <button key={m} className={`sdlc-btn ${mode === m ? 'sdlc-btn-primary' : 'sdlc-btn-secondary'}`} onClick={() => setMode(m)}>{label}</button>
            ))}
          </div>
          {loadError && <p className="sdlc-error">{loadError}</p>}
          {saved && (
            <>
              <small className="sdlc-intervention-hint" dir="ltr">
                {guides[stage].folder}\{saved.file} {saved.exists ? '' : '(هنوز ذخیره نشده — قالب اولیه)'}
              </small>
              <textarea
                dir="ltr" rows={14} value={text} spellCheck={false}
                style={{ width: '100%', fontFamily: 'monospace', fontSize: 12 }}
                onChange={e => setDrafts(current => ({ ...current, [draftKey]: e.target.value }))}
              />
            </>
          )}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '10px 0', flexWrap: 'wrap' }}>
            <button className="sdlc-btn sdlc-btn-secondary" disabled={busy || !dirty} onClick={saveOnly}>ذخیره</button>
            <button className="sdlc-btn sdlc-btn-secondary" disabled={busy || run.running || !setupCommand} onClick={install}
              title={setupCommand || 'در تنظیمات پروژه (Install Command) دستور نصب را وارد کنید'}>
              نصب{setupCommand ? `: ${setupCommand}` : ''}
            </button>
            {run.running ? (
              <button className="sdlc-btn sdlc-btn-secondary" disabled={busy} onClick={stop}><Square size={14} /> توقف</button>
            ) : (
              <button className="sdlc-btn sdlc-btn-primary" disabled={busy || !saved} onClick={saveAndStart}><Play size={14} /> ذخیره و اجرا</button>
            )}
            <span className={`sdlc-badge ${run.running ? 'green' : 'gray'}`}>
              {run.running
                ? (run.agent_running ? `agent در حال اجرا (${run.mode})` : `سرورها در حال اجرا (${(run.detached_pids || []).join(', ')})`)
                : run.exit_code != null ? `پایان (کد ${run.exit_code})` : 'متوقف'}
            </span>
          </div>
          {run.log !== undefined && run.log !== '' && (
            <pre className="sdlc-live-output" dir="ltr" style={{ maxHeight: 260, overflow: 'auto' }}>{run.log}</pre>
          )}
        </div>
      </div>
    </ModalShell>
  );
}

// M4-3C: ▶ / ■ buttons for the stages of a project that have a run command (dev servers etc.).
function ProjectRunControls({ project }) {
  const stages = Object.entries(project.agents || {}).filter(([, a]) => a.enabled && (a.run_command || '').trim());
  const [runs, setRuns] = useState({});   // stage -> status from the server
  const [busy, setBusy] = useState({});
  const [openLog, setOpenLog] = useState('');
  const stageKey = stages.map(([s]) => s).join(',');

  useEffect(() => {
    if (!stageKey) return undefined;
    let alive = true;
    const poll = async () => {
      for (const stage of stageKey.split(',')) {
        try {
          const data = await readJsonOrThrow(await fetch(`${API}/api/sdlc/projects/${project.id}/agents/${stage}/run`));
          if (alive) setRuns(current => ({ ...current, [stage]: data }));
        } catch { /* backend briefly unavailable */ }
      }
    };
    poll();
    const timer = setInterval(poll, 3000);
    return () => { alive = false; clearInterval(timer); };
  }, [project.id, stageKey]);

  if (stages.length === 0) return null;

  const act = async (stage, action) => {
    setBusy(current => ({ ...current, [stage]: true }));
    try {
      const data = await readJsonOrThrow(await fetch(`${API}/api/sdlc/projects/${project.id}/agents/${stage}/run/${action}`, { method: 'POST' }));
      setRuns(current => ({ ...current, [stage]: data }));
      if (action === 'start') setOpenLog(stage);
    } catch (err) {
      alert(`[M4-3C Run] ❌ ${err.message}`);
    } finally {
      setBusy(current => ({ ...current, [stage]: false }));
    }
  };

  return (
    <div className="sdlc-run-controls" data-ui="M4-3C">
      {stages.map(([stage, agent]) => {
        const run = runs[stage] || {};
        return (
          <div key={stage} className="sdlc-run-row" style={{ marginBottom: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {run.running ? (
                <button className="sdlc-btn sdlc-btn-secondary" disabled={busy[stage]} onClick={() => act(stage, 'stop')} title="توقف">
                  <Square size={14} /> {stage}
                </button>
              ) : (
                <button className="sdlc-btn sdlc-btn-primary" disabled={busy[stage]} onClick={() => act(stage, 'start')} title="اجرا">
                  <Play size={14} /> {stage}
                </button>
              )}
              <code dir="ltr" style={{ fontSize: 11, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{agent.run_command}</code>
              <span className={`sdlc-badge ${run.running ? 'green' : 'gray'}`}>
                {run.running ? 'در حال اجرا' : run.exit_code != null ? `پایان (${run.exit_code})` : 'متوقف'}
              </span>
              {run.log !== undefined && (
                <button className="sdlc-action-btn" onClick={() => setOpenLog(openLog === stage ? '' : stage)}>لاگ</button>
              )}
            </div>
            {openLog === stage && (
              <pre className="sdlc-live-output" dir="ltr" style={{ maxHeight: 180, overflow: 'auto' }}>{run.log || '(بدون خروجی)'}</pre>
            )}
          </div>
        );
      })}
    </div>
  );
}

// M4-3R: where one stage's code lives on GitHub and on disk (each stage can have its own repo).
function RepositorySettings({ project, stage, repository, onChange, canPrepare }) {
  const repo = { ...DEFAULT_REPOSITORY, ...(repository || {}) };
  const agent = project.agents?.[stage] || {};
  const defaultFolder = agent.project_path || `~/taskloom-workspaces/${project.id || '<project-id>'}/${stage}`;
  const defaultName = `${project.id || 'project'}-${stage}`;
  const prepare = () => {
    fetch(`${API}/api/sdlc/projects/${project.id}/agents/${stage}/repository/prepare`, { method: 'POST' })
      .then(readJsonOrThrow)
      .then(data => alert(`[A6 RepoPrepare] ✅ ریپوی ${stage} آماده است\n\nپوشه: ${data.path}\nبرنچ: ${data.branch}${data.url ? `\nGitHub: ${data.url}` : ''}`))
      .catch(err => alert(`[A6 RepoPrepare] ❌ ${err.message}`));
  };
  return (
    <div className="sdlc-repo-settings">
      <h4>ریپوی {stage} <UiTag id="M4-3R" name={`${stage} Repository`} /></h4>
      <div className="sdlc-repo-modes">
        {[
          ['none', 'بدون ریپو', 'این agent در پوشهٔ مسیر پروژه (project_path) کار می‌کند؛ چیزی ساخته یا clone نمی‌شود.'],
          ['create', 'ریپوی جدید', 'Taskloom یک ریپوی محلی می‌سازد و در اولین «Commit و Push» ریپوی private روی GitHub شما ایجاد می‌کند.'],
          ['existing', 'ریپوی موجود', 'یک بار clone می‌شود و قبل از هر تسک pull می‌شود؛ برنچ هر تسک از آخرین نسخهٔ origin ساخته می‌شود.'],
        ].map(([mode, label, help]) => (
          <label key={mode} className={`sdlc-repo-mode ${repo.mode === mode ? 'active' : ''}`}>
            <input type="radio" name={`repo-mode-${stage}`} checked={repo.mode === mode} onChange={() => onChange({ mode })} />
            <span><b>{label}</b><small>{help}</small></span>
          </label>
        ))}
      </div>
      {repo.mode !== 'none' && (
        <div className="sdlc-repo-fields">
          {repo.mode === 'existing' && (
            <div className="sdlc-form-group">
              <label>آدرس ریپو در GitHub</label>
              <input dir="ltr" value={repo.url} onChange={e => onChange({ url: e.target.value })} placeholder="https://github.com/owner/repo" />
            </div>
          )}
          {repo.mode === 'create' && (
            <>
              <div className="sdlc-form-group">
                <label>نام ریپو روی GitHub</label>
                <input dir="ltr" value={repo.name} onChange={e => onChange({ name: e.target.value })} placeholder={defaultName} />
                {repo.url && <small className="sdlc-intervention-hint">ساخته شده: <a href={repo.url} target="_blank" rel="noreferrer" dir="ltr">{repo.url}</a></small>}
              </div>
              <label className="sdlc-checkbox-label">
                <input type="checkbox" checked={repo.private} onChange={e => onChange({ private: e.target.checked })} /> ریپوی private
              </label>
            </>
          )}
          <div className="sdlc-form-group">
            <label>GitHub Token</label>
            <input
              type="password" dir="ltr" autoComplete="off" value={repo.github_token}
              onChange={e => onChange({ github_token: e.target.value })}
              placeholder={repo.token_saved ? 'ذخیره شده — برای تعویض، توکن جدید وارد کنید' : 'ghp_... یا github_pat_...'}
            />
            <small className="sdlc-intervention-hint">
              رمزنگاری‌شده جدا از فایل پروژه ذخیره می‌شود. دسترسی لازم: توکن classic با scope <code dir="ltr">repo</code>، یا fine-grained با
              Contents و Pull requests (Read/Write){repo.mode === 'create' ? ' و Administration (Read/Write) برای ساخت ریپو' : ''}.
            </small>
            {repo.token_saved && (
              <label className="sdlc-checkbox-label">
                <input type="checkbox" checked={!!repo.clear_token} onChange={e => onChange({ clear_token: e.target.checked })} /> حذف توکن ذخیره‌شده
              </label>
            )}
          </div>
          <div className="sdlc-form-group">
            <label>پوشهٔ محلی ریپو</label>
            <input dir="ltr" value={repo.local_path} onChange={e => onChange({ local_path: e.target.value })} placeholder={defaultFolder} />
          </div>
          <div className="sdlc-form-group">
            <label>برنچ پایه</label>
            <input dir="ltr" value={repo.default_branch} onChange={e => onChange({ default_branch: e.target.value })} placeholder="main" />
          </div>
          {canPrepare && (
            <button type="button" className="sdlc-btn sdlc-btn-secondary" onClick={prepare}>
              آماده‌سازی ریپوی {stage} اکنون ({repo.mode === 'existing' ? 'clone / بررسی' : 'ساخت ریپوی محلی'})
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// Top of M3-F: one-click validate / publish / PR for every stage that has its own repository.
function StageRepoActions({ task, project, onDone }) {
  const stages = Object.entries(project?.agents || {}).filter(([, agent]) => agent.repository && agent.repository.mode !== 'none');
  if (!stages.length) return null;
  const call = (stage, action, label, show) => {
    fetch(`${API}/api/sdlc/tasks/${task.base_task.task_id}/github/${action}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ agent: stage }),
    })
      .then(readJsonOrThrow)
      .then(data => { alert(`[${label} · ${stage}] ${show(data)}`); onDone && onDone(); })
      .catch(err => alert(`[${label} · ${stage}] ❌ ${err.message}`));
  };
  return (
    <div className="sdlc-stage-repos">
      {stages.map(([stage, agent]) => (
        <div key={stage} className="sdlc-project-repo-actions">
          <div className="sdlc-stage-repo-head">
            <strong>{stage}</strong>
            <span dir="ltr" className="sdlc-project-repo-target">
              {agent.repository.url
                ? <a href={agent.repository.url} target="_blank" rel="noreferrer">{agent.repository.url}</a>
                : <>new repo, created on the first push{agent.repository.private ? ' (private)' : ''}</>}
            </span>
          </div>
          <div className="sdlc-project-repo-buttons">
            <button type="button" className="sdlc-btn sdlc-btn-secondary" onClick={() => call(stage, 'validate', 'A3 GitHubValidate', d => d.status === 'valid'
              ? `✅ دسترسی تأیید شد: ${d.owner}/${d.repo}${d.will_create ? ' (در اولین push ساخته می‌شود)' : ''}`
              : `❌ ${d.message}`)}>بررسی دسترسی</button>
            <button type="button" className="sdlc-btn sdlc-btn-secondary" onClick={() => call(stage, 'commit-push', 'A4 CommitPush', d => `✅ ${d.message}\n\nCommit: ${d.commit_sha}\nBranch: ${d.branch}\nRepo: ${d.repository_url}`)}>Commit و Push</button>
            <button type="button" className="sdlc-btn sdlc-btn-primary" onClick={() => call(stage, 'create-pr', 'A5 PullRequest', d => `✅ ${d.message}\n\nPR #${d.pr_number}\nURL: ${d.pr_url}`)}>Pull Request</button>
          </div>
        </div>
      ))}
    </div>
  );
}
