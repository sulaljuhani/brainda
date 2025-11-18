import { useState, useCallback, useEffect } from 'react';
import { chatService } from '../services/chatService';
import { chatConversationsService } from '../services/chatConversationsService';
import type { ChatMessage } from '@/types';

interface UseChatOptions {
  conversationId?: string | null;
  onConversationCreated?: (conversationId: string) => void;
  modelId?: string | null;
}

export function useChat(options: UseChatOptions = {}) {
  const { conversationId, onConversationCreated, modelId } = options;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(
    conversationId || null
  );

  // Update current conversation ID when prop changes
  useEffect(() => {
    if (conversationId !== undefined) {
      setCurrentConversationId(conversationId);
    }
  }, [conversationId]);

  const sendMessage = useCallback(async (text: string, files?: File[]) => {
    if ((!text.trim() && (!files || files.length === 0)) || isLoading) return;

    // Add user message
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      // Save user message to database - use file upload endpoint if files present
      let savedUserMessage;
      if (files && files.length > 0) {
        savedUserMessage = await chatConversationsService.createMessageWithFiles(
          text,
          files,
          currentConversationId || undefined
        );
      } else {
        savedUserMessage = await chatConversationsService.createMessage({
          conversation_id: currentConversationId || undefined,
          role: 'user',
          content: text,
        });
      }

      // Update conversation ID if it was just created
      if (!currentConversationId && savedUserMessage.conversation_id) {
        setCurrentConversationId(savedUserMessage.conversation_id);
        onConversationCreated?.(savedUserMessage.conversation_id);
      }

      // Get AI response via streaming
      const stream = await chatService.sendMessage(text, modelId);
      const reader = stream.getReader();
      const decoder = new TextDecoder();

      let assistantMessage = '';
      const assistantId = `assistant-${Date.now()}`;

      // Create initial assistant message
      const initialAssistantMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        text: '',
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, initialAssistantMessage]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        assistantMessage += chunk;

        // Update the assistant message incrementally
        setMessages((prev) => {
          const newMessages = [...prev];
          const lastIndex = newMessages.length - 1;
          if (newMessages[lastIndex]?.id === assistantId) {
            newMessages[lastIndex] = {
              ...newMessages[lastIndex],
              text: assistantMessage,
            };
          }
          return newMessages;
        });
      }

      // Save assistant message to database
      if (assistantMessage) {
        await chatConversationsService.createMessage({
          conversation_id: savedUserMessage.conversation_id,
          role: 'assistant',
          content: assistantMessage,
        });
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      setError(errorMessage);

      // Add error message to chat
      const errorChatMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        text: `Sorry, I encountered an error: ${errorMessage}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorChatMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, currentConversationId, onConversationCreated]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  const loadMessages = useCallback((loadedMessages: ChatMessage[]) => {
    setMessages(loadedMessages);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    loadMessages,
    conversationId: currentConversationId,
  };
}
