import { useState, useMemo } from 'react';
import { Plus, CheckCircle } from 'lucide-react';
import { useTasks } from '@hooks/useTasks';
import { TaskForm } from '@components/tasks/TaskForm';
import { CategoryManager } from '@components/shared/CategoryManager';
import type { Task, CreateTaskRequest } from '@types/*';
import styles from './TasksPage.module.css';

type TabType = 'active' | 'completed';

interface GroupedTasks {
  categoryId: string | null;
  categoryName: string;
  categoryColor?: string;
  tasks: Task[];
}

export default function TasksPage() {
  const [activeTab, setActiveTab] = useState<TabType>('active');
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [parentTaskId, setParentTaskId] = useState<string | null>(null);
  const [parentTaskTitle, setParentTaskTitle] = useState<string | null>(null);
  const [showCategoryManager, setShowCategoryManager] = useState(false);
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());

  const { tasks, loading, error, createTask, updateTask, completeTask, deleteTask } =
    useTasks({ status: activeTab, includeSubtasks: false });

  // Group tasks by category
  const groupedTasks = useMemo(() => {
    const groups = new Map<string | null, GroupedTasks>();

    // Add "No Category" group first
    groups.set(null, {
      categoryId: null,
      categoryName: 'No Category',
      tasks: [],
    });

    // Group tasks
    tasks.forEach((task) => {
      const categoryId = task.category_id || null;
      if (!groups.has(categoryId)) {
        groups.set(categoryId, {
          categoryId,
          categoryName: task.category_name || 'No Category',
          categoryColor: undefined, // Would need to fetch from categories
          tasks: [],
        });
      }
      groups.get(categoryId)!.tasks.push(task);
    });

    // Remove empty groups except "No Category"
    const result: GroupedTasks[] = [];
    groups.forEach((group, key) => {
      if (key === null || group.tasks.length > 0) {
        result.push(group);
      }
    });

    return result;
  }, [tasks]);

  const handleCreateTask = async (data: CreateTaskRequest) => {
    await createTask(data);
    setShowTaskForm(false);
    setParentTaskId(null);
    setParentTaskTitle(null);
  };

  const handleEditTask = (task: Task) => {
    setEditingTask(task);
    setShowTaskForm(true);
  };

  const handleUpdateTask = async (data: CreateTaskRequest) => {
    if (editingTask) {
      await updateTask(editingTask.id, data);
      setEditingTask(null);
      setShowTaskForm(false);
    }
  };

  const handleCompleteTask = async (id: string) => {
    await completeTask(id);
  };

  const handleDeleteTask = async (id: string) => {
    if (confirm('Are you sure you want to delete this task?')) {
      await deleteTask(id);
    }
  };

  const handleAddSubtask = (parentTask: Task) => {
    setParentTaskId(parentTask.id);
    setParentTaskTitle(parentTask.title);
    setShowTaskForm(true);
  };

  const toggleTaskExpanded = (taskId: string) => {
    setExpandedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  };

  const renderTask = (task: Task, isSubtask = false) => {
    const hasSubtasks = task.subtasks && task.subtasks.length > 0;
    const isExpanded = expandedTasks.has(task.id);

    return (
      <div key={task.id} className={styles.taskWrapper}>
        <div className={`${styles.taskCard} ${isSubtask ? styles.subtask : ''}`}>
          <div className={styles.taskMain}>
            {activeTab === 'active' && (
              <button
                className={styles.checkbox}
                onClick={() => handleCompleteTask(task.id)}
                title="Mark as complete"
              >
                <CheckCircle size={20} />
              </button>
            )}

            <div className={styles.taskContent}>
              <div className={styles.taskHeader}>
                <h3 className={styles.taskTitle}>{task.title}</h3>
                {hasSubtasks && (
                  <button
                    className={styles.expandButton}
                    onClick={() => toggleTaskExpanded(task.id)}
                  >
                    {isExpanded ? '▼' : '▶'} {task.subtasks!.length} subtask
                    {task.subtasks!.length !== 1 ? 's' : ''}
                  </button>
                )}
              </div>

              {task.description && (
                <p className={styles.taskDescription}>{task.description}</p>
              )}

              {(task.starts_at || task.ends_at) && (
                <div className={styles.taskDates}>
                  {task.starts_at && (
                    <span>
                      Starts: {new Date(task.starts_at).toLocaleDateString()}
                    </span>
                  )}
                  {task.ends_at && (
                    <span>Ends: {new Date(task.ends_at).toLocaleDateString()}</span>
                  )}
                </div>
              )}

              {task.rrule && <div className={styles.recurringBadge}>Recurring</div>}
            </div>
          </div>

          <div className={styles.taskActions}>
            {activeTab === 'active' && !isSubtask && (
              <button
                className={styles.actionButton}
                onClick={() => handleAddSubtask(task)}
              >
                Add Subtask
              </button>
            )}
            <button
              className={styles.actionButton}
              onClick={() => handleEditTask(task)}
            >
              Edit
            </button>
            <button
              className={styles.deleteButton}
              onClick={() => handleDeleteTask(task.id)}
            >
              Delete
            </button>
          </div>
        </div>

        {hasSubtasks && isExpanded && (
          <div className={styles.subtaskContainer}>
            {task.subtasks!.map((subtask) => renderTask(subtask, true))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={styles.tasksPage}>
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <h1 className={styles.title}>Tasks</h1>
          <p className={styles.subtitle}>
            Organize your work with tasks and sub-tasks
          </p>
        </div>
        <button className={styles.createBtn} onClick={() => setShowTaskForm(true)}>
          <Plus size={20} />
          Add Task
        </button>
      </div>

      {error && (
        <div className={styles.errorBanner}>
          <p>{error}</p>
        </div>
      )}

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'active' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('active')}
        >
          Active
        </button>
        <button
          className={`${styles.tab} ${
            activeTab === 'completed' ? styles.tabActive : ''
          }`}
          onClick={() => setActiveTab('completed')}
        >
          Completed
        </button>
        <button
          className={styles.manageCategoriesBtn}
          onClick={() => setShowCategoryManager(true)}
        >
          Manage Categories
        </button>
      </div>

      <div className={styles.content}>
        {loading ? (
          <div className={styles.loadingState}>
            <div className={styles.spinner}></div>
            <p>Loading tasks...</p>
          </div>
        ) : groupedTasks.length === 0 ? (
          <div className={styles.emptyState}>
            <p>No {activeTab} tasks yet.</p>
            {activeTab === 'active' && (
              <button className={styles.createBtn} onClick={() => setShowTaskForm(true)}>
                <Plus size={20} />
                Create your first task
              </button>
            )}
          </div>
        ) : (
          <div className={styles.taskGroups}>
            {groupedTasks.map((group) => (
              <div key={group.categoryId || 'no-category'} className={styles.taskGroup}>
                <div className={styles.groupHeader}>
                  {group.categoryColor && (
                    <div
                      className={styles.categoryColor}
                      style={{ backgroundColor: group.categoryColor }}
                    />
                  )}
                  <h2 className={styles.groupTitle}>{group.categoryName}</h2>
                  <span className={styles.groupCount}>({group.tasks.length})</span>
                </div>
                <div className={styles.taskList}>
                  {group.tasks.map((task) => renderTask(task))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <TaskForm
        isOpen={showTaskForm}
        onClose={() => {
          setShowTaskForm(false);
          setEditingTask(null);
          setParentTaskId(null);
          setParentTaskTitle(null);
        }}
        onSubmit={editingTask ? handleUpdateTask : handleCreateTask}
        task={editingTask}
        parentTaskId={parentTaskId}
        parentTaskTitle={parentTaskTitle || undefined}
      />

      <CategoryManager
        isOpen={showCategoryManager}
        onClose={() => setShowCategoryManager(false)}
        type="tasks"
      />
    </div>
  );
}
