import React from 'react';
import { 
  ArrowUp, 
  ArrowDown, 
  RotateCcw, 
  Clock, 
  AlertCircle, 
  Radio, 
  Layers, 
  Cpu, 
  UserCheck, 
  Sliders
} from 'lucide-react';
import { useIncidentTimeline } from '../../../hooks/useIncidentTimeline';
import './IncidentTimeline.css';

export interface IncidentTimelineProps {
  incidentId: string;
}

export const IncidentTimeline: React.FC<IncidentTimelineProps> = ({ incidentId }) => {
  const { 
    data, 
    isLoading, 
    error, 
    order, 
    setOrder, 
    refetch 
  } = useIncidentTimeline(incidentId);

  const events = data?.events || [];
  const totalEvents = data?.total_events ?? events.length;

  const getEventBadgeClass = (type: string) => {
    switch (type) {
      case 'REPORT_FUSED':
        return 'etype-fused';
      case 'PRIORITY_CALCULATED':
        return 'etype-priority';
      case 'STATUS_CHANGED':
        return 'etype-status';
      case 'HUMAN_OVERRIDE':
        return 'etype-override';
      default:
        return 'etype-default';
    }
  };

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'REPORT_FUSED':
        return <Layers size={13} />;
      case 'PRIORITY_CALCULATED':
        return <Sliders size={13} />;
      case 'STATUS_CHANGED':
        return <UserCheck size={13} />;
      case 'HUMAN_OVERRIDE':
        return <Cpu size={13} />;
      default:
        return <Clock size={13} />;
    }
  };

  const getEventName = (type: string) => {
    switch (type) {
      case 'REPORT_FUSED':
        return 'Report Correlated';
      case 'PRIORITY_CALCULATED':
        return 'Priority Computed';
      case 'STATUS_CHANGED':
        return 'Status Changed';
      case 'HUMAN_OVERRIDE':
        return 'Operator Override';
      default:
        return type.replace(/_/g, ' ');
    }
  };

  return (
    <div className="timeline-container">
      {/* Controls Bar */}
      <div className="timeline-controls-bar">
        <span className="timeline-count-label font-mono">
          {totalEvents} {totalEvents === 1 ? 'Event Recorded' : 'Events Recorded'}
        </span>

        <div className="timeline-actions">
          <div className="timeline-sort-toggle">
            <button
              type="button"
              className={`sort-pill ${order === 'desc' ? 'is-active' : ''}`}
              onClick={() => setOrder('desc')}
              title="Newest first"
            >
              <ArrowDown size={11} />
              <span>Newest</span>
            </button>
            <button
              type="button"
              className={`sort-pill ${order === 'asc' ? 'is-active' : ''}`}
              onClick={() => setOrder('asc')}
              title="Oldest first"
            >
              <ArrowUp size={11} />
              <span>Oldest</span>
            </button>
          </div>

          <button
            type="button"
            className="timeline-refresh-btn"
            onClick={() => refetch()}
            disabled={isLoading}
            title="Refresh timeline"
          >
            <RotateCcw size={12} className={isLoading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="timeline-empty-card">
          <Radio size={20} className="spinning text-cyan" />
          <span>Loading event history...</span>
        </div>
      )}

      {/* Error State */}
      {!isLoading && error && (
        <div className="timeline-empty-card card-error">
          <AlertCircle size={20} className="text-crimson" />
          <span>{error}</span>
          <button type="button" className="retry-btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && events.length === 0 && (
        <div className="timeline-empty-card">
          <Clock size={20} className="text-muted" />
          <span>No timeline events recorded yet.</span>
        </div>
      )}

      {/* Events List */}
      {!isLoading && !error && events.length > 0 && (
        <div className="timeline-flow">
          {events.map((evt, idx) => {
            const formattedTime = evt.timestamp
              ? new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
              : '--';

            const detailEntries = evt.details ? Object.entries(evt.details) : [];

            return (
              <div key={evt.event_id || idx} className="timeline-flow-item">
                <div className={`timeline-step-icon ${getEventBadgeClass(evt.event_type)}`}>
                  {getEventIcon(evt.event_type)}
                </div>

                <div className="timeline-step-content">
                  <div className="step-header">
                    <span className={`step-type-tag ${getEventBadgeClass(evt.event_type)}`}>
                      {getEventName(evt.event_type)}
                    </span>
                    <span className="step-time font-mono">{formattedTime}</span>
                  </div>

                  <p className="step-summary font-body">{evt.summary}</p>

                  {detailEntries.length > 0 && (
                    <div className="step-tags">
                      {detailEntries.map(([k, v]) => (
                        <span key={k} className="step-tag font-mono">
                          {k}: <strong>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</strong>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default IncidentTimeline;
