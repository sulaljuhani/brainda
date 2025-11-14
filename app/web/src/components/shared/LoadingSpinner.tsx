import './LoadingSpinner.css';

interface LoadingSpinnerProps {
  size?: 'small' | 'medium' | 'large';
  fullScreen?: boolean;
}

export function LoadingSpinner({ size = 'medium', fullScreen = false }: LoadingSpinnerProps) {
  const spinner = (
    <div className={`spinner spinner--${size}`} role="status" aria-label="Loading">
      <div className="spinner-circle"></div>
    </div>
  );

  if (fullScreen) {
    return <div className="spinner-fullscreen">{spinner}</div>;
  }

  return spinner;
}
