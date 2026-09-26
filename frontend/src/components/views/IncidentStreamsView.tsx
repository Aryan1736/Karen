import React from 'react';
import { Radio, Rss } from 'lucide-react';
import { Badge } from '../ui';
import './IncidentStreamsView.css';

export const IncidentStreamsView: React.FC = () => {
  return (
    <div className="incident-streams-view" role="region" aria-label="Incident Streams View">
      <div className="streams-header">
        <div className="streams-title-group">
          <Rss size={18} color="var(--color-multiverse-cyan)" />
          <h2 className="streams-title">INCIDENT STREAMS // LIVE INGESTION CHANNELS</h2>
          <Badge variant="neutral" size="sm">0 ACTIVE STREAMS</Badge>
        </div>
        <div className="streams-status">
          <Badge variant="p2-medium" size="sm">CHANNEL MONITOR: STANDBY</Badge>
        </div>
      </div>

      <div className="streams-body">
        <div className="streams-empty-box">
          <div className="streams-empty-icon">
            <Radio size={48} color="var(--color-multiverse-cyan)" />
          </div>
          <h3 className="streams-empty-heading">Ingestion Streams Standby</h3>
          <p className="streams-empty-desc">
            Raw incoming emergency reports, RF dispatch transcripts, and simulated sensor events will appear in this synchronized multi-channel stream.
          </p>
          <div className="streams-meta-pills">
            <Badge variant="neutral" size="sm">AUDIO_TRANSCRIPTS: READY</Badge>
            <Badge variant="neutral" size="sm">CITIZEN_DISPATCHES: STANDBY</Badge>
            <Badge variant="neutral" size="sm">SENSOR_TELEMETRY: STANDBY</Badge>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IncidentStreamsView;
