import { useState, useEffect } from 'react';
import { Modal } from '@components/shared/Modal';
import { CategoryPicker } from '@components/shared/CategoryPicker';
import { RecurrenceInput } from '@components/shared/RecurrenceInput';
import { CategoryManager } from '@components/shared/CategoryManager';
import type { Task, CreateTaskRequest } from '@types/*';
import styles from './TaskForm.module.css';

interface TaskFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateTaskRequest) => Promise<void>;
  task?: Task | null;
  parentTaskId?: string | null;
  parentTaskTitle?: string;
}

export function TaskForm({
  isOpen,
  onClose,
  onSubmit,
  task,
  parentTaskId,
  parentTaskTitle,
}: TaskFormProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [startsAt, setStartsAt] = useState('');
  const [endsAt, setEndsAt] = useState('');
  const [allDay, setAllDay] = useState(false);
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone
  );
  const [rrule, setRrule] = useState('');
  const [showCategoryManager, setShowCategoryManager] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset form when opening
  useEffect(() => {
    if (isOpen) {
      if (task) {
        setTitle(task.title);
        setDescription(task.description || '');
        setCategoryId(task.category_id || null);
        setStartsAt(task.starts_at || '');
        setEndsAt(task.ends_at || '');
        setAllDay(task.all_day);
        setTimezone(task.timezone);
        setRrule(task.rrule || '');
      } else {
        setTitle('');
        setDescription('');
        setCategoryId(null);
        setStartsAt('');
        setEndsAt('');
        setAllDay(false);
        setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
        setRrule('');
      }
    }
  }, [isOpen, task]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      alert('Please enter a task title');
      return;
    }

    setIsSubmitting(true);
    try {
      const data: CreateTaskRequest = {
        title: title.trim(),
        description: description.trim() || undefined,
        category_id: categoryId || undefined,
        starts_at: startsAt || undefined,
        ends_at: endsAt || undefined,
        all_day: allDay,
        timezone,
        rrule: rrule || undefined,
        parent_task_id: parentTaskId || undefined,
      };

      await onSubmit(data);
      onClose();
    } catch (err) {
      console.error('Failed to create task:', err);
      alert('Failed to create task. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={task ? 'Edit Task' : 'Create Task'}
      >
        <form onSubmit={handleSubmit} className={styles.taskForm}>
          {parentTaskId && parentTaskTitle && (
            <div className={styles.subtaskNotice}>
              Creating subtask under: <strong>{parentTaskTitle}</strong>
            </div>
          )}

          <div className={styles.formGroup}>
            <label className={styles.label}>
              Task Name<span className={styles.required}>*</span>
            </label>
            <input
              type="text"
              className={styles.input}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter task name"
              required
              autoFocus
            />
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>Description</label>
            <textarea
              className={styles.textarea}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Enter task description (optional)"
              rows={3}
            />
          </div>

          <CategoryPicker
            type="tasks"
            value={categoryId}
            onChange={setCategoryId}
            onManageCategories={() => setShowCategoryManager(true)}
          />

          <div className={styles.formGroup}>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={allDay}
                onChange={(e) => setAllDay(e.target.checked)}
              />
              <span>All-day task</span>
            </label>
          </div>

          {!allDay && (
            <>
              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label className={styles.label}>Start Date & Time</label>
                  <input
                    type="datetime-local"
                    className={styles.input}
                    value={startsAt}
                    onChange={(e) => setStartsAt(e.target.value)}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.label}>End Date & Time</label>
                  <input
                    type="datetime-local"
                    className={styles.input}
                    value={endsAt}
                    onChange={(e) => setEndsAt(e.target.value)}
                  />
                </div>
              </div>
            </>
          )}

          {allDay && (
            <>
              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label className={styles.label}>Start Date</label>
                  <input
                    type="date"
                    className={styles.input}
                    value={startsAt}
                    onChange={(e) => setStartsAt(e.target.value)}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.label}>End Date</label>
                  <input
                    type="date"
                    className={styles.input}
                    value={endsAt}
                    onChange={(e) => setEndsAt(e.target.value)}
                  />
                </div>
              </div>
            </>
          )}

          <div className={styles.formGroup}>
            <label className={styles.label}>Timezone</label>
            <select
              className={styles.select}
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              <option value={Intl.DateTimeFormat().resolvedOptions().timeZone}>
                {Intl.DateTimeFormat().resolvedOptions().timeZone} (Local)
              </option>
              <option value="UTC">UTC</option>
              <option value="America/New_York">America/New_York</option>
              <option value="America/Chicago">America/Chicago</option>
              <option value="America/Denver">America/Denver</option>
              <option value="America/Los_Angeles">America/Los_Angeles</option>
              <option value="Europe/London">Europe/London</option>
              <option value="Europe/Paris">Europe/Paris</option>
              <option value="Asia/Tokyo">Asia/Tokyo</option>
            </select>
          </div>

          <RecurrenceInput type="task" value={rrule} onChange={setRrule} />

          <div className={styles.formActions}>
            <button
              type="button"
              className={styles.cancelButton}
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.submitButton}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Saving...' : task ? 'Update Task' : 'Create Task'}
            </button>
          </div>
        </form>
      </Modal>

      <CategoryManager
        isOpen={showCategoryManager}
        onClose={() => setShowCategoryManager(false)}
        type="tasks"
      />
    </>
  );
}
