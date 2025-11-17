import { api } from './api';
import type { ChatRequest } from '@/types';

export const chatService = {
  sendMessage: (message: string, modelId?: string | null) =>
    api.stream('/chat', { message, model_id: modelId } as ChatRequest),
};
