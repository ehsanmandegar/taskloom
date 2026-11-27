/**
 * Team Workflow Extension - Persian/English Localization System
 * 
 * Localization strategy:
 * - Centralized translation catalog
 * - Simple t(key) mechanism
 * - Persistent language preference (localStorage)
 * - RTL/LTR support via Radix DirectionProvider
 */

// Translation catalog - English
const en: Record<string, string> = {
  // UI Labels
  "taskloom": "Taskloom",
  "dashboard": "Dashboard",
  "projects": "Projects",
  "tasks": "Tasks",
  "releases": "Releases",
  "settings": "Settings",
  "humanInbox": "Human Inbox",
  "metrics": "Metrics",
  "overview": "Overview",
  "create_task": "Create Task",
  "roles": "Roles",
  "release_management": "Release Management",
  "sdlc_platform": "SDLC Platform",
  
  // Theme
  "light": "Light",
  "dark": "Dark",
  "enable_light_theme": "Enable light theme",
  "enable_dark_theme": "Enable dark theme",
  "theme_green": "Green theme",
  "theme_blue": "Blue theme",
  "theme_orange": "Orange theme",
  "theme_red": "Red theme",
  "theme_purple": "Purple theme",
  
  // Menu
  "main_menu": "Main Menu",
  "management_dashboard": "Management Dashboard",
  "open_menu": "Open menu",
  "close_menu": "Close menu",
  "dashboard_sections": "Dashboard sections",
  
  // SDLC Dashboard
  "sdlc_complete_cycle": "Complete Software Development Lifecycle Management",
  "create_new_task": "Create New Task",
  "update": "Update",
  "total_tasks": "Total Tasks",
  "running": "Running",
  "needs_approval": "Needs Approval",
  "approval_completed": "Completed",
  "failed_count": "Failed",
  "revisions_count": "Revisions",
  "pipeline_view": "Pipeline",
  "all_tasks": "All Tasks",
  "human_requests": "Human Requests",
  "projects_view": "Projects",
  "metrics_automation": "Metrics & Automation",
  "search_tasks": "Search tasks...",
  "all_projects": "All Projects",
  "all_statuses": "All Statuses",
  "sdlc_pipeline": "SDLC Pipeline",
  "tasks_by_stage": "Tasks by current stage",
  "no_tasks_in_stage": "No tasks in this stage",
  "show_one_task": "Show only one task",
  "previous": "Previous",
  "next": "Next",
  
  // SDLC Stages
  "stage_created": "Created",
  "stage_analyzing": "Analyzing",
  "stage_human_review": "Human Review",
  "stage_analysis_approved": "Analysis Approved",
  "stage_backend_running": "Backend Development",
  "stage_n8n_running": "n8n Development",
  "stage_frontend_running": "Frontend Development",
  "stage_testing": "Testing",
  "stage_human_qa": "QA Review",
  "stage_revision": "Revision",
  "stage_pending_approval": "Pending Final Approval",
  "stage_done": "Done",
  "stage_failed": "Failed",
  "stage_blocked": "Blocked",
  
  // Agent types
  "agent_analyst": "Analyst",
  "agent_backend_developer": "Backend Developer",
  "agent_n8n_engineer": "n8n Engineer",
  "agent_frontend_developer": "Frontend Developer",
  "agent_qa_tester": "QA Tester",
  
  // Status labels
  "created": "Created",
  "analyzing": "Analyzing",
  "human_review": "Human Review",
  "analysis_approved": "Analysis Approved",
  "backend_running": "Backend Development",
  "backend_review": "Backend Review",
  "frontend_running": "Frontend Development",
  "frontend_review": "Frontend Review",
  "qa_running": "QA Testing",
  "qa_review": "QA Review",
  "analyst_final_review": "Analyst Final Review",
  "po_pending_approval": "PO Approval",
  "pending_approval": "Pending Approval",
  "revision": "Revision",
  "release_ready": "Release Ready",
  "done": "Done",
  "failed": "Failed",
  "blocked": "Blocked",
  
  // Workflow gates
  "backendHandoff": "Backend Handoff",
  "frontendHandoff": "Frontend Handoff",
  "qaReport": "QA Report",
  "poDecision": "PO Decision",
  "analystFinalSummary": "Analyst Final Summary",
  
  // Action buttons
  "approve": "Approve",
  "requestChanges": "Request Changes",
  "reject": "Reject",
  "submit": "Submit",
  "cancel": "Cancel",
  "save": "Save",
  "delete": "Delete",
  "edit": "Edit",
  "close": "Close",
  "refresh": "Refresh",
  "create": "Create",
  "start": "Start",
  "retry": "Retry",
  "build": "Build",
  
  // Status messages
  "loading": "Loading...",
  "error": "Error",
  "success": "Success",
  "warning": "Warning",
  "info": "Info",
  
  // Form labels
  "title": "Title",
  "description": "Description",
  "priority": "Priority",
  "priority_high": "High",
  "priority_medium": "Medium",
  "priority_low": "Low",
  "task_id": "Task ID",
  "session_name": "Session Name",
  "base_branch": "Base Branch",
  "request": "Request",
  "project_path": "Project Path",
  "guide_paths": "Guide Paths",
  "test_command": "Test Command",
  "test_working_directory": "Test Working Directory",
  
  // Review statuses
  "pending": "Pending",
  "reviewing": "Reviewing",
  "approved": "Approved",
  "needs_revision": "Needs Revision",
  
  // PO Decision options
  "po_approve": "Approve Release",
  "po_changes_requested": "Request Changes",
  "po_reject": "Reject",
  
  // QA Report
  "qa_recommendation_pass": "Pass",
  "qa_recommendation_fail": "Fail",
  "qa_recommendation_blocked": "Blocked",
  "test_strategy": "Test Strategy",
  "test_cases": "Test Cases",
  "coverage_gaps": "Coverage Gaps",
  "residual_risks": "Residual Risks",
  
  // Timeline events
  "timeline_created": "Task Created",
  "timeline_stage_started": "Stage Started",
  "timeline_stage_completed": "Stage Completed",
  "timeline_stage_failed": "Stage Failed",
  "timeline_approved": "Approved",
  "timeline_merged": "Merged",
  "timeline_revision_requested": "Revision Requested",
  "timeline_po_decision_made": "PO Decision Made",
  
  // Navigation
  "pipeline": "Pipeline",
  "details": "Details",
  "timeline": "Timeline",
  "git": "Git",
  "release": "Release",
  
  // Pipeline view
  "all_stages": "All Stages",
  "active": "Active",
  "pending_human": "Pending Human",
  "completed": "Completed",
  "failed_tasks": "Failed Tasks",
  "revisions": "Revisions",
  
  // Task details
  "workflow_status": "Workflow Status",
  "current_stage": "Current Stage",
  "current_review_stage": "Current Review Stage",
  "execution_attempt": "Execution Attempt",
  "revision_count": "Revision Count",
  "created_at": "Created At",
  "updated_at": "Updated At",
  
  // Human inbox
  "pending_interventions": "Pending Interventions",
  "human_intervention": "Human Intervention",
  "intervention_id": "Intervention ID",
  "intervention_requesting_agent": "Requesting Agent",
  "intervention_reason": "Reason",
  "intervention_description": "Description",
  "intervention_response": "Response",
  "intervention_respond": "Respond",
  "approve_with_feedback": "Approve with Feedback",
  
  // Project form
  "new_project": "New Project",
  "project_id": "Project ID",
  "project_name": "Project Name",
  "project_description": "Project Description",
  "enabled": "Enabled",
  "sdlc_enabled": "SDLC Enabled",
  "workflow_stages": "Workflow Stages",
  "add_stage": "Add Stage",
  "remove_stage": "Remove Stage",
  "require_analysis_approval": "Require Analysis Approval",
  "require_final_human_approval": "Require Final Human Approval",
  "require_po_approval": "Require PO Approval",
  
  // Agent configuration
  "agent_configuration": "Agent Configuration",
  "knowledge_path": "Knowledge Path",
  "agent_project_path": "Project Path",
  "system_prompt": "System Prompt",
  "test_instructions": "Test Instructions",
  "timeout_seconds": "Timeout Seconds",
  "max_retries": "Max Retries",
  
  // AI Settings
  "ai_settings": "AI Settings",
  "provider": "Provider",
  "model": "Model",
  "default_provider": "Default Provider",
  "default_model": "Default Model",
  "ollama_endpoint": "Ollama Endpoint",
  
  // Release management
  "new_release": "New Release",
  "release_version": "Release Version",
  "repository": "Repository",
  "selected_tasks": "Selected Tasks",
  "release_status": "Release Status",
  "created_by": "Created By",
  "approved_by": "Approved By",
  "release_branch": "Release Branch",
  "target_branch": "Target Branch",
  
  // Language selector
  "language": "Language",
  "persian": "فارسی",
  "english": "English",
  "rtl": "RTL",
  "ltr": "LTR",
  
  // Validation messages
  "required_field": "This field is required",
  "invalid_input": "Invalid input",
  "field_too_long": "Field is too long",
  
  // Notifications
  "task_created": "Task created successfully",
  "task_updated": "Task updated successfully",
  "task_deleted": "Task deleted successfully",
  "release_created": "Release created successfully",
  "release_approved": "Release approved successfully",
  "po_approved": "Task approved for release",
  "changes_requested": "Changes requested",
  "task_rejected": "Task rejected",
  
  // Empty states
  "no_tasks": "No tasks found",
  "no_projects": "No projects found",
  "no_releases": "No releases found",
  "no_interventions": "No pending interventions",
  
  // Confirmation dialogs
  "confirm_delete": "Are you sure you want to delete?",
  "confirm_approve": "Are you sure you want to approve?",
  "confirm_release": "Are you sure you want to create this release?",
};

