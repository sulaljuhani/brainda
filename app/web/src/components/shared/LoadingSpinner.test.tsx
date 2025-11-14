import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/utils';
import { LoadingSpinner } from './LoadingSpinner';

describe('LoadingSpinner', () => {
  it('renders with default props', () => {
    render(<LoadingSpinner />);
    const spinner = screen.getByRole('status', { name: /loading/i });
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveClass('spinner', 'spinner--medium');
  });

  it('renders with different sizes', () => {
    const { rerender } = render(<LoadingSpinner size="small" />);
    expect(screen.getByRole('status')).toHaveClass('spinner--small');

    rerender(<LoadingSpinner size="large" />);
    expect(screen.getByRole('status')).toHaveClass('spinner--large');
  });

  it('renders in fullScreen mode', () => {
    render(<LoadingSpinner fullScreen />);
    const fullscreenContainer = document.querySelector('.spinner-fullscreen');
    expect(fullscreenContainer).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('has proper accessibility attributes', () => {
    render(<LoadingSpinner />);
    const spinner = screen.getByRole('status');
    expect(spinner).toHaveAttribute('aria-label', 'Loading');
  });

  it('renders spinner circle', () => {
    render(<LoadingSpinner />);
    const circle = document.querySelector('.spinner-circle');
    expect(circle).toBeInTheDocument();
  });
});
