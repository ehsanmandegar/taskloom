import React from 'react';
import { BarChart3, Clock, CheckCircle, XCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { useTranslation } from './translation_context';

/**
 * SDLC Stats Summary Component
 * Shows aggregate statistics at the top of the dashboard
 */
export default function SDLCStatsSummary({ tasks }) {
  const { t } = useTranslation();
  
  const stats = {
    total: tasks.length,
    running: tasks.filter(t => ['analyzing', 'backend_running', 'n8n_running', 'frontend_running', 'testing'].includes(t.sdlc_status)).length,
    needsApproval: tasks.filter(t => ['human_review', 'human_qa', 'pending_approval'].includes(t.sdlc_status)).length,
    done: tasks.filter(t => t.sdlc_status === 'done').length,
    failed: tasks.filter(t => t.sdlc_status === 'failed').length,
    revisions: tasks.filter(t => t.sdlc_status === 'revision').length
  };

  return (
    <div className="sdlc-stats-summary">
      <div className="stat-card">
        <div className="stat-icon" style={{background: 'var(--blue-3)', color: 'var(--blue-11)'}}>
          <BarChart3 size={20} />
        </div>
        <div className="stat-content">
          <span className="stat-label">{t('total_tasks')}</span>
          <span className="stat-value">{stats.total.toLocaleString('fa-IR')}</span>
        </div>
      </div>
      
      <div className="stat-card">
        <div className="stat-icon" style={{background: 'var(--orange-3)', color: 'var(--orange-11)'}}>
          <Clock size={20} />
        </div>
        <div className="stat-content">
          <span className="stat-label">{t('running')}</span>
          <span className="stat-value">{stats.running.toLocaleString('fa-IR')}</span>
        </div>
      </div>
      
      <div className="stat-card">
        <div className="stat-icon" style={{background: 'var(--yellow-3)', color: 'var(--yellow-11)'}}>
          <AlertCircle size={20} />
        </div>
        <div className="stat-content">
          <span className="stat-label">{t('needs_approval')}</span>
          <span className="stat-value">{stats.needsApproval.toLocaleString('fa-IR')}</span>
        </div>
      </div>
      
      <div className="stat-card">
        <div className="stat-icon" style={{background: 'var(--green-3)', color: 'var(--green-11)'}}>
          <CheckCircle size={20} />
        </div>
        <div className="stat-content">
          <span className="stat-label">{t('completed')}</span>
          <span className="stat-value">{stats.done.toLocaleString('fa-IR')}</span>
        </div>
      </div>
      
      <div className="stat-card">
        <div className="stat-icon" style={{background: 'var(--red-3)', color: 'var(--red-11)'}}>
          <XCircle size={20} />
        </div>
        <div className="stat-content">
          <span className="stat-label">{t('failed_count')}</span>
          <span className="stat-value">{stats.failed.toLocaleString('fa-IR')}</span>
        </div>
      </div>
      
      <div className="stat-card">
        <div className="stat-icon" style={{background: 'var(--purple-3)', color: 'var(--purple-11)'}}>
          <RefreshCw size={20} />
        </div>
        <div className="stat-content">
          <span className="stat-label">{t('revisions_count')}</span>
          <span className="stat-value">{stats.revisions.toLocaleString('fa-IR')}</span>
        </div>
      </div>
    </div>
  );
}
