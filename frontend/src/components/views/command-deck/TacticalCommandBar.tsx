import React, { useState } from 'react';
import { 
  Mic, 
  MicOff, 
  Volume2, 
  VolumeX, 
  Radio, 
  ShieldAlert,
  Share2
} from 'lucide-react';
import { AudioVisualizerBar } from '../../ui';
import './TacticalCommandBar.css';

export interface TacticalCommandBarProps {
  className?: string;
}

export const TacticalCommandBar: React.FC<TacticalCommandBarProps> = ({
  className = '',
}) => {
  const [isMuted, setIsMuted] = useState(false);

  return (
    <footer className={`tactical-command-bar ${className}`} role="toolbar" aria-label="Tactical Command Bar">
      {/* Audio Waveform Monitor Segment */}
      <div className="command-bar-audio-segment">
        <div className="audio-segment-label">
          {isMuted ? (
            <MicOff size={16} color="var(--color-p0-critical)" />
          ) : (
            <Mic size={16} color="var(--color-dispatch-yellow)" />
          )}
          <span className="audio-channel-title">LIVE DISPATCH TRANSIT CHANNEL:</span>
        </div>

        {/* Audio Visualizer Bar kept strictly in STANDBY unless real audio telemetry arrives */}
        <div className="audio-visualizer-wrap">
          <AudioVisualizerBar active={false} />
        </div>

        <div className="audio-freq-badge">
          <Radio size={11} style={{ marginRight: 3 }} />
          <span>470.8125 MHz (TAC-04)</span>
          <span className="audio-standby-pill">[STANDBY RX LOCK]</span>
        </div>
      </div>

      {/* Operator Action Buttons */}
      <div className="command-bar-actions">
        <button
          type="button"
          className={`tac-action-btn ${isMuted ? 'btn-muted' : ''}`}
          onClick={() => setIsMuted(!isMuted)}
          aria-pressed={isMuted}
          title="Toggle audio feeds mute state"
        >
          {isMuted ? (
            <>
              <VolumeX size={14} />
              <span>FEEDS MUTED [OFF]</span>
            </>
          ) : (
            <>
              <Volume2 size={14} />
              <span>MUTE FEEDS [M]</span>
            </>
          )}
        </button>

        <button
          type="button"
          className="tac-action-btn"
          disabled
          title="Broadcast functionality will be enabled in Phase 7"
        >
          <Share2 size={14} />
          <span>BROADCAST ALL [B]</span>
        </button>

        <div className="command-bar-security-tag">
          <ShieldAlert size={12} color="var(--color-hazard-orange)" />
          <span>RUNBOOK: TAC-OPS SOVEREIGN DISPATCH</span>
        </div>
      </div>
    </footer>
  );
};

export default TacticalCommandBar;
