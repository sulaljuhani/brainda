import { useState, useEffect, useCallback } from 'react';
import { chatConversationsService } from '../services/chatConversationsService';
import type { ConversationWithMessages, ChatMessage } from '@/types';

export function useConversation(conversationId: string | null) {
  const [conversation, setConversation] = useState<ConversationWithMessages | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadConversation = useCallback(async () => {
    if (!conversationId) {
      setConversation(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const data = await chatConversationsService.getConversation(conversationId);
      setConversation(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load conversation';
      setError(errorMessage);
      console.error('Error loading conversation:', err);
    } finally {
      setIsLoading(false);
    }
  }, [conversationId]);

  useEffect(() => {
    loadConversation();
  }, [loadConversation]);

  // Convert persisted messages to ChatMessage format for display
  const getMessages = useCallback((): ChatMessage[] => {
    if (!conversation) return [];

    return conversation.messages.map((msg) => ({
      id: msg.id,
      role: msg.role,
      text: msg.content,
      timestamp: new Date(msg.created_at),
      citations: msg.citations,
      toolCall: msg.tool_calls?.[0] ? {
        icon: msg.tool_calls[0].icon || '🔧',
        name: msg.tool_calls[0].name || 'Tool',
        result: msg.tool_calls[0].result || '',
        status: msg.tool_calls[0].status || 'success',
      } : undefined,
    }));
  }, [conversation]);

  return {
    conversation,
    messages: getMessages(),
    isLoading,
    error,
    loadConversation,
  };
}
