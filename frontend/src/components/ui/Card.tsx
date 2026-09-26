import React from 'react';
import clsx from 'clsx';
import './Card.css';

export type CardElevation = 0 | 1 | 2 | 3 | 'chromatic';
export type CardBorder = 'thin' | 'default' | 'thick' | 'heavy';
export type CardSurface = 'default' | 'elevated' | 'container' | 'newsprint' | 'glitch';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevation?: CardElevation;
  border?: CardBorder;
  surface?: CardSurface;
  interactive?: boolean;
}

export const Card: React.FC<CardProps> = ({
  elevation = 2,
  border = 'default',
  surface = 'default',
  interactive = false,
  className,
  children,
  ...props
}) => {
  return (
    <div
      className={clsx(
        'tactical-card',
        `tactical-card-elevation-${elevation}`,
        `tactical-card-border-${border}`,
        `tactical-card-surface-${surface}`,
        interactive && 'tactical-card-interactive',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {}
export const CardHeader: React.FC<CardHeaderProps> = ({ className, children, ...props }) => (
  <div className={clsx('tactical-card-header', className)} {...props}>
    {children}
  </div>
);

export interface CardBodyProps extends React.HTMLAttributes<HTMLDivElement> {}
export const CardBody: React.FC<CardBodyProps> = ({ className, children, ...props }) => (
  <div className={clsx('tactical-card-body', className)} {...props}>
    {children}
  </div>
);

export interface CardFooterProps extends React.HTMLAttributes<HTMLDivElement> {}
export const CardFooter: React.FC<CardFooterProps> = ({ className, children, ...props }) => (
  <div className={clsx('tactical-card-footer', className)} {...props}>
    {children}
  </div>
);

export default Card;
