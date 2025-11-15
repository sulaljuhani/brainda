import { api } from './api';
import type {
  ChatConversation,
  ConversationWithMessages,
  CreateMessageRequest,
  ChatMessagePersisted
} from '@/types';

export const chatConversationsService = {
  /**
   * List all conversations for the current user
   */
  listConversations: async (limit = 50, offset = 0): Promise<ChatConversation[]> => {
    return api.get<ChatConversation[]>(`/chat/conversations?limit=${limit}&offset=${offset}`);
  },

  /**
   * Get a specific conversation with all its messages
   */
  getConversation: async (conversationId: string): Promise<ConversationWithMessages> => {
    return api.get<ConversationWithMessages>(`/chat/conversations/${conversationId}`);
  },

  /**
   * Create a new message in a conversation
   * If conversation_id is not provided, a new conversation will be created
   */
  createMessage: async (message: CreateMessageRequest): Promise<ChatMessagePersisted> => {
    return api.post<ChatMessagePersisted>('/chat/messages', message);
  },

  /**
   * Delete a conversation and all its messages
   */
  deleteConversation: async (conversationId: string): Promise<void> => {
    return api.delete<void>(`/chat/conversations/${conversationId}`);
  },

  /**
   * Update conversation title
   */
  updateConversationTitle: async (conversationId: string, title: string): Promise<{ success: boolean; title: string }> => {
    return api.patch<{ success: boolean; title: string }>(`/chat/conversations/${conversationId}/title`, { title });
  },
};
