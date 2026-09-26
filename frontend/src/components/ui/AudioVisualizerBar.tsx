import React from 'react';
import clsx from 'clsx';
import './AudioVisualizerBar.css';

export interface AudioVisualizerBarProps extends React.HTMLAttributes<HTMLDivElement> {
  active?: boolean;
}

export const AudioVisualizerBar: React.FC<AudioVisualizerBarProps> = ({
  active = true,
  className,
  ...props
}) => {
  const bars = [
    { color: 'green', height: '6px', delay: '0s' },
    { color: 'green', height: '12px', delay: '0.2s' },
    { color: 'cyan', height: '8px', delay: '0.4s' },
    { color: 'cyan', height: '16px', delay: '0.1s' },
    { color: 'yellow', height: '10px', delay: '0.3s' },
    { color: 'orange', height: '14px', delay: '0.5s' },
    { color: 'red', height: '16px', delay: '0.15s' },
    { color: 'red', height: '8px', delay: '0.35s' },
  ];

  return (
    <div className={clsx('tactical-audio-visualizer', className)} {...props}>
      {bars.map((bar, idx) => (
        <div
          key={idx}
          className={clsx(
            'visualizer-bar',
            `visualizer-${bar.color}`,
            active && 'visualizer-animating'
          )}
          style={{
            height: bar.height,
            animationDelay: bar.delay,
            transformOrigin: 'bottom',
          }}
        />
      ))}
    </div>
  );
};

export default AudioVisualizerBar;
