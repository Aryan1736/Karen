import React from 'react';
import clsx from 'clsx';
import './ConfidenceGauge.css';

export type GaugeColor = 'cyan' | 'green' | 'yellow' | 'orange' | 'red' | 'magenta';

export interface ConfidenceGaugeProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number; // 0 to 100 or 0.0 to 1.0
  label?: string;
  color?: GaugeColor;
  showText?: boolean;
}

export const ConfidenceGauge: React.FC<ConfidenceGaugeProps> = ({
  value,
  label = 'CONFIDENCE',
  color = 'cyan',
  showText = true,
  className,
  ...props
}) => {
  // Normalize value if passed as float [0.0, 1.0]
  const percentage = value <= 1.0 && value >= 0 ? Math.round(value * 1000) / 10 : Math.min(100, Math.max(0, value));
  const remaining = Math.max(0, 100 - percentage);

  return (
    <div className={clsx('tactical-confidence-gauge', className)} {...props}>
      {(label || showText) && (
        <div className="gauge-header">
          {label && <span className="gauge-label">{label}</span>}
          {showText && (
            <span className={clsx('gauge-percentage', `gauge-percentage-${color}`)}>
              {percentage.toFixed(1)}%
            </span>
          )}
        </div>
      )}
      <div className="gauge-track">
        <div 
          className={clsx('gauge-fill', `gauge-fill-${color}`)} 
          style={{ width: `${percentage}%` }}
        />
        {remaining > 0 && <div className="gauge-empty" style={{ width: `${remaining}%` }} />}
      </div>
    </div>
  );
};

export default ConfidenceGauge;
