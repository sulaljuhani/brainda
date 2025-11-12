import axios, { AxiosRequestConfig } from 'axios';
import { v4 as uuidv4 } from 'uuid';
import * as SecureStore from 'expo-secure-store';

const api = axios.create({
  baseURL: process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
});

// Add auth token
api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Add idempotency key for state-changing operations
api.interceptors.request.use((config) => {
  const methods = ['POST', 'PATCH', 'PUT', 'DELETE'];
  if (methods.includes(config.method?.toUpperCase() || '')) {
    // Generate idempotency key if not provided
    if (!config.headers['Idempotency-Key']) {
      config.headers['Idempotency-Key'] = uuidv4();
    }
  }
  return config;
});

// Handle idempotency replays
api.interceptors.response.use((response) => {
  if (response.headers['x-idempotency-replay'] === 'true') {
    console.log('Idempotency replay detected');
  }
  return response;
});

export default api;
