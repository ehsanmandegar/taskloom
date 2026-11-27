import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useTranslation } from './translation_context';

/**
 * SDLC Pipeline View Component
 * Shows tasks organized by their current stage
 */
export default function SDLCPipelineView({ 
  tasks, 
  sdlcStages, 
  agentTypes,
  stageCursor,
  onStageCursorChange,
  onTaskClick 
}) {
  const { t, direction } = useTranslation();
  
  // Group tasks by stage
  const tasksByStage = {};
  sdlcStages.forEach(stage => {
    tasksByStage[stage.id] = tasks.filter(task => task.sdlc_status === stage.id);
  });

  function navigateStage(stageId, delta) {
    const stageTasks = tasksByStage[stageId];
    if (!stageTasks.length) return;
    
    const currentIndex = stageTasks.findIndex(t => t.id === stageCursor[stageId]);
    const nextIndex = currentIndex === -1 ? 0 : (currentIndex + delta + stageTasks.length) % stageTasks.length;
    
    onStageCursorChange({ ...stageCursor, [stageId]: stageTasks[nextIndex].id });
  }

  return (
    <div className="sdlc-pipeline">
      <div className="sdlc-pipeline-header">
        <h2>{t('sdlc_pipeline')}</h2>
        <p>{t('tasks_by_stage')}</p>
      </div>
      
      <div className="sdlc-pipeline-stages">
        {sdlcStages.map(stage => {
          const stageTasks = tasksByStage[stage.id];
          const visibleTask = stageTasks.find(t => t.id === stageCursor[stage.id]) || stageTasks[0];
          const taskIndex = visibleTask ? stageTasks.indexOf(visibleTask) : -1;
          const StageIcon = stage.icon;

          return (
            <div key={stage.id} className="pipeline-stage">
              <div className="pipeline-stage-header">
                <div className="pipeline-stage-icon" style={{background: `var(--${stage.color.replace('bg-', '')})`}}>
                  <StageIcon size={16} />
                </div>
                <div className="pipeline-stage-title">
                  <h3>{stage.label}</h3>
                  <span className="pipeline-stage-count">{stageTasks.length.toLocaleString('fa-IR')}</span>
                </div>
              </div>
              
              <div className="pipeline-stage-content">
                {stageTasks.length === 0 ? (
                  <div className="pipeline-stage-empty">
                    {t('no_tasks_in_stage')}
                  </div>
                ) : (
                  <>
                    <div 
                      className="pipeline-task-card"
                      onClick={() => visibleTask && onTaskClick(visibleTask.id)}
                    >
                      <div className="pipeline-task-id">{visibleTask.base_task.task_id}</div>
                      <div className="pipeline-task-title">{visibleTask.title}</div>
                      {visibleTask.current_agent && (
                        <div 
                          className={`pipeline-task-agent ${agentTypes[visibleTask.current_agent]?.color || 'bg-gray-500'}`}
                        >
                          {agentTypes[visibleTask.current_agent]?.label || visibleTask.current_agent}
                        </div>
                      )}
                      <div className="pipeline-task-time">
                        {new Date(visibleTask.created_at).toLocaleString('fa-IR', {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                    </div>
                    
                    {stageTasks.length > 1 && (
                      <div className="pipeline-task-nav">
                        <button
                          type="button"
                          onClick={() => navigateStage(stage.id, -1)}
                          className="pipeline-nav-btn"
                          aria-label={t('previous')}
                        >
                          {direction === 'rtl' ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
                        </button>
                        <span className="pipeline-nav-indicator">
                          {(taskIndex + 1).toLocaleString('fa-IR')} / {stageTasks.length.toLocaleString('fa-IR')}
                        </span>
                        <button
                          type="button"
                          onClick={() => navigateStage(stage.id, 1)}
                          className="pipeline-nav-btn"
                          aria-label={t('next')}
                        >
                          {direction === 'rtl' ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
