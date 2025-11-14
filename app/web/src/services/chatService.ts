import { api } from './api';
import type { ChatRequest } from '@types/*';

export const chatService = {
  sendMessage: (message: string) =>
    api.stream('/chat', { message } as ChatRequest),
};
