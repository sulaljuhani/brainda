import { useState, useEffect } from 'react';
import { apiClient } from '@services/apiClient';
import type { Task, CreateTaskRequest, UpdateTaskRequest } from '@/types';

interface UseTasksOptions {
  status?: 'active' | 'completed' | 'cancelled';
  includeSubtasks?: boolean;
  categoryId?: string;
}

export function useTasks(options: UseTasksOptions = {}) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (options.status) params.append('status', options.status);
      if (options.includeSubtasks !== undefined) {
        params.append('include_subtasks', String(options.includeSubtasks));
      }
      if (options.categoryId) params.append('category_id', options.categoryId);

      const response = await apiClient.get<Task[]>(`/tasks?${params.toString()}`);
      setTasks(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch tasks');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [options.status, options.includeSubtasks, options.categoryId]);

  const createTask = async (data: CreateTaskRequest) => {
    const response = await apiClient.post<{ success: boolean; data: Task }>('/tasks', data);
    if (response.success && response.data) {
      setTasks((prev) => [response.data!, ...prev]);
      return response.data;
    }
    throw new Error('Failed to create task');
  };

  const updateTask = async (id: string, data: UpdateTaskRequest) => {
    const response = await apiClient.patch<{ success: boolean; data: Task }>(
      `/tasks/${id}`,
      data
    );
    if (response.success && response.data) {
      setTasks((prev) =>
        prev.map((t) => (t.id === id ? response.data! : t))
      );
      return response.data;
    }
    throw new Error('Failed to update task');
  };

  const completeTask = async (id: string) => {
    const response = await apiClient.post<{ success: boolean; data: Task }>(
      `/tasks/${id}/complete`,
      {}
    );
    if (response.success && response.data) {
      setTasks((prev) =>
        prev.map((t) => (t.id === id ? response.data! : t))
      );
      return response.data;
    }
    throw new Error('Failed to complete task');
  };

  const deleteTask = async (id: string) => {
    await apiClient.delete(`/tasks/${id}`);
    setTasks((prev) => prev.filter((t) => t.id !== id));
  };

  const moveTask = async (taskId: string, parentTaskId: string | null) => {
    const params = new URLSearchParams();
    if (parentTaskId) params.append('parent_task_id', parentTaskId);

    const response = await apiClient.post<{ success: boolean; data: Task }>(
      `/tasks/${taskId}/move?${params.toString()}`,
      {}
    );
    if (response.success && response.data) {
      // Refetch to get updated hierarchy
      await fetchTasks();
      return response.data;
    }
    throw new Error('Failed to move task');
  };

  return {
    tasks,
    loading,
    error,
    createTask,
    updateTask,
    completeTask,
    deleteTask,
    moveTask,
    refetch: fetchTasks,
  };
}
