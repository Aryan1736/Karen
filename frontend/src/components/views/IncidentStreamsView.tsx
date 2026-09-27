import React from 'react';
import { Radio, Rss, Trash2, RefreshCw } from 'lucide-react';
import { Badge, Button } from '../ui';
import { useWebSocket } from '../../context/WebSocketContext';
import './IncidentStreamsView.css';

export const IncidentStreamsView: React.FC = () => {
  const { status, events, reconnect, clearEvents } = useWebSocket();

  const getEventBadgeVariant = (event: string) => {
    switch (event) {
      case 'INCIDENT_CREATED': return 'p0-critical';
      case 'INCIDENT_UPDATED': return 'p1-high';
      case 'INCIDENT_STATUS_CHANGED': return 'p2-medium';
      case 'SIMULATION_PULSE': return 'needs-review';
      case 'PING': return 'neutral';
      default: return 'neutral';
    }
  };

  const formatPayloadSummary = (event: string, payload: any): string => {
    const p = payload && typeof payload === 'object' ? payload : {};
    if (event === 'PING') return 'Heartbeat PING keepalive frame received from server';
    if (event === 'PONG') return 'Heartbeat PONG response frame';
    if (event === 'INCIDENT_CREATED') return `New Incident Created: ${p.incident_id || 'ID Unknown'} [${p.incident_type || 'Unclassified'}]`;
    if (event === 'INCIDENT_UPDATED') return `Incident Updated: ${p.incident_id || 'ID Unknown'} (Score: ${p.priority?.score ?? p.new_priority_score ?? 'N/A'})`;
    if (event === 'INCIDENT_STATUS_CHANGED') return `Status Transition: ${p.incident_id || 'ID Unknown'} [${p.old_status || 'UNKNOWN'} → ${p.new_status || 'UNKNOWN'}]`;
    if (event === 'SIMULATION_PULSE') return `Simulation Pulse: Injected ${p?.injected_count ?? 0}, Total ${p?.total_simulated ?? 0} (${p?.scenario || 'simulation'})`;
    try {
      return `Payload: ${JSON.stringify(payload).substring(0, 80)}`;
    } catch {
      return 'Payload: [unserializable]';
    }
  };

  return (
    <div className="incident-streams-view" role="region" aria-label="Incident Streams View">
      <div className="streams-header">
        <div className="streams-title-group">
          <Rss size={18} color="var(--color-multiverse-cyan)" />
          <h2 className="streams-title">LIVE INCIDENT STREAMS</h2>
          <Badge variant="neutral" size="sm">{events.length} EVENTS RECORDED</Badge>
        </div>
        <div className="streams-status" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Badge variant={status === 'CONNECTED' ? 'verified' : 'neutral'} size="sm">
            STATUS: {status}
          </Badge>
          {events.length > 0 && (
            <Button variant="secondary" size="sm" onClick={clearEvents} title="Clear stream events">
              <Trash2 size={13} style={{ marginRight: 4 }} />
              CLEAR
            </Button>
          )}
          {status !== 'CONNECTED' && (
            <Button variant="secondary" size="sm" onClick={reconnect} title="Reconnect WebSocket">
              <RefreshCw size={13} style={{ marginRight: 4 }} />
              RECONNECT
            </Button>
          )}
        </div>
      </div>

      <div className="streams-body">
        {events.length > 0 ? (
          <div className="streams-event-list">
            {events.map((evt, idx) => (
              <div key={`${evt.timestamp}-${idx}`} className="stream-event-item">
                <div className="stream-event-left">
                  <Badge variant={getEventBadgeVariant(evt.event)} size="sm">
                    {evt.event}
                  </Badge>
                  <span className="stream-event-summary">
                    {formatPayloadSummary(evt.event, evt.payload)}
                  </span>
                </div>
                <span className="stream-event-timestamp">
                  {evt.timestamp ? evt.timestamp.substring(11, 19) + ' UTC' : ''}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="streams-empty-container">
            <div className="streams-empty-box">
              <div className="streams-empty-icon">
                <Radio size={44} color="var(--color-multiverse-cyan)" />
              </div>
              <h3 className="streams-empty-heading">Monitoring Event Stream</h3>
              <p className="streams-empty-desc">
                Real-time incident updates, radio transcript extractions, and status changes appear live in this feed as they occur.
              </p>
              <div className="streams-meta-pills">
                <Badge variant="neutral" size="sm">WEBSOCKET: {status}</Badge>
                <Badge variant="neutral" size="sm">DISPATCH CHANNEL: ACTIVE</Badge>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default IncidentStreamsView;
