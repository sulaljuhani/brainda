import { InputHTMLAttributes, forwardRef } from 'react';
import './Input.css';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  fullWidth?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, fullWidth = false, className = '', ...props }, ref) => {
    const inputClasses = [
      'input',
      error ? 'input--error' : '',
      fullWidth ? 'input--full-width' : '',
      className,
    ]
      .filter(Boolean)
      .join(' ');

    return (
      <div className={`input-wrapper ${fullWidth ? 'input-wrapper--full-width' : ''}`}>
        {label && (
          <label htmlFor={props.id} className="input-label">
            {label}
          </label>
        )}
        <input ref={ref} className={inputClasses} {...props} />
        {error && <span className="input-error-message">{error}</span>}
      </div>
    );
  }
);

Input.displayName = 'Input';
