import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform, Linking } from 'react-native';
import api from './api';

// Configure notification handler
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotifications(): Promise<string | null> {
  if (!Device.isDevice) {
    console.log('Push notifications only work on physical devices');
    return null;
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    console.log('Push permission denied');
    return null;
  }

  try {
    const token = (await Notifications.getExpoPushTokenAsync()).data;

    // Register with backend
    await api.post('/devices/register', {
      platform: Platform.OS,
      push_token: token,
    });

    console.log('Push token registered:', token);
    return token;
  } catch (error) {
    console.error('Failed to register push token:', error);
    return null;
  }
}

export function setupNotificationHandlers() {
  // Handle notification received while app is foregrounded
  Notifications.addNotificationReceivedListener(notification => {
    console.log('Notification received:', notification);
  });

  // Handle user tapping notification
  Notifications.addNotificationResponseReceivedListener(response => {
    const data = response.notification.request.content.data;

    console.log('Notification tapped:', data);

    // Handle actions
    if (data.action === 'snooze_15m') {
      api.post(`/reminders/${data.reminder_id}/snooze`, { duration_minutes: 15 })
        .then(() => console.log('Reminder snoozed'))
        .catch(error => console.error('Failed to snooze:', error));
    } else if (data.action === 'done') {
      api.patch(`/reminders/${data.reminder_id}`, { status: 'done' })
        .then(() => console.log('Reminder marked as done'))
        .catch(error => console.error('Failed to mark as done:', error));
    } else if (data.deep_link) {
      // Navigate to deep link
      Linking.openURL(data.deep_link)
        .catch(error => console.error('Failed to open deep link:', error));
    }
  });
}

export async function scheduleLocalNotification(
  title: string,
  body: string,
  trigger: Date | { seconds: number },
  data?: any
) {
  try {
    const id = await Notifications.scheduleNotificationAsync({
      content: {
        title,
        body,
        data,
      },
      trigger,
    });
    console.log('Local notification scheduled:', id);
    return id;
  } catch (error) {
    console.error('Failed to schedule local notification:', error);
    return null;
  }
}

export async function cancelAllNotifications() {
  await Notifications.cancelAllScheduledNotificationsAsync();
  console.log('All scheduled notifications cancelled');
}
