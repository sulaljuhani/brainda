import React, { useState } from 'react';
import {
  View,
  TextInput,
  Button,
  ScrollView,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { useMutation } from '@tanstack/react-query';
import api from '../lib/api';
import offlineQueue from '../lib/offline-queue';
import NetInfo from '@react-native-community/netinfo';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  mode?: string;
  data?: any;
}

export default function ChatScreen() {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);

  const sendMessage = useMutation({
    mutationFn: async (text: string) => {
      const netInfo = await NetInfo.fetch();

      if (!netInfo.isConnected) {
        // Queue for offline sync
        await offlineQueue.enqueue('POST', '/chat', { message: text });
        return {
          mode: 'offline',
          message: 'Message queued for sending when online',
        };
      }

      try {
        const response = await api.post('/chat', { message: text });
        return response.data;
      } catch (error: any) {
        // If network error, queue for retry
        if (!error.response) {
          await offlineQueue.enqueue('POST', '/chat', { message: text });
          throw new Error('Network error - message queued for retry');
        }
        throw error;
      }
    },
    onSuccess: (data) => {
      // Add user message
      setMessages(prev => [
        ...prev,
        { role: 'user', content: message },
        { role: 'assistant', content: data.message, mode: data.mode, data: data.data },
      ]);
      setMessage('');
    },
    onError: (error: any) => {
      // Show error in chat
      setMessages(prev => [
        ...prev,
        { role: 'user', content: message },
        { role: 'assistant', content: `Error: ${error.message}` },
      ]);
      setMessage('');
    },
  });

  const handleSend = () => {
    if (!message.trim()) return;
    sendMessage.mutate(message);
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={90}
    >
      <ScrollView
        style={styles.messagesContainer}
        contentContainerStyle={styles.messagesContent}
      >
        {messages.length === 0 && (
          <Text style={styles.emptyText}>
            Start chatting! Try:{'\n'}
            • "Remind me to call mom at 5pm"{'\n'}
            • "Create a note titled Ideas"{'\n'}
            • "Search for project documents"
          </Text>
        )}
        {messages.map((msg, i) => (
          <View
            key={i}
            style={[
              styles.messageBubble,
              msg.role === 'user' ? styles.userBubble : styles.assistantBubble,
            ]}
          >
            <Text style={styles.messageRole}>
              {msg.role === 'user' ? '👤 You' : '🤖 Assistant'}
            </Text>
            <Text style={styles.messageContent}>{msg.content}</Text>
            {msg.mode && (
              <Text style={styles.messageMode}>Mode: {msg.mode}</Text>
            )}
          </View>
        ))}
      </ScrollView>

      <View style={styles.inputContainer}>
        <TextInput
          value={message}
          onChangeText={setMessage}
          placeholder="Type a message..."
          style={styles.input}
          multiline
          maxLength={500}
          editable={!sendMessage.isPending}
        />
        <Button
          title={sendMessage.isPending ? '...' : 'Send'}
          onPress={handleSend}
          disabled={sendMessage.isPending || !message.trim()}
        />
      </View>

      {sendMessage.isPending && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  messagesContainer: {
    flex: 1,
  },
  messagesContent: {
    padding: 16,
    paddingBottom: 8,
  },
  emptyText: {
    textAlign: 'center',
    color: '#666',
    fontSize: 14,
    marginTop: 32,
    lineHeight: 22,
  },
  messageBubble: {
    marginBottom: 12,
    padding: 12,
    borderRadius: 12,
    maxWidth: '85%',
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: '#007AFF',
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  messageRole: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
    color: '#666',
  },
  messageContent: {
    fontSize: 15,
    lineHeight: 20,
  },
  messageMode: {
    fontSize: 11,
    color: '#999',
    marginTop: 4,
    fontStyle: 'italic',
  },
  inputContainer: {
    flexDirection: 'row',
    padding: 12,
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
    gap: 8,
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    padding: 10,
    fontSize: 15,
    maxHeight: 100,
  },
  loadingOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
  },
});
