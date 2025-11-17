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
   * Create a new message with file attachments
   * Uses multipart/form-data to upload files
   */
  createMessageWithFiles: async (
    content: string,
    files: File[],
    conversationId?: string
  ): Promise<ChatMessagePersisted> => {
    const formData = new FormData();
    formData.append('content', content);
    if (conversationId) {
      formData.append('conversation_id', conversationId);
    }
    files.forEach((file) => {
      formData.append('files', file);
    });

    const token = localStorage.getItem('sessionToken');
    const response = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/v1/chat/messages/with-files`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to upload files' }));
      throw new Error(error.detail || 'Failed to upload files');
    }

    return response.json();
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
