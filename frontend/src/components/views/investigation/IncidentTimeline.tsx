import React from 'react';
import { 
  History, 
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

  return (
    <section className="inv-timeline-section" aria-label="Chronological Incident Timeline">
      {/* Timeline Section Header */}
      <div className="timeline-header">
        <div className="timeline-title-group">
          <History size={16} className="timeline-title-icon" />
          <h2 className="timeline-title">INCIDENT TIMELINE</h2>
          <span className="timeline-count-badge font-mono">
            {totalEvents} {totalEvents === 1 ? 'EVENT' : 'EVENTS'}
          </span>
        </div>

        {/* Timeline Controls */}
        <div className="timeline-controls">
          <div className="timeline-sort-group" role="group" aria-label="Timeline sort order">
            <button
              type="button"
              className={`timeline-sort-btn font-mono ${order === 'asc' ? 'active' : ''}`}
              onClick={() => setOrder('asc')}
              title="Sort oldest first"
              aria-pressed={order === 'asc'}
            >
              <ArrowUp size={12} />
              <span>ASCENDING</span>
            </button>
            <button
              type="button"
              className={`timeline-sort-btn font-mono ${order === 'desc' ? 'active' : ''}`}
              onClick={() => setOrder('desc')}
              title="Sort newest first"
              aria-pressed={order === 'desc'}
            >
              <ArrowDown size={12} />
              <span>DESCENDING</span>
            </button>
          </div>

          <button
            type="button"
            className="timeline-refresh-btn font-mono"
            onClick={() => refetch()}
            disabled={isLoading}
            title="Refresh timeline from API"
            aria-label="Refresh timeline"
          >
            <RotateCcw size={12} className={isLoading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="timeline-status-card">
          <Radio size={24} className="spinning text-multiverse-cyan" />
          <span className="font-mono text-sm">SYNTHESIZING TIMELINE FOR [{incidentId}]...</span>
        </div>
      )}

      {/* Error State */}
      {!isLoading && error && (
        <div className="timeline-status-card timeline-error">
          <AlertCircle size={24} className="text-crimson" />
          <div className="timeline-error-text">
            <strong>TIMELINE FETCH FAILED</strong>
            <p>{error}</p>
          </div>
          <button
            type="button"
            className="timeline-retry-btn font-headline"
            onClick={() => refetch()}
          >
            RETRY
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && events.length === 0 && (
        <div className="timeline-status-card">
          <Clock size={28} className="text-muted" />
          <div className="font-headline text-lg uppercase">NO TIMELINE EVENTS RECORDED</div>
          <p className="font-body text-sm text-secondary">
            No report fusion or priority calculation events are registered for this incident yet.
          </p>
        </div>
      )}

      {/* Populated Timeline Stream */}
      {!isLoading && !error && events.length > 0 && (
        <div className="timeline-stream-container">
          <div className="timeline-rail" />
          <ol className="timeline-list">
            {events.map((evt, idx) => {
              const formattedTime = evt.timestamp
                ? new Date(evt.timestamp).toUTCString().replace('GMT', 'UTC')
                : '--';

              const detailEntries = evt.details ? Object.entries(evt.details) : [];

              return (
                <li key={evt.event_id || idx} className="timeline-item">
                  <div className={`timeline-node ${getEventBadgeClass(evt.event_type)}`}>
                    {getEventIcon(evt.event_type)}
                  </div>

                  <article className="timeline-card" aria-label={`${evt.event_type}: ${evt.summary}`}>
                    <div className="timeline-card-header font-mono">
                      <div className="timeline-card-left">
                        <span className={`timeline-type-pill ${getEventBadgeClass(evt.event_type)}`}>
                          {evt.event_type.replace(/_/g, ' ')}
                        </span>
                        <span className="timeline-event-id font-mono">
                          ID: {evt.event_id}
                        </span>
                      </div>
                      <div className="timeline-card-time font-mono">
                        <Clock size={11} />
                        <span>{formattedTime}</span>
                      </div>
                    </div>

                    <div className="timeline-summary font-body">
                      {evt.summary}
                    </div>

                    {detailEntries.length > 0 && (
                      <div className="timeline-details-grid font-mono">
                        {detailEntries.map(([k, v]) => (
                          <div key={k} className="timeline-detail-tag">
                            <span className="td-key">{k}:</span>
                            <span className="td-val">
                              {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </article>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
};
