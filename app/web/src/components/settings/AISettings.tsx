import { useState, useEffect } from 'react';
import styles from './AISettings.module.css';

interface LLMConfig {
  backend: 'dummy' | 'ollama' | 'openai' | 'anthropic' | 'custom';
  apiKey?: string;
  baseUrl?: string;
  model?: string;
  temperature?: number;
  systemPrompt?: string;
}

const DEFAULT_SYSTEM_PROMPT = `You are a helpful assistant with access to calendar, task, and reminder management tools.

When the user asks to create events, tasks, or reminders, use the appropriate tools:
- For calendar events (meetings, appointments): use create_calendar_event
- For tasks (things to do, projects, work items): use create_task
- For reminders (time-based notifications): use create_reminder
- For subtasks: use create_subtask with parent_task_id

Tool usage guidelines:
- Tasks can have start/end dates, recurrence (rrule), and can be organized hierarchically
- Reminders can be standalone or linked to tasks/events with offsets
- Always infer reasonable defaults for missing information
- If no time is specified, use a sensible default based on context
- Use the user's timezone (default to UTC if unknown)
- For recurring items, construct proper RRULE strings

Be conversational and confirm what you've done.`;

export function AISettings() {
  const [config, setConfig] = useState<LLMConfig>({
    backend: 'dummy',
    temperature: 0.7,
    systemPrompt: DEFAULT_SYSTEM_PROMPT,
  });
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  // Load current configuration
  useEffect(() => {
    // In a real implementation, this would fetch from the API
    const savedConfig = localStorage.getItem('llm_config');
    if (savedConfig) {
      setConfig({ ...config, ...JSON.parse(savedConfig) });
    }
  }, []);

  const handleBackendChange = (backend: LLMConfig['backend']) => {
    setConfig({ ...config, backend });
  };

  const handleInputChange = (field: keyof LLMConfig, value: string | number) => {
    setConfig({ ...config, [field]: value });
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage('');

    try {
      // In a real implementation, this would save to the API
      localStorage.setItem('llm_config', JSON.stringify(config));

      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 500));

      setSaveMessage('Settings saved successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (error) {
      setSaveMessage('Failed to save settings. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetPrompt = () => {
    setConfig({ ...config, systemPrompt: DEFAULT_SYSTEM_PROMPT });
  };

  return (
    <div className={styles.aiSettings}>
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>LLM Backend</h2>
        <p className={styles.sectionDescription}>
          Choose which language model backend to use for chat and AI features.
        </p>

        <div className={styles.formGroup}>
          <label className={styles.label}>Backend Provider</label>
          <div className={styles.radioGroup}>
            <label className={styles.radioLabel}>
              <input
                type="radio"
                name="backend"
                value="dummy"
                checked={config.backend === 'dummy'}
                onChange={() => handleBackendChange('dummy')}
                className={styles.radio}
              />
              <div className={styles.radioContent}>
                <span className={styles.radioTitle}>Dummy (Testing)</span>
                <span className={styles.radioDescription}>
                  Simple placeholder responses for testing
                </span>
              </div>
            </label>

            <label className={styles.radioLabel}>
              <input
                type="radio"
                name="backend"
                value="ollama"
                checked={config.backend === 'ollama'}
                onChange={() => handleBackendChange('ollama')}
                className={styles.radio}
              />
              <div className={styles.radioContent}>
                <span className={styles.radioTitle}>Ollama (Local)</span>
                <span className={styles.radioDescription}>
                  Run models locally with Ollama
                </span>
              </div>
            </label>

            <label className={styles.radioLabel}>
              <input
                type="radio"
                name="backend"
                value="openai"
                checked={config.backend === 'openai'}
                onChange={() => handleBackendChange('openai')}
                className={styles.radio}
              />
              <div className={styles.radioContent}>
                <span className={styles.radioTitle}>OpenAI</span>
                <span className={styles.radioDescription}>
                  GPT-4, GPT-3.5 Turbo, and other OpenAI models
                </span>
              </div>
            </label>

            <label className={styles.radioLabel}>
              <input
                type="radio"
                name="backend"
                value="anthropic"
                checked={config.backend === 'anthropic'}
                onChange={() => handleBackendChange('anthropic')}
                className={styles.radio}
              />
              <div className={styles.radioContent}>
                <span className={styles.radioTitle}>Anthropic</span>
                <span className={styles.radioDescription}>
                  Claude 3 Opus, Sonnet, and Haiku models
                </span>
              </div>
            </label>

            <label className={styles.radioLabel}>
              <input
                type="radio"
                name="backend"
                value="custom"
                checked={config.backend === 'custom'}
                onChange={() => handleBackendChange('custom')}
                className={styles.radio}
              />
              <div className={styles.radioContent}>
                <span className={styles.radioTitle}>Custom (OpenAI-compatible)</span>
                <span className={styles.radioDescription}>
                  Any OpenAI-compatible API endpoint
                </span>
              </div>
            </label>
          </div>
        </div>
      </div>

      {/* Backend-specific configuration */}
      {(config.backend === 'openai' || config.backend === 'anthropic') && (
        <div className={styles.section}>
          <h3 className={styles.sectionSubtitle}>API Configuration</h3>

          <div className={styles.formGroup}>
            <label className={styles.label}>API Key</label>
            <input
              type="password"
              className={styles.input}
              value={config.apiKey || ''}
              onChange={(e) => handleInputChange('apiKey', e.target.value)}
              placeholder={`Enter your ${config.backend === 'openai' ? 'OpenAI' : 'Anthropic'} API key`}
            />
            <p className={styles.helpText}>
              Your API key is stored securely and never shared.
            </p>
          </div>

          {config.backend === 'openai' && (
            <div className={styles.formGroup}>
              <label className={styles.label}>Model</label>
              <select
                className={styles.select}
                value={config.model || 'gpt-4-turbo-preview'}
                onChange={(e) => handleInputChange('model', e.target.value)}
              >
                <option value="gpt-4-turbo-preview">GPT-4 Turbo</option>
                <option value="gpt-4">GPT-4</option>
                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
              </select>
            </div>
          )}

          {config.backend === 'anthropic' && (
            <div className={styles.formGroup}>
              <label className={styles.label}>Model</label>
              <select
                className={styles.select}
                value={config.model || 'claude-3-sonnet-20240229'}
                onChange={(e) => handleInputChange('model', e.target.value)}
              >
                <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                <option value="claude-3-sonnet-20240229">Claude 3 Sonnet</option>
                <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
              </select>
            </div>
          )}
        </div>
      )}

      {(config.backend === 'ollama' || config.backend === 'custom') && (
        <div className={styles.section}>
          <h3 className={styles.sectionSubtitle}>Server Configuration</h3>

          <div className={styles.formGroup}>
            <label className={styles.label}>Base URL</label>
            <input
              type="url"
              className={styles.input}
              value={config.baseUrl || (config.backend === 'ollama' ? 'http://localhost:11434' : '')}
              onChange={(e) => handleInputChange('baseUrl', e.target.value)}
              placeholder={config.backend === 'ollama' ? 'http://localhost:11434' : 'https://api.example.com/v1'}
            />
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>Model</label>
            <input
              type="text"
              className={styles.input}
              value={config.model || ''}
              onChange={(e) => handleInputChange('model', e.target.value)}
              placeholder={config.backend === 'ollama' ? 'llama2, mistral, etc.' : 'Model name'}
            />
          </div>
        </div>
      )}

      {/* Advanced Settings */}
      <div className={styles.section}>
        <h3 className={styles.sectionSubtitle}>Advanced Settings</h3>

        <div className={styles.formGroup}>
          <label className={styles.label}>
            Temperature
            <span className={styles.labelValue}>{config.temperature}</span>
          </label>
          <input
            type="range"
            min="0"
            max="2"
            step="0.1"
            className={styles.slider}
            value={config.temperature || 0.7}
            onChange={(e) => handleInputChange('temperature', parseFloat(e.target.value))}
          />
          <div className={styles.sliderLabels}>
            <span>Precise (0)</span>
            <span>Balanced</span>
            <span>Creative (2)</span>
          </div>
          <p className={styles.helpText}>
            Higher values make output more creative but less predictable.
          </p>
        </div>
      </div>

      {/* System Prompt */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <div>
            <h3 className={styles.sectionSubtitle}>System Prompt</h3>
            <p className={styles.sectionDescription}>
              Customize the AI assistant's behavior and personality.
            </p>
          </div>
          <button
            type="button"
            className={styles.resetButton}
            onClick={handleResetPrompt}
          >
            Reset to Default
          </button>
        </div>

        <div className={styles.formGroup}>
          <textarea
            className={styles.textarea}
            value={config.systemPrompt || ''}
            onChange={(e) => handleInputChange('systemPrompt', e.target.value)}
            rows={15}
            placeholder="Enter custom system prompt..."
          />
          <p className={styles.helpText}>
            The system prompt defines how the AI assistant behaves and what tools it can use.
          </p>
        </div>
      </div>

      {/* Save Button */}
      <div className={styles.actions}>
        <button
          className={styles.saveButton}
          onClick={handleSave}
          disabled={isSaving}
        >
          {isSaving ? 'Saving...' : 'Save Settings'}
        </button>
        {saveMessage && (
          <span className={`${styles.saveMessage} ${
            saveMessage.includes('success') ? styles.saveMessageSuccess : styles.saveMessageError
          }`}>
            {saveMessage}
          </span>
        )}
      </div>
    </div>
  );
}
