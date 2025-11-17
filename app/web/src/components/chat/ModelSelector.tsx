import { useState, useEffect } from 'react';
import { llmModelsService, type LLMModel } from '../../services/llmModelsService';
import './ModelSelector.css';

interface ModelSelectorProps {
  selectedModelId: string | null;
  onModelChange: (modelId: string | null) => void;
}

export function ModelSelector({ selectedModelId, onModelChange }: ModelSelectorProps) {
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
      const data = await llmModelsService.list();
      setModels(data);

      // If no model is selected but we have models, select the default one
      if (!selectedModelId && data.length > 0) {
        const defaultModel = data.find(m => m.is_default) || data[0];
        onModelChange(defaultModel.id);
      }
    } catch (err) {
      console.error('Failed to load LLM models:', err);
      setError('Failed to load models');
    } finally {
      setIsLoading(false);
    }
  };

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onModelChange(value === '' ? null : value);
  };

  const getModelDisplayName = (model: LLMModel) => {
    return `${model.name} (${model.provider}/${model.model_name})`;
  };

  if (error) {
    return (
      <div className="model-selector model-selector--error">
        <span className="model-selector__error">{error}</span>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="model-selector model-selector--loading">
        <select className="model-selector__select" disabled>
          <option>Loading models...</option>
        </select>
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div className="model-selector model-selector--empty">
        <span className="model-selector__empty">No models configured</span>
      </div>
    );
  }

  return (
    <div className="model-selector">
      <label htmlFor="model-select" className="model-selector__label">
        Model:
      </label>
      <select
        id="model-select"
        className="model-selector__select"
        value={selectedModelId || ''}
        onChange={handleModelChange}
      >
        <option value="">Default</option>
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {getModelDisplayName(model)}
            {model.is_default && ' ⭐'}
          </option>
        ))}
      </select>
    </div>
  );
}
