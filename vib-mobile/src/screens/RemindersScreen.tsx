import React from 'react';
import {
  View,
  Text,
  FlatList,
  Button,
  StyleSheet,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';

interface Reminder {
  id: string;
  title: string;
  body?: string;
  due_at_utc: string;
  due_at_local: string;
  timezone: string;
  status: string;
  created_at: string;
}

export default function RemindersScreen() {
  const queryClient = useQueryClient();

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['reminders'],
    queryFn: async () => {
      const response = await api.get('/reminders');
      return response.data.data || [];
    },
  });

  const updateReminder = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: string }) => {
      const response = await api.patch(`/reminders/${id}`, { status });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminders'] });
    },
  });

  const snoozeReminder = useMutation({
    mutationFn: async ({ id, minutes }: { id: string; minutes: number }) => {
      const response = await api.post(`/reminders/${id}/snooze`, {
        duration_minutes: minutes,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminders'] });
    },
  });

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const renderItem = ({ item }: { item: Reminder }) => {
    const isPast = new Date(item.due_at_utc) < new Date();
    const isActive = item.status === 'active';

    return (
      <View style={[styles.reminderCard, !isActive && styles.inactiveCard]}>
        <View style={styles.reminderHeader}>
          <Text style={styles.reminderTitle}>{item.title}</Text>
          <Text style={[styles.status, styles[`status_${item.status}`]]}>
            {item.status}
          </Text>
        </View>

        {item.body && <Text style={styles.reminderBody}>{item.body}</Text>}

        <View style={styles.reminderMeta}>
          <Text style={[styles.dueDate, isPast && styles.pastDue]}>
            {isPast ? '⚠️ ' : '🕐 '}
            {formatDate(item.due_at_utc)}
          </Text>
          <Text style={styles.timezone}>{item.timezone}</Text>
        </View>

        {isActive && (
          <View style={styles.actions}>
            <TouchableOpacity
              style={styles.actionButton}
              onPress={() => snoozeReminder.mutate({ id: item.id, minutes: 15 })}
            >
              <Text style={styles.actionButtonText}>Snooze 15m</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.actionButton, styles.doneButton]}
              onPress={() => updateReminder.mutate({ id: item.id, status: 'done' })}
            >
              <Text style={styles.actionButtonText}>✓ Done</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    );
  };

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <Text>Loading reminders...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={data}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No reminders yet</Text>
            <Text style={styles.emptySubtext}>
              Create one in the Chat tab!
            </Text>
          </View>
        }
      />

      <View style={styles.footer}>
        <Button title="Refresh" onPress={() => refetch()} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  list: {
    padding: 16,
  },
  reminderCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#e0e0e0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 2,
  },
  inactiveCard: {
    opacity: 0.6,
  },
  reminderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  reminderTitle: {
    fontSize: 17,
    fontWeight: '600',
    flex: 1,
    marginRight: 8,
  },
  status: {
    fontSize: 11,
    fontWeight: '600',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    overflow: 'hidden',
    textTransform: 'uppercase',
  },
  status_active: {
    backgroundColor: '#e3f2fd',
    color: '#1976d2',
  },
  status_done: {
    backgroundColor: '#e8f5e9',
    color: '#388e3c',
  },
  status_snoozed: {
    backgroundColor: '#fff3e0',
    color: '#f57c00',
  },
  reminderBody: {
    fontSize: 14,
    color: '#666',
    marginBottom: 12,
  },
  reminderMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  dueDate: {
    fontSize: 14,
    color: '#444',
    fontWeight: '500',
  },
  pastDue: {
    color: '#d32f2f',
  },
  timezone: {
    fontSize: 12,
    color: '#999',
  },
  actions: {
    flexDirection: 'row',
    gap: 8,
  },
  actionButton: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: '#f0f0f0',
    alignItems: 'center',
  },
  doneButton: {
    backgroundColor: '#e8f5e9',
  },
  actionButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  footer: {
    padding: 16,
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 64,
  },
  emptyText: {
    fontSize: 18,
    color: '#666',
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#999',
  },
});
