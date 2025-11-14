import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/utils';
import userEvent from '@testing-library/user-event';
import { Input } from './Input';

describe('Input', () => {
  it('renders with default props', () => {
    render(<Input placeholder="Enter text" />);
    const input = screen.getByPlaceholderText('Enter text');
    expect(input).toBeInTheDocument();
    expect(input).toHaveClass('input');
  });

  it('renders with label', () => {
    render(<Input label="Username" id="username" />);
    const label = screen.getByText('Username');
    const input = screen.getByLabelText('Username');

    expect(label).toBeInTheDocument();
    expect(input).toBeInTheDocument();
    expect(label).toHaveAttribute('for', 'username');
  });

  it('displays error message', () => {
    render(<Input error="This field is required" />);
    const input = screen.getByRole('textbox');
    const errorMessage = screen.getByText('This field is required');

    expect(input).toHaveClass('input--error');
    expect(errorMessage).toBeInTheDocument();
    expect(errorMessage).toHaveClass('input-error-message');
  });

  it('renders with fullWidth prop', () => {
    render(<Input fullWidth />);
    const input = screen.getByRole('textbox');
    expect(input).toHaveClass('input--full-width');
  });

  it('handles user input', async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();

    render(<Input onChange={handleChange} />);
    const input = screen.getByRole('textbox');

    await user.type(input, 'Hello');

    expect(input).toHaveValue('Hello');
    expect(handleChange).toHaveBeenCalledTimes(5); // Once per character
  });

  it('can be disabled', () => {
    render(<Input disabled />);
    const input = screen.getByRole('textbox');
    expect(input).toBeDisabled();
  });

  it('accepts different input types', () => {
    const { rerender } = render(<Input type="email" />);
    expect(screen.getByRole('textbox')).toHaveAttribute('type', 'email');

    rerender(<Input type="password" />);
    const passwordInput = document.querySelector('input[type="password"]');
    expect(passwordInput).toBeInTheDocument();
  });

  it('forwards ref correctly', () => {
    const ref = { current: null as HTMLInputElement | null };
    render(<Input ref={ref} />);

    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });

  it('accepts custom className', () => {
    render(<Input className="custom-input" />);
    expect(screen.getByRole('textbox')).toHaveClass('input', 'custom-input');
  });

  it('shows both label and error', () => {
    render(<Input label="Email" error="Invalid email" id="email" />);

    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Invalid email')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveClass('input--error');
  });

  it('is accessible', () => {
    render(<Input label="Email" id="email" />);
    const input = screen.getByLabelText('Email');
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute('id', 'email');
  });
});
