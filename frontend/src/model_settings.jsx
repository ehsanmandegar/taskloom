import React, { useState, useEffect } from 'react';
import { RefreshCw, CheckCircle2, XCircle, Save, AlertCircle } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || '';

export default function ModelSettings({ projectId, onClose }) {
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [ollamaConnected, setOllamaConnected] = useState(false);
    const [models, setModels] = useState([]);
    const [settings, setSettings] = useState({
        default_model: 'qwen3.5:0.8b',
        stage_assignments: {},
        ollama_endpoint: 'http://localhost:11434'
    });
    
    // مراحل SDLC
    const stages = ['analysis', 'backend', 'n8n', 'frontend', 'qa'];
    const stageLabels = {
        analysis: 'تحلیل نیازمندی‌ها',
        backend: 'توسعه بک‌اند',
        n8n: 'مهندسی workflow n8n',
        frontend: 'توسعه فرانت‌اند',
        qa: 'تست و کیفیت'
    };

    // بارگیری تنظیمات و مدل‌ها
    useEffect(() => {
        loadData();
    }, [projectId]);

    async function loadData() {
        setLoading(true);
        setError('');
        try {
            // بررسی اتصال Ollama
            const connectionRes = await fetch(`${API}/api/ollama/connection`);
            const connectionData = await connectionRes.json();
            setOllamaConnected(connectionData.connected);
            
            // دریافت لیست مدل‌ها
            if (connectionData.connected) {
                const modelsRes = await fetch(`${API}/api/ollama/models`);
                if (modelsRes.ok) {
                    const modelsData = await modelsRes.json();
                    setModels(modelsData);
                }
            }
            
            // دریافت تنظیمات پروژه
            const settingsRes = await fetch(`${API}/api/sdlc/projects/${projectId}/model-settings`);
            if (settingsRes.ok) {
                const settingsData = await settingsRes.json();
                setSettings(settingsData);
            }
        } catch (err) {
            setError('خطا در بارگیری داده‌ها: ' + err.message);
        } finally {
            setLoading(false);
        }
    }

    async function refreshModels() {
        setError('');
        try {
            const res = await fetch(`${API}/api/ollama/models`);
            if (res.ok) {
                const data = await res.json();
                setModels(data);
                
                // بررسی اتصال مجدد
                const connectionRes = await fetch(`${API}/api/ollama/connection`);
                const connectionData = await connectionRes.json();
                setOllamaConnected(connectionData.connected);
            }
        } catch (err) {
            setError('خطا در به‌روزرسانی مدل‌ها: ' + err.message);
        }
    }

    async function saveSettings() {
        setSaving(true);
        setError('');
        setSuccess('');
        try {
            const res = await fetch(`${API}/api/sdlc/projects/${projectId}/model-settings`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            
            if (res.ok) {
                setSuccess('تنظیمات با موفقیت ذخیره شد');
                setTimeout(() => setSuccess(''), 3000);
            } else {
                const errorData = await res.json();
                throw new Error(errorData.detail || 'خطا در ذخیره تنظیمات');
            }
        } catch (err) {
            setError('خطا در ذخیره تنظیمات: ' + err.message);
        } finally {
            setSaving(false);
        }
    }

    function updateDefaultModel(model) {
        setSettings(prev => ({ ...prev, default_model: model }));
    }

    function updateStageModel(stage, model) {
        setSettings(prev => ({
            ...prev,
            stage_assignments: {
                ...prev.stage_assignments,
                [stage]: model
            }
        }));
    }

    function getStageModel(stage) {
        return settings.stage_assignments[stage] || settings.default_model;
    }

    function getModelDisplayName(modelName) {
        const model = models.find(m => m.name === modelName);
        if (!model) return modelName;
        
        let displayName = modelName;
        if (model.family) {
            displayName = `${model.family} ${model.parameters || ''}`.trim();
            if (model.quantization) {
                displayName += ` (${model.quantization})`;
            }
        }
        return displayName;
    }

    if (loading) {
        return (
            <div className="model-settings" dir="rtl">
                <header>
                    <h2>تنظیمات مدل‌های AI</h2>
                    <button type="button" onClick={onClose}>×</button>
                </header>
                <div className="loading">در حال بارگیری...</div>
            </div>
        );
    }

    return (
        <div className="model-settings" dir="rtl">
            <header>
                <h2>تنظیمات مدل‌های AI</h2>
                <button type="button" onClick={onClose}>×</button>
            </header>
            
            <div className="model-settings-content">
                {/* وضعیت Ollama */}
                <section className="ollama-status">
                    <h3>وضعیت Ollama</h3>
                    <div className={`status-indicator ${ollamaConnected ? 'connected' : 'disconnected'}`}>
                        {ollamaConnected ? (
                            <>
                                <CheckCircle2 size={16} />
                                <span>متصل به Ollama</span>
                            </>
                        ) : (
                            <>
                                <XCircle size={16} />
                                <span>Ollama در دسترس نیست</span>
                            </>
                        )}
                    </div>
                    <div className="ollama-actions">
                        <button type="button" onClick={refreshModels} disabled={!ollamaConnected}>
                            <RefreshCw size={14} />
                            به‌روزرسانی مدل‌ها
                        </button>
                        <small>آدرس: {settings.ollama_endpoint}</small>
                    </div>
                </section>

                {/* مدل‌های موجود */}
                <section className="available-models">
                    <h3>مدل‌های نصب شده ({models.length})</h3>
                    {models.length > 0 ? (
                        <div className="model-list">
                            {models.map(model => (
                                <div key={model.name} className="model-item">
                                    <div className="model-name">{getModelDisplayName(model.name)}</div>
                                    <div className="model-details">
                                        {model.family && <span className="model-family">{model.family}</span>}
                                        {model.parameters && <span className="model-params">{model.parameters}</span>}
                                        {model.quantization && <span className="model-quant">{model.quantization}</span>}
                                        {model.supports_tool_calls && <span className="model-tool-calls">ابزار</span>}
                                    </div>
                                    <div className="model-size">
                                        {(model.size / 1024 / 1024 / 1024).toFixed(2)} GB
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="no-models">
                            <AlertCircle size={24} />
                            <p>هیچ مدلی در Ollama یافت نشد.</p>
                            <small>برای افزودن مدل از دستور <code>ollama pull &lt;model-name&gt;</code> استفاده کنید.</small>
                        </div>
                    )}
                </section>

                {/* مدل پیش‌فرض پروژه */}
                <section className="default-model">
                    <h3>مدل پیش‌فرض پروژه</h3>
                    <p className="section-description">این مدل برای مراحلی که مدل خاصی برای آنها تعیین نشده استفاده می‌شود.</p>
                    <select 
                        value={settings.default_model}
                        onChange={(e) => updateDefaultModel(e.target.value)}
                        disabled={models.length === 0}
                    >
                        {models.length > 0 ? (
                            models.map(model => (
                                <option key={model.name} value={model.name}>
                                    {getModelDisplayName(model.name)}
                                </option>
                            ))
                        ) : (
                            <option value="qwen3.5:0.8b">qwen3.5:0.8b (پیش‌فرض سیستم)</option>
                        )}
                    </select>
                </section>

                {/* تنظیمات مدل برای هر مرحله */}
                <section className="stage-models">
                    <h3>مدل‌های اختصاصی مراحل</h3>
                    <p className="section-description">برای هر مرحله می‌توانید مدل متفاوتی انتخاب کنید.</p>
                    
                    <table className="stage-model-table">
                        <thead>
                            <tr>
                                <th>مرحله</th>
                                <th>وظیفه</th>
                                <th>مدل انتخاب شده</th>
                            </tr>
                        </thead>
                        <tbody>
                            {stages.map(stage => (
                                <tr key={stage}>
                                    <td className="stage-name">
                                        <strong>{stageLabels[stage]}</strong>
                                        <small>{stage}</small>
                                    </td>
                                    <td className="stage-role">
                                        {stage === 'analysis' && 'تحلیل و مستندسازی'}
                                        {stage === 'backend' && 'کدنویسی بک‌اند'}
                                        {stage === 'n8n' && 'طراحی workflow'}
                                        {stage === 'frontend' && 'کدنویسی فرانت‌اند'}
                                        {stage === 'qa' && 'تست و کیفیت‌سنجی'}
                                    </td>
                                    <td className="stage-model">
                                        <select
                                            value={getStageModel(stage)}
                                            onChange={(e) => updateStageModel(stage, e.target.value)}
                                            disabled={models.length === 0}
                                        >
                                            <option value="">استفاده از مدل پیش‌فرض پروژه</option>
                                            {models.map(model => (
                                                <option key={`${stage}-${model.name}`} value={model.name}>
                                                    {getModelDisplayName(model.name)}
                                                </option>
                                            ))}
                                        </select>
                                        <small className="model-hint">
                                            {getStageModel(stage) === settings.default_model ? 
                                                '← مدل پیش‌فرض پروژه' : 
                                                `← ${getModelDisplayName(getStageModel(stage))}`}
                                        </small>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </section>

                {/* پیام‌های خطا و موفقیت */}
                {error && (
                    <div className="error-message">
                        <AlertCircle size={16} />
                        {error}
                    </div>
                )}
                {success && (
                    <div className="success-message">
                        <CheckCircle2 size={16} />
                        {success}
                    </div>
                )}

                {/* دکمه‌های اقدام */}
                <div className="action-buttons">
                    <button type="button" onClick={onClose} className="secondary">
                        انصراف
                    </button>
                    <button 
                        type="button" 
                        onClick={saveSettings} 
                        disabled={saving || models.length === 0}
                        className="primary"
                    >
                        {saving ? (
                            <>
                                <RefreshCw size={14} className="spin" />
                                در حال ذخیره...
                            </>
                        ) : (
                            <>
                                <Save size={14} />
                                ذخیره تنظیمات
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}