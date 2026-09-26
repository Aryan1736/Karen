import React from 'react';
import clsx from 'clsx';
import './ConfidenceGauge.css';

export type GaugeColor = 'cyan' | 'green' | 'yellow' | 'orange' | 'red' | 'magenta';

export interface ConfidenceGaugeProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number | null; // Optional: when null or undefined, indicates no model prediction available
  label?: string;
  color?: GaugeColor;
  showText?: boolean;
}

export const ConfidenceGauge: React.FC<ConfidenceGaugeProps> = ({
  value = null,
  label = 'CONFIDENCE',
  color = 'cyan',
  showText = true,
  className,
  ...props
}) => {
  // If value is null or undefined, render an empty/idle gauge without fabricating a score
  const hasValue = typeof value === 'number' && !isNaN(value);
  const percentage = hasValue
    ? value <= 1.0 && value >= 0
      ? Math.round(value * 1000) / 10
      : Math.min(100, Math.max(0, value))
    : 0;
  const remaining = Math.max(0, 100 - percentage);

  return (
    <div className={clsx('tactical-confidence-gauge', className)} {...props}>
      {(label || showText) && (
        <div className="gauge-header">
          {label && <span className="gauge-label">{label}</span>}
          {showText && (
            <span className={clsx('gauge-percentage', hasValue ? `gauge-percentage-${color}` : 'gauge-percentage-idle')}>
              {hasValue ? `${percentage.toFixed(1)}%` : '--%'}
            </span>
          )}
        </div>
      )}
      <div className="gauge-track">
        {hasValue && percentage > 0 && (
          <div 
            className={clsx('gauge-fill', `gauge-fill-${color}`)} 
            style={{ width: `${percentage}%` }}
          />
        )}
        <div className="gauge-empty" style={{ width: `${hasValue ? remaining : 100}%` }} />
      </div>
    </div>
  );
};

export default ConfidenceGauge;
