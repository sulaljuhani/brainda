import { TextareaHTMLAttributes, forwardRef } from 'react';
import './Textarea.css';

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  fullWidth?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, fullWidth = false, className = '', ...props }, ref) => {
    const textareaClasses = [
      'textarea',
      error ? 'textarea--error' : '',
      fullWidth ? 'textarea--full-width' : '',
      className,
    ]
      .filter(Boolean)
      .join(' ');

    return (
      <div className={`textarea-wrapper ${fullWidth ? 'textarea-wrapper--full-width' : ''}`}>
        {label && (
          <label htmlFor={props.id} className="textarea-label">
            {label}
          </label>
        )}
        <textarea ref={ref} className={textareaClasses} {...props} />
        {error && <span className="textarea-error-message">{error}</span>}
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';
