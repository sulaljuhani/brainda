// Service worker for Web Push
self.addEventListener('push', function(event) {
  const data = event.data.json();
  
  const options = {
    body: data.body,
    icon: '/icon.png',
    badge: '/badge.png',
    data: data.data,
    actions: data.actions || [],
    tag: data.collapse_key,
    requireInteraction: true
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Get API token from IndexedDB
async function getApiToken() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('brainda-auth', 1);

    request.onerror = () => reject(request.error);

    request.onsuccess = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains('tokens')) {
        resolve(null);
        return;
      }

      const transaction = db.transaction(['tokens'], 'readonly');
      const store = transaction.objectStore('tokens');

      const resolveWithFallback = () => {
        const legacyRequest = store.get('api_token');
        legacyRequest.onsuccess = () => resolve(legacyRequest.result?.value);
        legacyRequest.onerror = () => reject(legacyRequest.error);
      };

      const sessionRequest = store.get('session_token');
      sessionRequest.onsuccess = () => {
        const token = sessionRequest.result?.value;
        if (token) {
          resolve(token);
        } else {
          resolveWithFallback();
        }
      };
      sessionRequest.onerror = () => {
        resolveWithFallback();
      };
    };

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('tokens')) {
        db.createObjectStore('tokens', { keyPath: 'key' });
      }
    };
  });
}

self.addEventListener('notificationclick', function(event) {
  event.notification.close();

  const action = event.action;
  const data = event.notification.data;

  if (action === 'snooze_15m') {
    // Call API to snooze with authentication
    event.waitUntil(
      getApiToken().then(token => {
        if (!token) {
          console.error('No API token available for service worker');
          return;
        }

        return fetch(`/api/v1/reminders/${data.reminder_id}/snooze`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ duration_minutes: 15 })
        }).catch(err => console.error('Failed to snooze reminder:', err));
      })
    );
  } else if (action === 'done') {
    // Mark as done with authentication
    event.waitUntil(
      getApiToken().then(token => {
        if (!token) {
          console.error('No API token available for service worker');
          return;
        }

        return fetch(`/api/v1/reminders/${data.reminder_id}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }).catch(err => console.error('Failed to delete reminder:', err));
      })
    );
  } else {
    // Open app
    event.waitUntil(
      clients.openWindow(data.deep_link || '/')
    );
  }
});
