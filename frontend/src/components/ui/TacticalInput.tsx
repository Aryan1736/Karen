import React from 'react';
import clsx from 'clsx';
import './TacticalInput.css';

export interface TacticalInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  wrapperClassName?: string;
}

export const TacticalInput = React.forwardRef<HTMLInputElement, TacticalInputProps>(({
  leftIcon,
  rightIcon,
  className,
  wrapperClassName,
  ...props
}, ref) => {
  return (
    <div className={clsx('tactical-input-wrapper', wrapperClassName)}>
      {leftIcon && <span className="tactical-input-icon-left">{leftIcon}</span>}
      <input
        ref={ref}
        className={clsx(
          'tactical-input',
          leftIcon && 'tactical-input-has-left-icon',
          rightIcon && 'tactical-input-has-right-icon',
          className
        )}
        {...props}
      />
      {rightIcon && <span className="tactical-input-icon-right">{rightIcon}</span>}
    </div>
  );
});

TacticalInput.displayName = 'TacticalInput';
export default TacticalInput;
