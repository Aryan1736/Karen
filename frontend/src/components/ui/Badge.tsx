import React from 'react';
import clsx from 'clsx';
import './Badge.css';

export type BadgeVariant = 
  | 'p0-critical'
  | 'p1-high'
  | 'p2-medium'
  | 'p3-low'
  | 'needs-review'
  | 'verified'
  | 'simulation'
  | 'neutral';

export type BadgeSize = 'sm' | 'md' | 'lg';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  showBeacon?: boolean;
  beaconColor?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  size = 'md',
  showBeacon = false,
  beaconColor,
  className,
  children,
  ...props
}) => {
  return (
    <span
      className={clsx(
        'tactical-badge',
        `tactical-badge-${variant}`,
        `tactical-badge-${size}`,
        className
      )}
      {...props}
    >
      {showBeacon && (
        <span 
          className="badge-beacon-dot badge-beacon-pulse"
          style={{ backgroundColor: beaconColor || 'currentColor' }}
        />
      )}
      {children}
    </span>
  );
};

export default Badge;
