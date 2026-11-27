import React, { useState, useEffect } from 'react';
import { RefreshCw, CheckCircle, XCircle, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || '';

/**
 * AI Provider Configuration Component
 * 
 * This component provides UI for configuring AI providers and models
 * for a project at both project-level and stage-level.
 */
export default function AIProviderConfig({ projectId, aiSettings, onSettingsChange }) {
  const [providers, setProviders] = useState([]);
  const [providerModels, setProviderModels] = useState({});
  const [loading, setLoading] = useState(false);
  const [activeProviderTab, setActiveProviderTab] = useState('project');
  const [expandedStages, setExpandedStages] = useState({});

  // Load available providers
  useEffect(() => {
    loadProviders();
  }, []);

  // Load models when provider changes
  useEffect(() => {
    if (aiSettings.default_provider) {
      loadProviderModels(aiSettings.default_provider);
    }
  }, [aiSettings.default_provider]);

  async function loadProviders() {
    try {
      const response = await fetch(`${API}/api/ai/providers`);
      if (!response.ok) throw new Error('خطا در بارگذاری ارائه‌دهندگان');
      const data = await response.json();
      setProviders(data);
    } catch (err) {
      console.error('Error loading providers:', err);
    }
  }

  async function loadProviderModels(providerId) {
    try {
      const response = await fetch(`${API}/api/ai/providers/${providerId}/models`);
      if (!response.ok) {
        // If endpoint not available, use empty list
        setProviderModels(prev => ({ ...prev, [providerId]: [] }));
        return;
      }
      const data = await response.json();
      setProviderModels(prev => ({ ...prev, [providerId]: data }));
    } catch (err) {
      console.error(`Error loading models for ${providerId}:`, err);
      setProviderModels(prev => ({ ...prev, [providerId]: [] }));
    }
  }

  async function refreshProviderModels(providerId) {
    try {
      const response = await fetch(`${API}/api/ai/providers/${providerId}/refresh`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('خطا در بروزرسانی مدل‌ها');
      
      // Reload models
      await loadProviderModels(providerId);
    } catch (err) {
      console.error(`Error refreshing models for ${providerId}:`, err);
    }
  }

  function updateProjectDefaults(field, value) {
    const updated = { ...aiSettings };
    updated[field] = value;
    
    // If provider changed, reset model to first available
    if (field === 'default_provider' && value !== aiSettings.default_provider) {
      const models = providerModels[value] || [];
      updated.default_model = models.length > 0 ? models[0].name : '';
      
      // Also update stage providers that inherit from project
      Object.keys(updated.stage_providers || {}).forEach(stage => {
        if (updated.stage_providers[stage].inherit_from_project) {
          updated.stage_providers[stage].provider = value;
          updated.stage_providers[stage].model = updated.default_model;
        }
      });
    }
    
    onSettingsChange(updated);
  }

  function updateStageProvider(stage, field, value) {
    const updated = { ...aiSettings };
    
    // Ensure stage_providers exists
    if (!updated.stage_providers) {
      updated.stage_providers = {};
    }
    
    // Ensure stage config exists
    if (!updated.stage_providers[stage]) {
      updated.stage_providers[stage] = {
        provider: aiSettings.default_provider,
        model: aiSettings.default_model,
        inherit_from_project: true
      };
    }
    
    // Update the field
    updated.stage_providers[stage][field] = value;
    
    // If inherit_from_project is set to false, ensure provider and model are set
    if (field === 'inherit_from_project' && value === false) {
      if (!updated.stage_providers[stage].provider) {
        updated.stage_providers[stage].provider = aiSettings.default_provider;
      }
      if (!updated.stage_providers[stage].model) {
        updated.stage_providers[stage].model = aiSettings.default_model;
      }
    }
    
    // If provider changed, reset model
    if (field === 'provider' && value !== updated.stage_providers[stage].provider) {
      const models = providerModels[value] || [];
      updated.stage_providers[stage].model = models.length > 0 ? models[0].name : '';
    }
    
    onSettingsChange(updated);
  }

  function toggleStageExpansion(stage) {
    setExpandedStages(prev => ({
      ...prev,
      [stage]: !prev[stage]
    }));
  }

  // SDLC stages
  const sdlcStages = ['analysis', 'backend', 'n8n', 'frontend', 'qa'];

  // Provider display names
  const providerDisplayNames = {
    ollama: 'Ollama (محلی)',
    codex: 'Codex CLI',
    claude: 'Claude CLI'
  };

  // Stage display names
  const stageDisplayNames = {
    analysis: 'تحلیل',
    backend: 'بک‌اند',
    n8n: 'n8n',
    frontend: 'فرانت‌اند',
    qa: 'تست و کیفیت'
  };

  return (
    <div className="ai-provider-config">
      <div className="ai-provider-tabs">
        <button
          type="button"
          className={`ai-provider-tab ${activeProviderTab === 'project' ? 'active' : ''}`}
          onClick={() => setActiveProviderTab('project')}
        >
          تنظیمات کلی پروژه
        </button>
        <button
          type="button"
          className={`ai-provider-tab ${activeProviderTab === 'stages' ? 'active' : ''}`}
          onClick={() => setActiveProviderTab('stages')}
        >
          تنظیمات مراحل
        </button>
      </div>

      {activeProviderTab === 'project' && (
        <div className="ai-project-config">
          <div className="ai-form-group">
            <label htmlFor="default-provider">ارائه‌دهنده پیش‌فرض</label>
            <select
              id="default-provider"
              value={aiSettings.default_provider || 'ollama'}
              onChange={(e) => updateProjectDefaults('default_provider', e.target.value)}
            >
              {providers.map(provider => (
                <option key={provider.id} value={provider.id}>
                  {provider.name} {provider.available ? '✅' : '❌'}
                </option>
              ))}
            </select>
            <div className="ai-provider-status">
              {providers.find(p => p.id === aiSettings.default_provider)?.available ? (
                <span className="ai-status-success">
                  <CheckCircle size={14} /> ارائه‌دهنده در دسترس است
                </span>
              ) : (
                <span className="ai-status-error">
                  <XCircle size={14} /> ارائه‌دهنده در دسترس نیست
                </span>
              )}
            </div>
          </div>

          <div className="ai-form-group">
            <label htmlFor="default-model">مدل پیش‌فرض</label>
            <div className="ai-model-selector">
              <select
                id="default-model"
                value={aiSettings.default_model || ''}
                onChange={(e) => updateProjectDefaults('default_model', e.target.value)}
                disabled={!providerModels[aiSettings.default_provider]?.length}
              >
                <option value="">انتخاب مدل</option>
                {(providerModels[aiSettings.default_provider] || []).map(model => (
                  <option key={model.name} value={model.name}>
                    {model.name} {model.family ? `(${model.family})` : ''}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="ai-refresh-btn"
                onClick={() => refreshProviderModels(aiSettings.default_provider)}
                title="بروزرسانی لیست مدل‌ها"
              >
                <RefreshCw size={14} />
              </button>
            </div>
            <div className="ai-model-hint">
              {providerModels[aiSettings.default_provider]?.length === 0 && (
                <span className="ai-status-warning">
                  <AlertCircle size={14} /> مدلی یافت نشد
                </span>
              )}
            </div>
          </div>

          {/* Provider-specific settings */}
          {aiSettings.default_provider === 'ollama' && (
            <div className="ai-form-group">
              <label htmlFor="ollama-endpoint">آدرس Ollama</label>
              <input
                id="ollama-endpoint"
                type="text"
                value={aiSettings.ollama_endpoint || 'http://localhost:11434'}
                onChange={(e) => updateProjectDefaults('ollama_endpoint', e.target.value)}
                placeholder="http://localhost:11434"
              />
            </div>
          )}

          {aiSettings.default_provider === 'codex' && aiSettings.codex_endpoint && (
            <div className="ai-form-group">
              <label htmlFor="codex-endpoint">آدرس Codex App Server</label>
              <input
                id="codex-endpoint"
                type="text"
                value={aiSettings.codex_endpoint || ''}
                onChange={(e) => updateProjectDefaults('codex_endpoint', e.target.value)}
                placeholder="آدرس سرور Codex"
              />
            </div>
          )}

          {aiSettings.default_provider === 'claude' && aiSettings.claude_endpoint && (
            <div className="ai-form-group">
              <label htmlFor="claude-endpoint">آدرس Claude CLI</label>
              <input
                id="claude-endpoint"
                type="text"
                value={aiSettings.claude_endpoint || ''}
                onChange={(e) => updateProjectDefaults('claude_endpoint', e.target.value)}
                placeholder="آدرس Claude CLI"
              />
            </div>
          )}
        </div>
      )}

      {activeProviderTab === 'stages' && (
        <div className="ai-stages-config">
          <div className="ai-stages-list">
            {sdlcStages.map(stage => {
              const stageConfig = aiSettings.stage_providers?.[stage] || {
                provider: aiSettings.default_provider,
                model: aiSettings.default_model,
                inherit_from_project: true
              };
              const isExpanded = expandedStages[stage] || false;

              return (
                <div key={stage} className="ai-stage-item">
                  <div 
                    className="ai-stage-header"
                    onClick={() => toggleStageExpansion(stage)}
                  >
                    <div className="ai-stage-toggle">
                      {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </div>
                    <div className="ai-stage-title">
                      <strong>{stageDisplayNames[stage] || stage}</strong>
                      <span className="ai-stage-summary">
                        {stageConfig.inherit_from_project ? (
                          <>
                            از تنظیمات پروژه استفاده می‌کند: {providerDisplayNames[stageConfig.provider]} - {stageConfig.model}
                          </>
                        ) : (
                          <>
                            {providerDisplayNames[stageConfig.provider]} - {stageConfig.model}
                          </>
                        )}
                      </span>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="ai-stage-config">
                      <div className="ai-form-group">
                        <label>
                          <input
                            type="checkbox"
                            checked={!stageConfig.inherit_from_project}
                            onChange={(e) => updateStageProvider(stage, 'inherit_from_project', !e.target.checked)}
                          />
                          تنظیمات متفاوت از پروژه
                        </label>
                      </div>

                      {!stageConfig.inherit_from_project && (
                        <>
                          <div className="ai-form-group">
                            <label>ارائه‌دهنده</label>
                            <select
                              value={stageConfig.provider || aiSettings.default_provider}
                              onChange={(e) => updateStageProvider(stage, 'provider', e.target.value)}
                            >
                              {providers.map(provider => (
                                <option key={provider.id} value={provider.id}>
                                  {provider.name} {provider.available ? '✅' : '❌'}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="ai-form-group">
                            <label>مدل</label>
                            <div className="ai-model-selector">
                              <select
                                value={stageConfig.model || ''}
                                onChange={(e) => updateStageProvider(stage, 'model', e.target.value)}
                                disabled={!providerModels[stageConfig.provider]?.length}
                              >
                                <option value="">انتخاب مدل</option>
                                {(providerModels[stageConfig.provider] || []).map(model => (
                                  <option key={model.name} value={model.name}>
                                    {model.name} {model.family ? `(${model.family})` : ''}
                                  </option>
                                ))}
                              </select>
                              <button
                                type="button"
                                className="ai-refresh-btn"
                                onClick={() => refreshProviderModels(stageConfig.provider)}
                                title="بروزرسانی لیست مدل‌ها"
                              >
                                <RefreshCw size={14} />
                              </button>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}