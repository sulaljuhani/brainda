import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@/test/utils';
import userEvent from '@testing-library/user-event';
import { Toast, ToastContainer, ToastProps } from './Toast';

describe('Toast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const defaultProps: ToastProps = {
    id: '1',
    type: 'success',
    message: 'Success message',
    onClose: vi.fn(),
  };

  it('renders with success type', () => {
    render(<Toast {...defaultProps} />);
    expect(screen.getByText('Success message')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveClass('toast--success');
  });

  it('renders with error type', () => {
    render(<Toast {...defaultProps} type="error" message="Error message" />);
    expect(screen.getByText('Error message')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveClass('toast--error');
  });

  it('renders with warning type', () => {
    render(<Toast {...defaultProps} type="warning" message="Warning message" />);
    expect(screen.getByText('Warning message')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveClass('toast--warning');
  });

  it('renders with info type', () => {
    render(<Toast {...defaultProps} type="info" message="Info message" />);
    expect(screen.getByText('Info message')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveClass('toast--info');
  });

  it('calls onClose when close button is clicked', async () => {
    const handleClose = vi.fn();
    const user = userEvent.setup({ delay: null });

    render(<Toast {...defaultProps} onClose={handleClose} />);

    const closeButton = screen.getByRole('button', { name: /close notification/i });
    await user.click(closeButton);

    expect(handleClose).toHaveBeenCalledWith('1');
  });

  it('auto-closes after duration', () => {
    const handleClose = vi.fn();
    render(<Toast {...defaultProps} onClose={handleClose} duration={3000} />);

    expect(handleClose).not.toHaveBeenCalled();

    vi.advanceTimersByTime(3000);

    expect(handleClose).toHaveBeenCalledWith('1');
  });

  it('does not auto-close when duration is 0', () => {
    const handleClose = vi.fn();
    render(<Toast {...defaultProps} onClose={handleClose} duration={0} />);

    vi.advanceTimersByTime(10000);

    expect(handleClose).not.toHaveBeenCalled();
  });

  it('has proper accessibility attributes', () => {
    render(<Toast {...defaultProps} />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveAttribute('aria-live', 'polite');
  });

  it('cleans up timer on unmount', () => {
    const handleClose = vi.fn();
    const { unmount } = render(
      <Toast {...defaultProps} onClose={handleClose} duration={3000} />
    );

    unmount();
    vi.advanceTimersByTime(3000);

    // onClose should not be called after unmount
    expect(handleClose).not.toHaveBeenCalled();
  });
});

describe('ToastContainer', () => {
  it('renders multiple toasts', () => {
    const toasts: ToastProps[] = [
      { id: '1', type: 'success', message: 'Success', onClose: vi.fn() },
      { id: '2', type: 'error', message: 'Error', onClose: vi.fn() },
      { id: '3', type: 'info', message: 'Info', onClose: vi.fn() },
    ];

    render(<ToastContainer toasts={toasts} onClose={vi.fn()} />);

    expect(screen.getByText('Success')).toBeInTheDocument();
    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Info')).toBeInTheDocument();
  });

  it('renders empty container when no toasts', () => {
    render(<ToastContainer toasts={[]} onClose={vi.fn()} />);
    const container = document.querySelector('.toast-container');
    expect(container).toBeInTheDocument();
    expect(container?.children.length).toBe(0);
  });

  it('passes onClose to each toast', async () => {
    const handleClose = vi.fn();
    const toasts: ToastProps[] = [
      { id: '1', type: 'success', message: 'Test', onClose: vi.fn() },
    ];

    const user = userEvent.setup();
    render(<ToastContainer toasts={toasts} onClose={handleClose} />);

    const closeButton = screen.getByRole('button', { name: /close notification/i });
    await user.click(closeButton);

    expect(handleClose).toHaveBeenCalledWith('1');
  });
});
