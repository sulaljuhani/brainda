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

export interface TestProviderRequest {
  provider: 'openai' | 'anthropic' | 'ollama' | 'custom';
  config: Record<string, any>;
}

export interface DiscoveredModel {
  id: string;
  name: string;
  description?: string;
  created?: number;
  size?: number;
  modified_at?: string;
}

export interface DiscoverModelsResponse {
  success: boolean;
  provider: string;
  models: DiscoveredModel[];
  note?: string;
  message?: string;
}

export interface BulkCreateModelsRequest {
  provider: 'openai' | 'anthropic' | 'ollama' | 'custom';
  config: Record<string, any>;
  models: string[];  // List of model IDs to create
  temperature?: number;
  set_first_as_default?: boolean;
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

  // Test provider credentials
  testProvider: (data: TestProviderRequest): Promise<{ success: boolean; message: string; provider: string }> =>
    api.post('/llm-models/test-provider', data),

  // Discover available models from provider
  discoverModels: (provider: string, config: Record<string, any>): Promise<DiscoverModelsResponse> =>
    api.post('/llm-models/discover-models', { provider, config }),

  // Bulk create models
  bulkCreate: (data: BulkCreateModelsRequest): Promise<{ success: boolean; created: number; models: LLMModel[] }> =>
    api.post('/llm-models/bulk-create', data),
};
