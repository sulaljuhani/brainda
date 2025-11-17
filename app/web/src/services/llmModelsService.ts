import { api } from './api';

export interface LLMModel {
  id: string;
  user_id: string;
  name: string;
  provider: 'openai' | 'anthropic' | 'ollama' | 'custom';
  model_name: string;
  config: Record<string, any>;
  temperature: number;
  max_tokens?: number;
  is_default: boolean;
  is_active: boolean;
}

export interface CreateLLMModelRequest {
  name: string;
  provider: 'openai' | 'anthropic' | 'ollama' | 'custom';
  model_name: string;
  config: Record<string, any>;
  temperature?: number;
  max_tokens?: number;
  is_default?: boolean;
}

export interface UpdateLLMModelRequest {
  name?: string;
  provider?: 'openai' | 'anthropic' | 'ollama' | 'custom';
  model_name?: string;
  config?: Record<string, any>;
  temperature?: number;
  max_tokens?: number;
  is_default?: boolean;
  is_active?: boolean;
}

export const llmModelsService = {
  // List all LLM models
  list: (includeInactive = false): Promise<LLMModel[]> =>
    api.get(`/llm-models?include_inactive=${includeInactive}`),

  // Get default model
  getDefault: (): Promise<LLMModel | null> =>
    api.get('/llm-models/default'),

  // Get specific model
  get: (id: string): Promise<LLMModel> =>
    api.get(`/llm-models/${id}`),

  // Create new model
  create: (data: CreateLLMModelRequest): Promise<LLMModel> =>
    api.post('/llm-models', data),

  // Update model
  update: (id: string, data: UpdateLLMModelRequest): Promise<LLMModel> =>
    api.patch(`/llm-models/${id}`, data),

  // Delete model
  delete: (id: string): Promise<{ success: boolean; message: string }> =>
    api.delete(`/llm-models/${id}`),

  // Set as default
  setDefault: (id: string): Promise<{ success: boolean; message: string }> =>
    api.post(`/llm-models/${id}/set-default`, {}),
};
