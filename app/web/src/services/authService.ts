import { api } from './api';
import type { User } from '@types/api';

export interface LoginResponse {
  success: boolean;
  session_token: string;
  expires_at: string;
  user: {
    id: string;
    username: string;
    email?: string;
    display_name?: string;
  };
}

export interface RegisterResponse {
  success: boolean;
  session_token: string;
  expires_at: string;
  user: {
    id: string;
    username: string;
    email?: string;
    display_name?: string;
  };
}

class AuthService {
  /**
   * Get current user profile
   */
  async getCurrentUser(): Promise<User> {
    return api.get<User>('/auth/users/me');
  }

  /**
   * Register a new user with username and password
   */
  async register(
    username: string,
    password: string,
    email?: string,
    displayName?: string
  ): Promise<RegisterResponse> {
    return api.post<RegisterResponse>('/auth/register', {
      username,
      password,
      email,
      display_name: displayName,
    });
  }

  /**
   * Login with username and password
   */
  async login(username: string, password: string): Promise<LoginResponse> {
    return api.post<LoginResponse>('/auth/login', {
      username,
      password,
    });
  }

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
      // Continue with local logout even if API call fails
    } finally {
      // Clear local storage
      localStorage.removeItem('session_token');
      localStorage.removeItem('api_token');
    }
  }

  /**
   * Check if user is authenticated by validating session token
   */
  async validateSession(): Promise<User | null> {
    const token = localStorage.getItem('session_token');
    if (!token) {
      return null;
    }

    try {
      const user = await this.getCurrentUser();
      return user;
    } catch (error) {
      // Token is invalid, clear it
      localStorage.removeItem('session_token');
      return null;
    }
  }
}

export const authService = new AuthService();
