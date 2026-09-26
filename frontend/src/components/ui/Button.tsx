import React from 'react';
import clsx from 'clsx';
import './Button.css';

export type ButtonVariant = 
  | 'primary'       // Stark Red / P0 Critical
  | 'hazard'        // Hazard Orange / P1 High
  | 'warning'       // Dispatch Yellow / P2 Medium
  | 'cyan'          // Multiverse Cyan / P3 Low
  | 'secondary'     // Surface Container High
  | 'ghost'         // Outline / Subtle
  | 'danger-stripe'; // Diagonal hazard stripes

export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({
  variant = 'secondary',
  size = 'md',
  leftIcon,
  rightIcon,
  className,
  children,
  ...props
}, ref) => {
  return (
    <button
      ref={ref}
      className={clsx(
        'tactical-btn',
        `tactical-btn-${variant}`,
        `tactical-btn-${size}`,
        className
      )}
      {...props}
    >
      {leftIcon && <span className="btn-icon-left">{leftIcon}</span>}
      <span>{children}</span>
      {rightIcon && <span className="btn-icon-right">{rightIcon}</span>}
    </button>
  );
});

Button.displayName = 'Button';
export default Button;
