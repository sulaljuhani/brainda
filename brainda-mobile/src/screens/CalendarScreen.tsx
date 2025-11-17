import React, { useMemo, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { addWeeks, eachDayOfInterval, endOfWeek, format, isSameDay, startOfWeek } from 'date-fns';

import api from '../lib/api';

interface CalendarEvent {
  id: string;
  title: string;
  starts_at: string;
  location_text?: string | null;
  is_recurring_instance?: boolean;
}

interface CalendarResponse {
  data?: {
    events: CalendarEvent[];
  };
}

export default function CalendarScreen() {
  const [anchorDate, setAnchorDate] = useState(() => new Date());

  const weekStart = useMemo(() => startOfWeek(anchorDate, { weekStartsOn: 1 }), [anchorDate]);
  const weekEnd = useMemo(() => endOfWeek(anchorDate, { weekStartsOn: 1 }), [anchorDate]);
  const isoStart = useMemo(() => weekStart.toISOString(), [weekStart]);
  const isoEnd = useMemo(() => weekEnd.toISOString(), [weekEnd]);
  const days = useMemo(() => eachDayOfInterval({ start: weekStart, end: weekEnd }), [weekStart, weekEnd]);

  const { data, isLoading, refetch, isFetching, error } = useQuery<CalendarResponse>({
    queryKey: ['calendar-events', isoStart, isoEnd],
    queryFn: async () => {
      const response = await api.get('/calendar/events', {
        params: {
          start: isoStart,
          end: isoEnd,
        },
      });
      return response.data;
    },
    staleTime: 1000 * 30,
  });

  const events = data?.data?.events ?? [];

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => setAnchorDate(addWeeks(weekStart, -1))}>
          <Text style={styles.link}>← Previous</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>
          {format(weekStart, 'MMM d')} - {format(weekEnd, 'MMM d, yyyy')}
        </Text>
        <TouchableOpacity onPress={() => setAnchorDate(addWeeks(weekStart, 1))}>
          <Text style={styles.link}>Next →</Text>
        </TouchableOpacity>
      </View>

      {isLoading ? (
        <View style={styles.loadingContainer}>
          <Text style={styles.loadingText}>Loading events…</Text>
        </View>
      ) : error ? (
        <View style={styles.loadingContainer}>
          <Text style={styles.errorText}>Unable to load events</Text>
        </View>
      ) : (
        <ScrollView
          refreshControl={<RefreshControl refreshing={isFetching} onRefresh={refetch} />}>
          {days.map((day) => {
            const dayEvents = events.filter((event) => isSameDay(new Date(event.starts_at), day));

            return (
              <View key={day.toISOString()} style={styles.daySection}>
                <Text style={styles.dayTitle}>{format(day, 'EEEE, MMM d')}</Text>
                {dayEvents.length === 0 ? (
                  <Text style={styles.emptyText}>No events</Text>
                ) : (
                  dayEvents.map((event) => (
                    <View
                      key={`${event.id}-${event.starts_at}`}
                      style={[
                        styles.eventCard,
                        event.is_recurring_instance ? styles.recurringEvent : null,
                      ]}
                    >
                      <Text style={styles.eventTitle}>
                        {format(new Date(event.starts_at), 'HH:mm')} - {event.title}
                      </Text>
                      {event.location_text ? (
                        <Text style={styles.eventLocation}>📍 {event.location_text}</Text>
                      ) : null}
                    </View>
                  ))
                )}
              </View>
            );
          })}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#fff',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#ddd',
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  link: {
    color: '#1976d2',
    fontWeight: '500',
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    color: '#666',
  },
  errorText: {
    color: '#d32f2f',
    fontWeight: '500',
  },
  daySection: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#e0e0e0',
    backgroundColor: '#fff',
  },
  dayTitle: {
    fontWeight: '700',
    fontSize: 15,
    marginBottom: 8,
  },
  emptyText: {
    color: '#999',
  },
  eventCard: {
    backgroundColor: '#e3f2fd',
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
  },
  recurringEvent: {
    backgroundColor: '#f3e5f5',
  },
  eventTitle: {
    fontWeight: '600',
    marginBottom: 4,
  },
  eventLocation: {
    color: '#555',
  },
});
