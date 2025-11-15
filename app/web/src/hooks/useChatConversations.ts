import { useState, useEffect, useCallback } from 'react';
import { chatConversationsService } from '../services/chatConversationsService';
import type { ChatConversation } from '@/types';

export function useChatConversations() {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadConversations = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await chatConversationsService.listConversations();
      setConversations(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load conversations';
      setError(errorMessage);
      console.error('Error loading conversations:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const deleteConversation = useCallback(async (conversationId: string) => {
    try {
      await chatConversationsService.deleteConversation(conversationId);
      // Remove from local state
      setConversations((prev) => prev.filter((c) => c.id !== conversationId));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete conversation';
      setError(errorMessage);
      console.error('Error deleting conversation:', err);
      throw err;
    }
  }, []);

  const updateConversationTitle = useCallback(async (conversationId: string, title: string) => {
    try {
      await chatConversationsService.updateConversationTitle(conversationId, title);
      // Update in local state
      setConversations((prev) =>
        prev.map((c) => (c.id === conversationId ? { ...c, title } : c))
      );
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update title';
      setError(errorMessage);
      console.error('Error updating conversation title:', err);
      throw err;
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  return {
    conversations,
    isLoading,
    error,
    loadConversations,
    deleteConversation,
    updateConversationTitle,
  };
}
