import { useState, useCallback } from 'react';
import { chatService } from '../services/chatService';
import type { ChatMessage } from '@types/*';

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

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
      const stream = await chatService.sendMessage(text);
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
  }, [isLoading]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
  };
}
