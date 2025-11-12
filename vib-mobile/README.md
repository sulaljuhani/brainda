# VIB Mobile App

React Native/Expo mobile application for VIB (chat-first notes, reminders & knowledge assistant).

## Features

- **Chat Interface**: Natural language interaction for creating notes, reminders, and searching
- **Offline Support**: Queue operations when offline, sync when connection returns
- **Idempotency**: Prevents duplicate data from retries using idempotency keys
- **Push Notifications**: Receive reminder notifications on your device
- **Deep Linking**: Navigate directly to reminders/notes from notifications

## Tech Stack

- React Native with Expo
- TypeScript
- React Navigation (Bottom Tabs)
- TanStack Query (React Query) for data fetching
- Axios for HTTP requests
- Expo Notifications for push notifications
- AsyncStorage for offline queue persistence

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create `.env` file:
```bash
cp .env.example .env
# Edit .env with your API URL and token
```

3. Start the development server:
```bash
npm start
```

4. Run on device/simulator:
```bash
# iOS
npm run ios

# Android
npm run android
```

## Project Structure

```
vib-mobile/
├── App.tsx                 # Main app entry with navigation
├── src/
│   ├── lib/
│   │   ├── api.ts         # API client with idempotency
│   │   ├── offline-queue.ts   # Offline operation queue
│   │   └── notifications.ts   # Push notification setup
│   └── screens/
│       ├── ChatScreen.tsx     # Chat interface
│       ├── RemindersScreen.tsx # Reminders list
│       └── NotesScreen.tsx    # Notes list
├── app.json               # Expo configuration
├── package.json          # Dependencies
└── tsconfig.json         # TypeScript config
```

## Key Features

### Idempotency
All state-changing operations (POST, PATCH, PUT, DELETE) automatically include an `Idempotency-Key` header. This prevents duplicate reminders/notes from being created when retrying failed requests.

### Offline Queue
When the device is offline, operations are queued locally using AsyncStorage. When the connection returns, the queue is automatically processed with retry logic:
- Max 5 retries for network errors
- Removes permanently failed requests (4xx errors)
- Preserves idempotency keys for reliable sync

### Push Notifications
The app registers for push notifications and handles them in all states:
- **Foreground**: Shows in-app alert
- **Background**: Shows system notification
- **Killed**: Shows notification, opens app on tap

Notification actions:
- Snooze 15 minutes
- Mark as done
- Deep link to reminder/note

## Deep Linking

The app supports these URL schemes:
- `vib://reminders/{id}` - Open reminder details
- `vib://notes/{id}` - Open note details
- `vib://chat` - Open chat screen

## Building for Production

1. Configure your `app.json` with proper bundle identifiers
2. Build with EAS:

```bash
# Install EAS CLI
npm install -g eas-cli

# Build for iOS
eas build --platform ios

# Build for Android
eas build --platform android
```

3. Submit to app stores:
```bash
eas submit --platform ios
eas submit --platform android
```

## Environment Variables

- `EXPO_PUBLIC_API_URL`: Backend API URL (default: http://localhost:8000/api/v1)
- `EXPO_PUBLIC_API_TOKEN`: API authentication token

## Testing

To test offline functionality:
1. Enable airplane mode on your device
2. Create a reminder or note
3. Check that it's queued (you'll see a "queued" message)
4. Disable airplane mode
5. The operation should automatically sync

## Notes

- This app requires the VIB backend to be running
- Push notifications only work on physical devices, not simulators
- Deep linking requires proper URL scheme configuration in `app.json`
