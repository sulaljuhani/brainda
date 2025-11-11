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

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  
  const action = event.action;
  const data = event.notification.data;
  
  if (action === 'snooze_15m') {
    // Call API to snooze
    fetch(`/api/v1/reminders/${data.reminder_id}/snooze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ duration_minutes: 15 })
    });
  } else if (action === 'done') {
    // Mark as done
    fetch(`/api/v1/reminders/${data.reminder_id}`, {
      method: 'DELETE'
    });
  } else {
    // Open app
    event.waitUntil(
      clients.openWindow(data.deep_link || '/')
    );
  }
});
