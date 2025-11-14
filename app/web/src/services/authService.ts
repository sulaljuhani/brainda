import { api } from './api';
import type { User, Session } from '@types/api';

export interface PasskeyRegisterBeginResponse {
  user_id: string;
  options: string; // JSON string of WebAuthn options
}

export interface PasskeyLoginBeginResponse {
  challenge_id: string;
  options: string; // JSON string of WebAuthn options
}

export interface LoginResponse {
  success: boolean;
  session_token: string;
  expires_at: string;
}

export interface RegisterCompleteResponse {
  success: boolean;
  message: string;
}

class AuthService {
  /**
   * Get current user profile
   */
  async getCurrentUser(): Promise<User> {
    return api.get<User>('/auth/users/me');
  }

  /**
   * Begin passkey registration flow
   */
  async beginPasskeyRegistration(
    email: string,
    displayName: string
  ): Promise<PasskeyRegisterBeginResponse> {
    return api.post<PasskeyRegisterBeginResponse>('/auth/register/begin', {
      email,
      display_name: displayName,
    });
  }

  /**
   * Complete passkey registration
   */
  async completePasskeyRegistration(
    userId: string,
    credential: any,
    deviceName?: string
  ): Promise<RegisterCompleteResponse> {
    return api.post<RegisterCompleteResponse>('/auth/register/complete', {
      user_id: userId,
      credential,
      device_name: deviceName,
    });
  }

  /**
   * Begin passkey login flow
   */
  async beginPasskeyLogin(): Promise<PasskeyLoginBeginResponse> {
    return api.post<PasskeyLoginBeginResponse>('/auth/login/begin');
  }

  /**
   * Complete passkey login
   */
  async completePasskeyLogin(
    challengeId: string,
    credential: any
  ): Promise<LoginResponse> {
    return api.post<LoginResponse>('/auth/login/complete', {
      challenge_id: challengeId,
      credential,
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

  /**
   * Helper to check if WebAuthn is supported
   */
  isWebAuthnSupported(): boolean {
    return (
      window.PublicKeyCredential !== undefined &&
      typeof window.PublicKeyCredential === 'function'
    );
  }

  /**
   * Helper to check if platform authenticator is available (biometrics)
   */
  async isPlatformAuthenticatorAvailable(): Promise<boolean> {
    if (!this.isWebAuthnSupported()) {
      return false;
    }

    try {
      return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    } catch {
      return false;
    }
  }
}

export const authService = new AuthService();
