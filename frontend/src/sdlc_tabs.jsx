import React from 'react';
import { BarChart3, ClipboardList, Users, Gauge } from 'lucide-react';
import { useTranslation } from './translation_context';

/**
 * SDLC Dashboard Tabs Component
 */
export default function SDLCTabs({ activeTab, onTabChange, pendingCount = 0 }) {
  const { t } = useTranslation();
  
  const tabs = [
    { id: 'pipeline', label: t('pipeline_view'), icon: BarChart3 },
    { id: 'tasks', label: t('all_tasks'), icon: ClipboardList },
    { id: 'inbox', label: t('human_requests'), icon: Users, badge: pendingCount },
    { id: 'projects', label: t('projects_view'), icon: ClipboardList },
    { id: 'metrics', label: t('metrics_automation'), icon: Gauge }
  ];

  return (
    <div className="sdlc-tabs">
      {tabs.map(tab => {
        const TabIcon = tab.icon;
        return (
          <button
            key={tab.id}
            type="button"
            className={`sdlc-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => onTabChange(tab.id)}
          >
            <TabIcon size={16} />
            <span>{tab.label}</span>
            {tab.badge > 0 && (
              <span className="sdlc-tab-badge">{tab.badge}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