// Translation catalog - Persian
const fa: Record<string, string> = {
  // UI Labels
  "taskloom": "تسک‌لوم",
  "dashboard": "داشبورد",
  "projects": "پروژه‌ها",
  "tasks": "تسک‌ها",
  "releases": "نسخه‌ها",
  "settings": "تنظیمات",
  "humanInbox": "صندوق ورودی انسانی",
  "metrics": "معیارها",
  "overview": "نمای کلی",
  "create_task": "ایجاد تسک",
  "roles": "نقش‌ها",
  "release_management": "مدیریت نسخه",
  "sdlc_platform": "پلتفرم SDLC",
  
  // Theme
  "light": "روشن",
  "dark": "تاریک",
  "enable_light_theme": "فعال‌کردن تم روشن",
  "enable_dark_theme": "فعال‌کردن تم تاریک",
  "theme_green": "تم سبز",
  "theme_blue": "تم آبی",
  "theme_orange": "تم نارنجی",
  "theme_red": "تم قرمز",
  "theme_purple": "تم بنفش",
  
  // Menu
  "main_menu": "منوی اصلی",
  "management_dashboard": "داشبورد مدیریت",
  "open_menu": "باز کردن منو",
  "close_menu": "بستن منو",
  "dashboard_sections": "بخش‌های داشبورد",
  
  // SDLC Dashboard
  "sdlc_complete_cycle": "مدیریت چرخه کامل توسعه نرم‌افزار",
  "create_new_task": "ایجاد تسک جدید",
  "update": "به‌روزرسانی",
  "total_tasks": "کل تسک‌ها",
  "running": "در حال اجرا",
  "needs_approval": "نیازمند تأیید",
  "approval_completed": "انجام شده",
  "failed_count": "ناموفق",
  "revisions_count": "بازبینی‌ها",
  "pipeline_view": "خط تولید",
  "all_tasks": "همه تسک‌ها",
  "human_requests": "درخواست‌های انسانی",
  "projects_view": "پروژه‌ها",
  "metrics_automation": "آمار و خودکارسازی",
  "search_tasks": "جست‌وجو در تسک‌ها...",
  "all_projects": "همه پروژه‌ها",
  "all_statuses": "همه وضعیت‌ها",
  "sdlc_pipeline": "خط تولید SDLC",
  "tasks_by_stage": "تسک‌ها بر اساس مرحله جاری",
  "no_tasks_in_stage": "هیچ تسکی در این مرحله نیست",
  "show_one_task": "فقط یک تسک نشون بده",
  "previous": "قبلی",
  "next": "بعدی",
  
  // SDLC Stages
  "stage_created": "ایجاد شده",
  "stage_analyzing": "در حال تحلیل",
  "stage_human_review": "بازبینی انسانی",
  "stage_analysis_approved": "تأیید تحلیل",
  "stage_backend_running": "توسعه بک‌اند",
  "stage_n8n_running": "توسعه n8n",
  "stage_frontend_running": "توسعه فرانت‌اند",
  "stage_testing": "آزمون",
  "stage_human_qa": "تأیید کیفیت",
  "stage_revision": "بازبینی",
  "stage_pending_approval": "منتظر تأیید نهایی",
  "stage_done": "انجام شده",
  "stage_failed": "ناموفق",
  "stage_blocked": "مسدود شده",
  
  // Agent types
  "agent_analyst": "تحلیلگر",
  "agent_backend_developer": "توسعه‌دهنده بک‌اند",
  "agent_n8n_engineer": "مهندس n8n",
  "agent_frontend_developer": "توسعه‌دهنده فرانت‌اند",
  "agent_qa_tester": "آزمونگر",
  
  // Status labels
  "created": "ایجاد شده",
  "analyzing": "در حال تحلیل",
  "human_review": "بازبینی انسانی",
  "analysis_approved": "تأیید تحلیل",
  "backend_running": "توسعه بک‌اند",
  "backend_review": "بازبینی بک‌اند",
  "frontend_running": "توسعه فرانت‌اند",
  "frontend_review": "بازبینی فرانت‌اند",
  "qa_running": "آزمون QA",
  "qa_review": "بازبینی QA",
  "analyst_final_review": "بازبینی نهایی تحلیلگر",
  "po_pending_approval": "تأیید PO",
  "pending_approval": "منتظر تأیید نهایی",
  "revision": "بازبینی",
  "release_ready": "آماده انتشار",
  "done": "انجام شده",
  "failed": "ناموفق",
  "blocked": "مسدود شده",
  
  // Workflow gates
  "backendHandoff": "اتصال بک‌اند",
  "frontendHandoff": "اتصال فرانت‌اند",
  "qaReport": "گزارش QA",
  "poDecision": "تصمیم PO",
  "analystFinalSummary": "خلاصه نهایی تحلیلگر",
  
  // Action buttons
  "approve": "تأیید",
  "requestChanges": "درخواست تغییرات",
  "reject": "رد",
  "submit": "ثبت",
  "cancel": "لغو",
  "save": "ذخیره",
  "delete": "حذف",
  "edit": "ویرایش",
  "close": "بستن",
  "refresh": "به‌روزرسانی",
  "create": "ساخت",
  "start": "شروع",
  "retry": "تلاش مجدد",
  "build": "ساخت",
  
  // Status messages
  "loading": "در حال بارگذاری...",
  "error": "خطا",
  "success": "موفقیت",
  "warning": "هشدار",
  "info": "اطلاعات",
  
  // Form labels
  "title": "عنوان",
  "description": "توضیحات",
  "priority": "اولویت",
  "priority_high": "بالا",
  "priority_medium": "متوسط",
  "priority_low": "پایین",
  "task_id": "شناسه تسک",
  "session_name": "نام سشن",
  "base_branch": "برنچ مبنا",
  "request": "درخواست",
  "project_path": "مسیر پروژه",
  "guide_paths": "مسیرهای راهنما",
  "test_command": "دستور تست",
  "test_working_directory": "شاخه کاری تست",
  
  // Review statuses
  "pending": "در انتظار",
  "reviewing": "در حال بازبینی",
  "approved": "تأیید شده",
  "needs_revision": "نیاز به بازبینی",
  
  // PO Decision options
  "po_approve": "تأیید انتشار",
  "po_changes_requested": "درخواست تغییرات",
  "po_reject": "رد",
  
  // QA Report
  "qa_recommendation_pass": "پاس",
  "qa_recommendation_fail": "شکست",
  "qa_recommendation_blocked": "مسدود",
  "test_strategy": "استراتژی تست",
  "test_cases": "موارد تست",
  "coverage_gaps": "فواصل پوشش",
  "residual_risks": "ریسک‌های باقی‌مانده",
  
  // Timeline events
  "timeline_created": "تسک ایجاد شد",
  "timeline_stage_started": "مرحله شروع شد",
  "timeline_stage_completed": "مرحله انجام شد",
  "timeline_stage_failed": "مرحله ناموفق بود",
  "timeline_approved": "تأیید شد",
  "timeline_merged": "ادغام شد",
  "timeline_revision_requested": "بازبینی درخواست شد",
  "timeline_po_decision_made": "تصمیم PO گرفته شد",
  
  // Navigation
  "pipeline": "خط لوله",
  "details": "جزئیات",
  "timeline": "تاریخچه",
  "git": "گیت",
  "release": "نسخه",
  
  // Pipeline view
  "all_stages": "همه مراحل",
  "active": "فعال",
  "pending_human": "منتظر انسان",
  "completed": "انجام شده",
  "failed_tasks": "تسک‌های ناموفق",
  "revisions": "بازبینی‌ها",
  
  // Task details
  "workflow_status": "وضعیت گردش کار",
  "current_stage": "مرحله فعلی",
  "current_review_stage": "مرحله بازبینی فعلی",
  "execution_attempt": "تلاش اجرا",
  "revision_count": "تعداد بازبینی",
  "created_at": "تاریخ ایجاد",
  "updated_at": "تاریخ به‌روزرسانی",
  
  // Human inbox
  "pending_interventions": "مداخلات در انتظار",
  "human_intervention": "مداخله انسانی",
  "intervention_id": "شناسه مداخله",
  "intervention_requesting_agent": "عامل درخواست‌کننده",
  "intervention_reason": "دلیل",
  "intervention_description": "توضیحات",
  "intervention_response": "پاسخ",
  "intervention_respond": "پاسخ",
  "approve_with_feedback": "تأیید با بازخورد",
  
  // Project form
  "new_project": "پروژه جدید",
  "project_id": "شناسه پروژه",
  "project_name": "نام پروژه",
  "project_description": "توضیحات پروژه",
  "enabled": "فعال",
  "sdlc_enabled": "SDLC فعال",
  "workflow_stages": "مراحل گردش کار",
  "add_stage": "اضافه کردن مرحله",
  "remove_stage": "حذف مرحله",
  "require_analysis_approval": "نیاز به تأیید تحلیل",
  "require_final_human_approval": "نیاز به تأیید نهایی انسانی",
  "require_po_approval": "نیاز به تأیید PO",
  
  // Agent configuration
  "agent_configuration": "پیکربندی عامل",
  "knowledge_path": "مسیر دانش",
  "agent_project_path": "مسیر پروژه",
  "system_prompt": "پرامپت سیستم",
  "test_instructions": "دستورالعمل تست",
  "timeout_seconds": "زمان تایم‌اوت ثانیه",
  "max_retries": "حداکثر تلاش مجدد",
  
  // AI Settings
  "ai_settings": "تنظیمات هوش مصنوعی",
  "provider": "ارائه‌دهنده",
  "model": "مدل",
  "default_provider": "ارائه‌دهنده پیش‌فرض",
  "default_model": "مدل پیش‌فرض",
  "ollama_endpoint": "endpoint Ollama",
  
  // Release management
  "new_release": "نسخه جدید",
  "release_version": "نسخه انتشار",
  "repository": "مخزن",
  "selected_tasks": "تسک‌های انتخاب‌شده",
  "release_status": "وضعیت نسخه",
  "created_by": "ایجاد شده توسط",
  "approved_by": "تأیید شده توسط",
  "release_branch": "برنچ نسخه",
  "target_branch": "برنچ هدف",
  
  // Language selector
  "language": "زبان",
  "persian": "فارسی",
  "english": "English",
  "rtl": "راست‌چین",
  "ltr": "چپ‌چین",
  
  // Validation messages
  "required_field": "این فیلد الزامی است",
  "invalid_input": "ورودی نامعتبر",
  "field_too_long": "فیلد خیلی طولانی است",
  
  // Notifications
  "task_created": "تسک با موفقیت ایجاد شد",
  "task_updated": "تسک با موفقیت به‌روزرسانی شد",
  "task_deleted": "تسک با موفقیت حذف شد",
  "release_created": "نسخه با موفقیت ایجاد شد",
  "release_approved": "نسخه با موفقیت تأیید شد",
  "po_approved": "تسک برای انتشار تأیید شد",
  "changes_requested": "تغییرات درخواست شد",
  "task_rejected": "تسک رد شد",
  
  // Empty states
  "no_tasks": "هیچ تسکی پیدا نشد",
  "no_projects": "هیچ پروژه‌ای پیدا نشد",
  "no_releases": "هیچ نسخه‌ای پیدا نشد",
  "no_interventions": "هیچ مداخله‌ای در انتظار نیست",
  
  // Confirmation dialogs
  "confirm_delete": "آیا مطمئن هستید که می‌خواهید حذف کنید؟",
  "confirm_approve": "آیا مطمئن هستید که می‌خواهید تأیید کنید؟",
  "confirm_release": "آیا مطمئن هستید که می‌خواهید این نسخه را ایجاد کنید؟",
};

