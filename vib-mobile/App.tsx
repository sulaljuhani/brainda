import React, { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as SecureStore from 'expo-secure-store';
import { Alert, Platform, Text } from 'react-native';

import ChatScreen from './src/screens/ChatScreen';
import RemindersScreen from './src/screens/RemindersScreen';
import NotesScreen from './src/screens/NotesScreen';
import offlineQueue from './src/lib/offline-queue';
import {
  registerForPushNotifications,
  setupNotificationHandlers,
} from './src/lib/notifications';

const Tab = createBottomTabNavigator();

// Create a QueryClient instance
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30000, // 30 seconds
    },
  },
});

// Deep linking configuration
const linking = {
  prefixes: ['vib://', 'https://vib.app'],
  config: {
    screens: {
      Chat: 'chat',
      Reminders: {
        path: 'reminders/:id?',
        parse: {
          id: (id: string) => id,
        },
      },
      Notes: {
        path: 'notes/:id?',
        parse: {
          id: (id: string) => id,
        },
      },
    },
  },
};

export default function App() {
  useEffect(() => {
    // Initialize the app
    initializeApp();
  }, []);

  const initializeApp = async () => {
    try {
      // 1. Check if auth token exists, if not create a demo one
      let token = await SecureStore.getItemAsync('auth_token');
      if (!token) {
        // For demo purposes, use a default token
        // In production, this should be obtained through proper authentication
        token = process.env.EXPO_PUBLIC_API_TOKEN || 'default-token-change-me';
        await SecureStore.setItemAsync('auth_token', token);
        console.log('Auth token set');
      }

      // 2. Initialize offline queue
      await offlineQueue.init();
      console.log('Offline queue initialized');

      // 3. Setup push notifications
      setupNotificationHandlers();
      const pushToken = await registerForPushNotifications();
      if (pushToken) {
        console.log('Push notifications registered');
      } else {
        console.log('Push notifications not available on this device');
      }
    } catch (error) {
      console.error('Failed to initialize app:', error);
      Alert.alert(
        'Initialization Error',
        'Failed to initialize the app. Please restart.'
      );
    }
  };

  return (
    <QueryClientProvider client={queryClient}>
      <NavigationContainer linking={linking}>
        <Tab.Navigator
          screenOptions={{
            tabBarActiveTintColor: '#007AFF',
            tabBarInactiveTintColor: '#8E8E93',
            headerStyle: {
              backgroundColor: '#fff',
            },
            headerTitleStyle: {
              fontWeight: '600',
            },
          }}
        >
          <Tab.Screen
            name="Chat"
            component={ChatScreen}
            options={{
              tabBarIcon: ({ color }) => <Text style={{ fontSize: 24 }}>💬</Text>,
              title: 'Chat',
            }}
          />
          <Tab.Screen
            name="Reminders"
            component={RemindersScreen}
            options={{
              tabBarIcon: ({ color }) => <Text style={{ fontSize: 24 }}>⏰</Text>,
              title: 'Reminders',
            }}
          />
          <Tab.Screen
            name="Notes"
            component={NotesScreen}
            options={{
              tabBarIcon: ({ color }) => <Text style={{ fontSize: 24 }}>📝</Text>,
              title: 'Notes',
            }}
          />
        </Tab.Navigator>
        <StatusBar style="auto" />
      </NavigationContainer>
    </QueryClientProvider>
  );
}
