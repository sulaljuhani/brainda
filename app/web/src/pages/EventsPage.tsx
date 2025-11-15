import { useState } from 'react';
import { useEvents } from '@hooks/useEvents';
import { EventForm } from '@components/calendar/EventForm';
import type { CalendarEvent, CreateEventRequest } from '@/types';
import styles from './EventsPage.module.css';

export default function EventsPage() {
  const [isEventFormOpen, setIsEventFormOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Fetch upcoming events
  const {
    events: upcomingEvents,
    loading: upcomingLoading,
    createEvent: createUpcoming,
    updateEvent: updateUpcoming,
    deleteEvent: deleteUpcoming,
  } = useEvents({ status: 'upcoming' });

  // Fetch past events
  const {
    events: pastEvents,
    loading: pastLoading,
  } = useEvents({ status: 'past' });

  const loading = upcomingLoading || pastLoading;

  const handleCreateEvent = async (data: CreateEventRequest) => {
    try {
      await createUpcoming(data);
      setIsEventFormOpen(false);
    } catch (err) {
      console.error('Failed to create event:', err);
      throw err;
    }
  };

  const handleUpdateEvent = async (data: CreateEventRequest) => {
    if (!editingEvent) return;

    try {
      await updateUpcoming(editingEvent.id, data);
      setEditingEvent(null);
      setIsEventFormOpen(false);
    } catch (err) {
      console.error('Failed to update event:', err);
      throw err;
    }
  };

  const handleDelete = async (id: string) => {
    if (deletingId !== id) {
      setDeletingId(id);
      setTimeout(() => setDeletingId(null), 3000);
      return;
    }

    try {
      await deleteUpcoming(id);
      setDeletingId(null);
    } catch (err) {
      console.error('Failed to delete event:', err);
      alert('Failed to delete event. Please try again.');
    }
  };

  const openCreateForm = () => {
    setEditingEvent(null);
    setIsEventFormOpen(true);
  };

  const openEditForm = (event: CalendarEvent) => {
    setEditingEvent(event);
    setIsEventFormOpen(true);
  };

  const closeForm = () => {
    setIsEventFormOpen(false);
    setEditingEvent(null);
  };

  const formatEventDate = (event: CalendarEvent): string => {
    const start = new Date(event.starts_at);
    const options: Intl.DateTimeFormatOptions = {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    };

    let dateStr = start.toLocaleDateString('en-US', options);

    if (event.ends_at) {
      const end = new Date(event.ends_at);
      const isSameDay =
        start.toDateString() === end.toDateString();

      if (isSameDay) {
        dateStr += ` - ${end.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
        })}`;
      } else {
        dateStr += ` - ${end.toLocaleDateString('en-US', options)}`;
      }
    }

    return dateStr;
  };

  const renderEventCard = (event: CalendarEvent) => (
    <div key={event.id} className={styles.eventCard}>
      <div className={styles.eventMain}>
        {event.category_id && (
          <div
            className={styles.categoryIndicator}
            style={{
              backgroundColor: event.category_id
                ? `var(--category-${event.category_id}, #ccc)`
                : '#ccc',
            }}
          />
        )}
        <div className={styles.eventContent}>
          <div className={styles.eventHeader}>
            <h3 className={styles.eventTitle}>{event.title}</h3>
            {event.rrule && (
              <span className={styles.recurringBadge}>Recurring</span>
            )}
          </div>

          {event.description && (
            <p className={styles.eventDescription}>{event.description}</p>
          )}

          <div className={styles.eventMeta}>
            <span className={styles.eventDate}>{formatEventDate(event)}</span>
            {event.location_text && (
              <>
                <span className={styles.metaDivider}>•</span>
                <span className={styles.eventLocation}>{event.location_text}</span>
              </>
            )}
            {event.category_name && (
              <>
                <span className={styles.metaDivider}>•</span>
                <span className={styles.categoryName}>{event.category_name}</span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className={styles.eventActions}>
        <button
          className={styles.actionButton}
          onClick={() => openEditForm(event)}
        >
          Edit
        </button>
        <button
          className={`${styles.deleteButton} ${
            deletingId === event.id ? styles.deleteConfirm : ''
          }`}
          onClick={() => handleDelete(event.id)}
        >
          {deletingId === event.id ? 'Confirm?' : 'Delete'}
        </button>
      </div>
    </div>
  );

  return (
    <div className={styles.eventsPage}>
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <h1 className={styles.title}>Events</h1>
          <p className={styles.subtitle}>Manage your calendar events</p>
        </div>
        <button className={styles.createBtn} onClick={openCreateForm}>
          <span>+</span>
          New Event
        </button>
      </div>

      <div className={styles.content}>
        {loading ? (
          <div className={styles.loadingState}>
            <div className={styles.spinner} />
            <p>Loading events...</p>
          </div>
        ) : (
          <>
            {/* Upcoming Events Section */}
            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>
                Upcoming Events
                {upcomingEvents.length > 0 && (
                  <span className={styles.sectionCount}>
                    ({upcomingEvents.length})
                  </span>
                )}
              </h2>

              {upcomingEvents.length === 0 ? (
                <div className={styles.emptyState}>
                  <p>No upcoming events</p>
                  <button className={styles.emptyActionBtn} onClick={openCreateForm}>
                    Create your first event
                  </button>
                </div>
              ) : (
                <div className={styles.eventList}>
                  {upcomingEvents.map(renderEventCard)}
                </div>
              )}
            </section>

            {/* Past Events Section */}
            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>
                Past Events
                {pastEvents.length > 0 && (
                  <span className={styles.sectionCount}>
                    ({pastEvents.length})
                  </span>
                )}
              </h2>

              {pastEvents.length === 0 ? (
                <div className={styles.emptyState}>
                  <p>No past events</p>
                </div>
              ) : (
                <div className={styles.eventList}>
                  {pastEvents.map(renderEventCard)}
                </div>
              )}
            </section>
          </>
        )}
      </div>

      <EventForm
        isOpen={isEventFormOpen}
        onClose={closeForm}
        onSubmit={editingEvent ? handleUpdateEvent : handleCreateEvent}
        event={editingEvent}
      />
    </div>
  );
}