// Current language
let currentLanguage: "en" | "fa" = "en";

// Initialize language from localStorage or browser preference
export function initializeLanguage(): "en" | "fa" {
  const savedLanguage = localStorage.getItem("taskloom.language");
  if (savedLanguage && ["en", "fa"].includes(savedLanguage)) {
    currentLanguage = savedLanguage as "en" | "fa";
    return currentLanguage;
  }
  
  // Check browser language
  const browserLanguage = navigator.language.toLowerCase();
  if (browserLanguage.startsWith("fa") || browserLanguage.startsWith("ir")) {
    currentLanguage = "fa";
    localStorage.setItem("taskloom.language", "fa");
    return "fa";
  }
  
  return "en";
}

// Get current language
export function getLanguage(): "en" | "fa" {
  return currentLanguage;
}

// Set language
export function setLanguage(lang: "en" | "fa"): void {
  currentLanguage = lang;
  localStorage.setItem("taskloom.language", lang);
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "fa" ? "rtl" : "ltr";
  
  // Update direction provider
  const dirProvider = document.querySelector("[data-radix-ui-direction]");
  if (dirProvider) {
    (dirProvider as HTMLElement).setAttribute("dir", lang === "fa" ? "rtl" : "ltr");
  }
}

// Get direction based on language
export function getDirection(lang: "en" | "fa" = currentLanguage): "rtl" | "ltr" {
  return lang === "fa" ? "rtl" : "ltr";
}

// Translate function
export function t(key: string, lang: "en" | "fa" = currentLanguage): string {
  const translations = lang === "fa" ? fa : en;
  return translations[key] || key;
}

// Format date in Persian or English
export function formatDate(date: Date, lang: "en" | "fa" = currentLanguage): string {
  if (lang === "fa") {
    return new Intl.DateTimeFormat("fa-IR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(date);
  }
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

// Format number with locale-specific separators
export function formatNumber(num: number, lang: "en" | "fa" = currentLanguage): string {
  const locale = lang === "fa" ? "fa-IR" : "en-US";
  return num.toLocaleString(locale);
}

// Get available languages
export function getAvailableLanguages(): { code: "en" | "fa"; name: string }[] {
  return [
    { code: "en", name: t("english", "en") },
    { code: "fa", name: t("persian", "fa") },
  ];
}