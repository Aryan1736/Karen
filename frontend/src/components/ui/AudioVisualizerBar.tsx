import React from 'react';
import clsx from 'clsx';
import './AudioVisualizerBar.css';

export interface AudioVisualizerBarProps extends React.HTMLAttributes<HTMLDivElement> {
  active?: boolean;
  levels?: number[]; // Normalized [0.0, 1.0] amplitude levels from genuine audio source
}

const DEFAULT_BAR_COLORS = [
  'green',
  'green',
  'cyan',
  'cyan',
  'yellow',
  'orange',
  'red',
  'red',
];

export const AudioVisualizerBar: React.FC<AudioVisualizerBarProps> = ({
  active = false,
  levels,
  className,
  ...props
}) => {
  return (
    <div
      className={clsx(
        'tactical-audio-visualizer',
        active ? 'visualizer-active' : 'visualizer-idle',
        className
      )}
      title={active ? 'Audio channel active' : 'Audio channel standby / no signal'}
      {...props}
    >
      {DEFAULT_BAR_COLORS.map((color, idx) => {
        // If real levels provided and active, scale between 3px and 16px; otherwise resting at 3px
        const heightPx = active && levels && typeof levels[idx] === 'number'
          ? Math.max(3, Math.min(16, Math.round(levels[idx] * 16)))
          : 3;

        return (
          <div
            key={idx}
            className={clsx('visualizer-bar', `visualizer-${color}`)}
            style={{
              height: `${heightPx}px`,
              transformOrigin: 'bottom',
            }}
          />
        );
      })}
    </div>
  );
};

export default AudioVisualizerBar;
