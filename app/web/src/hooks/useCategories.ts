import { useState, useEffect } from 'react';
import { apiClient } from '@services/apiClient';
import type { Category, CreateCategoryRequest, UpdateCategoryRequest } from '@/types';

type CategoryType = 'tasks' | 'events' | 'reminders';

export function useCategories(type: CategoryType) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCategories = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.get<Category[]>(`/categories/${type}`);
      setCategories(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch categories');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCategories();
  }, [type]);

  const createCategory = async (data: CreateCategoryRequest) => {
    const response = await apiClient.post<{ success: boolean; data: Category }>(
      `/categories/${type}`,
      data
    );
    if (response.success && response.data) {
      setCategories((prev) => [...prev, response.data!].sort((a, b) => a.name.localeCompare(b.name)));
      return response.data;
    }
    throw new Error('Failed to create category');
  };

  const updateCategory = async (id: string, data: UpdateCategoryRequest) => {
    const response = await apiClient.patch<{ success: boolean; data: Category }>(
      `/categories/${type}/${id}`,
      data
    );
    if (response.success && response.data) {
      setCategories((prev) =>
        prev.map((c) => (c.id === id ? response.data! : c)).sort((a, b) => a.name.localeCompare(b.name))
      );
      return response.data;
    }
    throw new Error('Failed to update category');
  };

  const deleteCategory = async (id: string) => {
    await apiClient.delete(`/categories/${type}/${id}`);
    setCategories((prev) => prev.filter((c) => c.id !== id));
  };

  return {
    categories,
    loading,
    error,
    createCategory,
    updateCategory,
    deleteCategory,
    refetch: fetchCategories,
  };
}
