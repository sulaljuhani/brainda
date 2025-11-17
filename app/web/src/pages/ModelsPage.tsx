import { useState, useEffect } from 'react';
import { llmModelsService, type LLMModel } from '../services/llmModelsService';
import './ModelsPage.css';

export default function ModelsPage() {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await llmModelsService.list(true); // Include inactive
      setModels(data);
    } catch (err) {
      console.error('Failed to load models:', err);
      setError('Failed to load models');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSetDefault = async (modelId: string) => {
    try {
      await llmModelsService.setDefault(modelId);
      await loadModels();
    } catch (err) {
      console.error('Failed to set default model:', err);
      alert('Failed to set default model');
    }
  };

  const handleDelete = async (modelId: string, modelName: string) => {
    if (!confirm(`Are you sure you want to delete "${modelName}"?`)) {
      return;
    }

    try {
      await llmModelsService.delete(modelId);
      await loadModels();
    } catch (err) {
      console.error('Failed to delete model:', err);
      alert('Failed to delete model');
    }
  };

  if (isLoading) {
    return (
      <div className="models-page">
        <div className="models-page__loading">Loading models...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="models-page">
        <div className="models-page__error">{error}</div>
      </div>
    );
  }

  return (
    <div className="models-page">
      <div className="models-page__header">
        <h1 className="models-page__title">LLM Models</h1>
        <p className="models-page__subtitle">
          Manage your connected AI models. Configure API keys and settings for different providers.
        </p>
      </div>

      {models.length === 0 ? (
        <div className="models-page__empty">
          <p>No models configured yet.</p>
          <p className="models-page__empty-hint">
            Add your first model to start using AI features.
          </p>
        </div>
      ) : (
        <div className="models-page__list">
          {models.map((model) => (
            <div key={model.id} className="model-card">
              <div className="model-card__header">
                <div className="model-card__title-section">
                  <h3 className="model-card__name">
                    {model.name}
                    {model.is_default && (
                      <span className="model-card__badge model-card__badge--default">
                        Default
                      </span>
                    )}
                    {!model.is_active && (
                      <span className="model-card__badge model-card__badge--inactive">
                        Inactive
                      </span>
                    )}
                  </h3>
                  <p className="model-card__provider">
                    {model.provider} / {model.model_name}
                  </p>
                </div>
              </div>

              <div className="model-card__details">
                <div className="model-card__detail">
                  <span className="model-card__detail-label">Temperature:</span>
                  <span className="model-card__detail-value">{model.temperature}</span>
                </div>
                {model.max_tokens && (
                  <div className="model-card__detail">
                    <span className="model-card__detail-label">Max Tokens:</span>
                    <span className="model-card__detail-value">{model.max_tokens}</span>
                  </div>
                )}
              </div>

              <div className="model-card__actions">
                {!model.is_default && (
                  <button
                    onClick={() => handleSetDefault(model.id)}
                    className="model-card__button model-card__button--primary"
                  >
                    Set as Default
                  </button>
                )}
                <button
                  onClick={() => handleDelete(model.id, model.name)}
                  className="model-card__button model-card__button--danger"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="models-page__footer">
        <p className="models-page__footer-note">
          To add a new model, use the API or configure it in your environment settings.
        </p>
      </div>
    </div>
  );
}
