import { useState } from 'react';
import { useCategories } from '@hooks/useCategories';
import type { Category } from '@/types';
import styles from './CategoriesPage.module.css';

type CategoryType = 'tasks' | 'events' | 'reminders';

const PRESET_COLORS = [
  '#3b82f6', // blue
  '#10b981', // green
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // purple
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#f97316', // orange
];

interface CategorySectionProps {
  type: CategoryType;
  title: string;
}

function CategorySection({ type, title }: CategorySectionProps) {
  const { categories, loading, createCategory, updateCategory, deleteCategory } =
    useCategories(type);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newCategoryColor, setNewCategoryColor] = useState(PRESET_COLORS[0]);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleStartEdit = (category: Category) => {
    setEditingId(category.id);
    setEditingName(category.name);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditingName('');
  };

  const handleSaveEdit = async (id: string, color?: string) => {
    if (!editingName.trim()) return;

    try {
      await updateCategory(id, { name: editingName, color });
      setEditingId(null);
      setEditingName('');
    } catch (err) {
      console.error('Failed to update category:', err);
    }
  };

  const handleColorChange = async (id: string, color: string) => {
    try {
      await updateCategory(id, { color });
    } catch (err) {
      console.error('Failed to update category color:', err);
    }
  };

  const handleCreate = async () => {
    if (!newCategoryName.trim()) return;

    try {
      await createCategory({
        name: newCategoryName,
        color: newCategoryColor,
      });
      setNewCategoryName('');
      setNewCategoryColor(PRESET_COLORS[0]);
    } catch (err) {
      console.error('Failed to create category:', err);
    }
  };

  const handleDelete = async (id: string) => {
    if (deletingId !== id) {
      setDeletingId(id);
      return;
    }

    try {
      await deleteCategory(id);
      setDeletingId(null);
    } catch (err) {
      console.error('Failed to delete category:', err);
    }
  };

  return (
    <div className={styles.categorySection}>
      <h2 className={styles.sectionTitle}>{title}</h2>

      {loading ? (
        <div className={styles.loading}>Loading categories...</div>
      ) : (
        <>
          <div className={styles.categoryList}>
            {categories.length === 0 ? (
              <div className={styles.empty}>No categories yet. Create one below!</div>
            ) : (
              categories.map((category) => (
                <div key={category.id} className={styles.categoryItem}>
                  <div className={styles.categoryMain}>
                    <div
                      className={styles.colorIndicator}
                      style={{ backgroundColor: category.color || '#ccc' }}
                    />
                    {editingId === category.id ? (
                      <input
                        className={styles.editInput}
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') {
                            handleSaveEdit(category.id, category.color);
                          }
                        }}
                        autoFocus
                      />
                    ) : (
                      <span
                        className={styles.categoryName}
                        onClick={() => handleStartEdit(category)}
                      >
                        {category.name}
                      </span>
                    )}
                  </div>

                  <div className={styles.categoryActions}>
                    {editingId === category.id ? (
                      <>
                        <button
                          className={styles.actionButton}
                          onClick={() => handleSaveEdit(category.id, category.color)}
                        >
                          Save
                        </button>
                        <button className={styles.actionButton} onClick={handleCancelEdit}>
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <div className={styles.colorPicker}>
                          {PRESET_COLORS.map((color) => (
                            <button
                              key={color}
                              className={`${styles.colorOption} ${
                                category.color === color ? styles.colorOptionActive : ''
                              }`}
                              style={{ backgroundColor: color }}
                              onClick={() => handleColorChange(category.id, color)}
                              title={`Change to ${color}`}
                            />
                          ))}
                        </div>
                        <button
                          className={`${styles.deleteButton} ${
                            deletingId === category.id ? styles.deleteConfirm : ''
                          }`}
                          onClick={() => handleDelete(category.id)}
                        >
                          {deletingId === category.id ? 'Confirm?' : 'Delete'}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className={styles.createSection}>
            <h3 className={styles.createTitle}>Add New Category</h3>
            <div className={styles.createForm}>
              <input
                className={styles.input}
                type="text"
                placeholder="Category name"
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    handleCreate();
                  }
                }}
              />
              <div className={styles.colorPicker}>
                {PRESET_COLORS.map((color) => (
                  <button
                    key={color}
                    className={`${styles.colorOption} ${
                      newCategoryColor === color ? styles.colorOptionActive : ''
                    }`}
                    style={{ backgroundColor: color }}
                    onClick={() => setNewCategoryColor(color)}
                  />
                ))}
              </div>
              <button className={styles.createButton} onClick={handleCreate}>
                Add Category
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function CategoriesPage() {
  return (
    <div className={styles.categoriesPage}>
      <div className={styles.header}>
        <h1 className={styles.title}>Categories</h1>
        <p className={styles.subtitle}>
          Organize your tasks, events, and reminders with custom categories
        </p>
      </div>

      <div className={styles.content}>
        <CategorySection type="tasks" title="Task Categories" />
        <CategorySection type="events" title="Event Categories" />
        <CategorySection type="reminders" title="Reminder Categories" />
      </div>
    </div>
  );
}
