import React from 'react';
import clsx from 'clsx';
import './StatusIndicator.css';

export type StatusVariant = 
  | 'online'      // System Green (Online / Healthy)
  | 'connected'   // Multiverse Cyan (WebSocket connected)
  | 'standby'     // Dispatch Yellow (Standby / Buffering)
  | 'alert'       // Stark Red (Critical Alert active)
  | 'offline';    // Slate Gray (Disconnected)

export interface StatusIndicatorProps extends React.HTMLAttributes<HTMLDivElement> {
  status?: StatusVariant;
  pulse?: boolean;
  label?: string;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status = 'online',
  pulse = true,
  label,
  className,
  children,
  ...props
}) => {
  return (
    <div
      className={clsx(
        'tactical-status-indicator',
        `tactical-status-${status}`,
        className
      )}
      {...props}
    >
      <span className={clsx('status-dot-core', pulse && 'status-dot-pulse')} />
      <span>{label || children}</span>
    </div>
  );
};

export default StatusIndicator;
