import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';
import { v4 as uuidv4 } from 'uuid';
import api from './api';

interface QueuedRequest {
  id: string;
  method: string;
  url: string;
  data: any;
  headers: Record<string, string>;
  idempotencyKey: string;
  createdAt: number;
  retries: number;
}

class OfflineQueue {
  private queue: QueuedRequest[] = [];
  private processing = false;
  private readonly MAX_QUEUE_SIZE = 100;
  private readonly MAX_RETRIES = 5;

  async init() {
    // Load queue from storage
    const stored = await AsyncStorage.getItem('offline_queue');
    if (stored) {
      try {
        this.queue = JSON.parse(stored);
        console.log(`Loaded ${this.queue.length} queued requests from storage`);
      } catch (error) {
        console.error('Failed to parse offline queue:', error);
        this.queue = [];
      }
    }

    // Listen for connectivity changes
    NetInfo.addEventListener(state => {
      if (state.isConnected) {
        console.log('Network connected, processing queue...');
        this.processQueue();
      }
    });

    // Process queue if we're already online
    const netInfo = await NetInfo.fetch();
    if (netInfo.isConnected) {
      this.processQueue();
    }
  }

  async enqueue(method: string, url: string, data: any): Promise<string> {
    // Check queue size limit
    if (this.queue.length >= this.MAX_QUEUE_SIZE) {
      // Remove oldest item
      this.queue.shift();
      console.warn('Queue full, removed oldest item');
    }

    const idempotencyKey = uuidv4();

    const request: QueuedRequest = {
      id: uuidv4(),
      method,
      url,
      data,
      headers: { 'Idempotency-Key': idempotencyKey },
      idempotencyKey,
      createdAt: Date.now(),
      retries: 0,
    };

    this.queue.push(request);
    await this.saveQueue();

    console.log(`Queued request: ${method} ${url} (${this.queue.length} in queue)`);

    // Try processing immediately
    this.processQueue();

    return idempotencyKey;
  }

  async processQueue() {
    if (this.processing || this.queue.length === 0) {
      return;
    }

    const netInfo = await NetInfo.fetch();
    if (!netInfo.isConnected) {
      console.log('No network connection, queue processing postponed');
      return;
    }

    this.processing = true;
    console.log(`Processing queue with ${this.queue.length} items...`);

    while (this.queue.length > 0) {
      const request = this.queue[0];

      try {
        console.log(`Sending queued request: ${request.method} ${request.url}`);

        await api.request({
          method: request.method,
          url: request.url,
          data: request.data,
          headers: request.headers,
        });

        console.log(`✓ Request succeeded: ${request.method} ${request.url}`);

        // Success: remove from queue
        this.queue.shift();
        await this.saveQueue();
      } catch (error: any) {
        request.retries++;

        const isClientError = error.response?.status >= 400 && error.response?.status < 500;
        const maxRetriesExceeded = request.retries >= this.MAX_RETRIES;

        if (maxRetriesExceeded || isClientError) {
          // Remove permanently failed requests
          console.error(
            `✗ Request failed permanently (${isClientError ? 'client error' : 'max retries'}):`,
            request.method,
            request.url,
            error.message
          );
          this.queue.shift();
          await this.saveQueue();
        } else {
          // Retry later
          console.warn(
            `✗ Request failed (attempt ${request.retries}/${this.MAX_RETRIES}):`,
            request.method,
            request.url,
            error.message
          );
          await this.saveQueue();
          break; // Stop processing, will retry later
        }
      }
    }

    this.processing = false;

    if (this.queue.length === 0) {
      console.log('Queue processing complete, all requests sent');
    } else {
      console.log(`Queue processing paused, ${this.queue.length} items remaining`);
    }
  }

  async saveQueue() {
    try {
      await AsyncStorage.setItem('offline_queue', JSON.stringify(this.queue));
    } catch (error) {
      console.error('Failed to save offline queue:', error);
    }
  }

  async clearQueue() {
    this.queue = [];
    await this.saveQueue();
    console.log('Queue cleared');
  }

  getQueueLength(): number {
    return this.queue.length;
  }

  getQueue(): QueuedRequest[] {
    return [...this.queue];
  }
}

export default new OfflineQueue();
