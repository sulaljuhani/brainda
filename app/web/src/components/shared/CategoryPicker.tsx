import { useCategories } from '@hooks/useCategories';
import styles from './CategoryPicker.module.css';

interface CategoryPickerProps {
  type: 'tasks' | 'events' | 'reminders';
  value: string | null;
  onChange: (categoryId: string | null) => void;
  onManageCategories: () => void;
}

export function CategoryPicker({
  type,
  value,
  onChange,
  onManageCategories,
}: CategoryPickerProps) {
  const { categories, loading } = useCategories(type);

  if (loading) {
    return (
      <div className={styles.categoryPicker}>
        <label className={styles.label}>Category</label>
        <div className={styles.loading}>Loading categories...</div>
      </div>
    );
  }

  return (
    <div className={styles.categoryPicker}>
      <label className={styles.label}>Category</label>
      <select
        className={styles.select}
        value={value || ''}
        onChange={(e) => onChange(e.target.value || null)}
      >
        <option value="">No category</option>
        {categories.map((category) => (
          <option key={category.id} value={category.id}>
            {category.color && (
              <span
                className={styles.colorIndicator}
                style={{ backgroundColor: category.color }}
              />
            )}
            {category.name}
          </option>
        ))}
      </select>
      <button
        type="button"
        className={styles.manageButton}
        onClick={onManageCategories}
      >
        + Manage Categories
      </button>
    </div>
  );
}
