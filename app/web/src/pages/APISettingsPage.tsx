import { useState } from 'react';
import { llmModelsService, type DiscoveredModel } from '../services/llmModelsService';
import './APISettingsPage.css';

type Provider = 'openai' | 'anthropic' | 'ollama' | 'custom';

interface ProviderConfig {
  api_key?: string;
  base_url?: string;
  url?: string;
  headers?: Record<string, string>;
}

export default function APISettingsPage() {
  const [selectedProvider, setSelectedProvider] = useState<Provider>('openai');
  const [config, setConfig] = useState<ProviderConfig>({});
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<{
    type: 'success' | 'error' | null;
    message: string;
  }>({ type: null, message: '' });

  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveredModels, setDiscoveredModels] = useState<DiscoveredModel[]>([]);
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [discoveryNote, setDiscoveryNote] = useState<string>('');

  const [isCreating, setIsCreating] = useState(false);
  const [createStatus, setCreateStatus] = useState<{
    type: 'success' | 'error' | null;
    message: string;
  }>({ type: null, message: '' });

  const handleProviderChange = (provider: Provider) => {
    setSelectedProvider(provider);
    setConfig({});
    setConnectionStatus({ type: null, message: '' });
    setDiscoveredModels([]);
    setSelectedModels(new Set());
    setDiscoveryNote('');
    setCreateStatus({ type: null, message: '' });
  };

  const handleConfigChange = (field: string, value: string) => {
    setConfig(prev => ({ ...prev, [field]: value }));
    setConnectionStatus({ type: null, message: '' });
  };

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setConnectionStatus({ type: null, message: '' });

    try {
      const result = await llmModelsService.testProvider({
        provider: selectedProvider,
        config,
      });

      setConnectionStatus({
        type: 'success',
        message: result.message,
      });
    } catch (err: any) {
      setConnectionStatus({
        type: 'error',
        message: err.message || 'Connection test failed',
      });
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleDiscoverModels = async () => {
    setIsDiscovering(true);
    setDiscoveredModels([]);
    setSelectedModels(new Set());
    setDiscoveryNote('');
    setConnectionStatus({ type: null, message: '' });

    try {
      const result = await llmModelsService.discoverModels(selectedProvider, config);
      setDiscoveredModels(result.models);
      setDiscoveryNote(result.note || result.message || '');

      if (result.models.length === 0) {
        setConnectionStatus({
          type: 'error',
          message: 'No models found. Please check your configuration.',
        });
      }
    } catch (err: any) {
      setConnectionStatus({
        type: 'error',
        message: err.message || 'Failed to discover models',
      });
    } finally {
      setIsDiscovering(false);
    }
  };

  const toggleModelSelection = (modelId: string) => {
    setSelectedModels(prev => {
      const newSet = new Set(prev);
      if (newSet.has(modelId)) {
        newSet.delete(modelId);
      } else {
        newSet.add(modelId);
      }
      return newSet;
    });
  };

  const handleCreateModels = async () => {
    if (selectedModels.size === 0) {
      setCreateStatus({
        type: 'error',
        message: 'Please select at least one model',
      });
      return;
    }

    setIsCreating(true);
    setCreateStatus({ type: null, message: '' });

    try {
      const result = await llmModelsService.bulkCreate({
        provider: selectedProvider,
        config,
        models: Array.from(selectedModels),
        temperature: 0.7,
        set_first_as_default: true,
      });

      setCreateStatus({
        type: 'success',
        message: `Successfully created ${result.created} model(s). You can now use them in the chat!`,
      });

      // Clear selections
      setSelectedModels(new Set());
    } catch (err: any) {
      setCreateStatus({
        type: 'error',
        message: err.message || 'Failed to create models',
      });
    } finally {
      setIsCreating(false);
    }
  };

  const renderProviderForm = () => {
    switch (selectedProvider) {
      case 'openai':
        return (
          <div className="api-settings__form">
            <div className="api-settings__form-group">
              <label htmlFor="api-key">API Key *</label>
              <input
                id="api-key"
                type="password"
                placeholder="sk-..."
                value={config.api_key || ''}
                onChange={e => handleConfigChange('api_key', e.target.value)}
              />
              <small>Your OpenAI API key from platform.openai.com</small>
            </div>
            <div className="api-settings__form-group">
              <label htmlFor="base-url">Base URL (optional)</label>
              <input
                id="base-url"
                type="text"
                placeholder="https://api.openai.com/v1"
                value={config.base_url || ''}
                onChange={e => handleConfigChange('base_url', e.target.value)}
              />
              <small>Leave empty for default OpenAI endpoint</small>
            </div>
          </div>
        );

      case 'anthropic':
        return (
          <div className="api-settings__form">
            <div className="api-settings__form-group">
              <label htmlFor="api-key">API Key *</label>
              <input
                id="api-key"
                type="password"
                placeholder="sk-ant-..."
                value={config.api_key || ''}
                onChange={e => handleConfigChange('api_key', e.target.value)}
              />
              <small>Your Anthropic API key from console.anthropic.com</small>
            </div>
          </div>
        );

      case 'ollama':
        return (
          <div className="api-settings__form">
            <div className="api-settings__form-group">
              <label htmlFor="base-url">Ollama URL *</label>
              <input
                id="base-url"
                type="text"
                placeholder="http://localhost:11434"
                value={config.base_url || ''}
                onChange={e => handleConfigChange('base_url', e.target.value)}
              />
              <small>URL of your local or remote Ollama instance</small>
            </div>
          </div>
        );

      case 'custom':
        return (
          <div className="api-settings__form">
            <div className="api-settings__form-group">
              <label htmlFor="url">API URL *</label>
              <input
                id="url"
                type="text"
                placeholder="https://your-api.com/v1/chat/completions"
                value={config.url || ''}
                onChange={e => handleConfigChange('url', e.target.value)}
              />
              <small>OpenAI-compatible API endpoint</small>
            </div>
            <div className="api-settings__form-group">
              <label htmlFor="api-key">API Key (optional)</label>
              <input
                id="api-key"
                type="password"
                placeholder="your-api-key"
                value={config.api_key || ''}
                onChange={e => handleConfigChange('api_key', e.target.value)}
              />
              <small>Leave empty if no authentication required</small>
            </div>
          </div>
        );
    }
  };

  return (
    <div className="api-settings">
      <div className="api-settings__header">
        <h1 className="api-settings__title">API Settings</h1>
        <p className="api-settings__subtitle">
          Configure AI providers and discover available models
        </p>
      </div>

      <div className="api-settings__content">
        {/* Provider Selection */}
        <section className="api-settings__section">
          <h2 className="api-settings__section-title">1. Select Provider</h2>
          <div className="api-settings__provider-tabs">
            {(['openai', 'anthropic', 'ollama', 'custom'] as Provider[]).map(provider => (
              <button
                key={provider}
                className={`api-settings__tab ${selectedProvider === provider ? 'api-settings__tab--active' : ''}`}
                onClick={() => handleProviderChange(provider)}
              >
                {provider === 'openai' && '🤖 OpenAI'}
                {provider === 'anthropic' && '🧠 Anthropic'}
                {provider === 'ollama' && '🦙 Ollama'}
                {provider === 'custom' && '⚙️ Custom'}
              </button>
            ))}
          </div>
        </section>

        {/* Provider Configuration */}
        <section className="api-settings__section">
          <h2 className="api-settings__section-title">2. Enter Credentials</h2>
          {renderProviderForm()}

          <div className="api-settings__actions">
            <button
              className="api-settings__button api-settings__button--secondary"
              onClick={handleTestConnection}
              disabled={isTestingConnection || !config.api_key && !config.base_url && !config.url}
            >
              {isTestingConnection ? 'Testing...' : 'Test Connection'}
            </button>

            <button
              className="api-settings__button api-settings__button--primary"
              onClick={handleDiscoverModels}
              disabled={isDiscovering || !config.api_key && !config.base_url && !config.url}
            >
              {isDiscovering ? 'Discovering...' : 'Discover Models'}
            </button>
          </div>

          {connectionStatus.type && (
            <div className={`api-settings__status api-settings__status--${connectionStatus.type}`}>
              {connectionStatus.message}
            </div>
          )}
        </section>

        {/* Model Discovery Results */}
        {discoveredModels.length > 0 && (
          <section className="api-settings__section">
            <h2 className="api-settings__section-title">3. Select Models</h2>
            {discoveryNote && (
              <p className="api-settings__note">{discoveryNote}</p>
            )}

            <div className="api-settings__models-list">
              {discoveredModels.map(model => (
                <label key={model.id} className="api-settings__model-item">
                  <input
                    type="checkbox"
                    checked={selectedModels.has(model.id)}
                    onChange={() => toggleModelSelection(model.id)}
                  />
                  <div className="api-settings__model-info">
                    <span className="api-settings__model-name">{model.name}</span>
                    {model.description && (
                      <span className="api-settings__model-desc">{model.description}</span>
                    )}
                  </div>
                </label>
              ))}
            </div>

            <div className="api-settings__actions">
              <button
                className="api-settings__button api-settings__button--primary"
                onClick={handleCreateModels}
                disabled={isCreating || selectedModels.size === 0}
              >
                {isCreating ? 'Creating...' : `Create ${selectedModels.size} Model(s)`}
              </button>
            </div>

            {createStatus.type && (
              <div className={`api-settings__status api-settings__status--${createStatus.type}`}>
                {createStatus.message}
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
