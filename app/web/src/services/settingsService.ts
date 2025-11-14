import { api } from './api';
import type {
  UserSettings,
  UpdateProfileRequest,
  ChangePasswordRequest,
  GoogleCalendarSettings,
  OpenMemorySettings,
} from '@types/*';

class SettingsService {
  // User settings
  async getUserSettings(): Promise<UserSettings> {
    return api.get<UserSettings>('/settings');
  }

  async updateUserSettings(settings: Partial<UserSettings>): Promise<UserSettings> {
    return api.put<UserSettings>('/settings', settings);
  }

  // Profile
  async updateProfile(data: UpdateProfileRequest): Promise<void> {
    return api.put<void>('/user/profile', data);
  }

  // Security
  async changePassword(data: ChangePasswordRequest): Promise<void> {
    return api.post<void>('/user/change-password', data);
  }

  // Google Calendar
  async getGoogleCalendarSettings(): Promise<GoogleCalendarSettings> {
    return api.get<GoogleCalendarSettings>('/calendar/google/settings');
  }

  async connectGoogleCalendar(): Promise<{ auth_url: string }> {
    return api.get<{ auth_url: string }>('/calendar/google/connect');
  }

  async disconnectGoogleCalendar(): Promise<void> {
    return api.post<void>('/calendar/google/disconnect');
  }

  async updateGoogleCalendarSync(enabled: boolean): Promise<void> {
    return api.put<void>('/calendar/google/settings', { sync_enabled: enabled });
  }

  // OpenMemory
  async getOpenMemorySettings(): Promise<OpenMemorySettings> {
    return api.get<OpenMemorySettings>('/memory/settings');
  }

  async updateOpenMemorySettings(settings: Partial<OpenMemorySettings>): Promise<OpenMemorySettings> {
    return api.put<OpenMemorySettings>('/memory/settings', settings);
  }
}

export const settingsService = new SettingsService();
