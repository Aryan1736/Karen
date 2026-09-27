import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  Rss,
  Trash2,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  Search,
  Sparkles,
} from 'lucide-react';
import { Badge, BadgeVariant, Button } from '../ui';
import { useWebSocket } from '../../context/WebSocketContext';
import { useNavigation } from '../../context/NavigationContext';
import { RealtimeEvent, RealtimeEventType } from '../../types/incident';
import './IncidentStreamsView.css';

export type StreamFilterCategory = 'ALL' | 'INCIDENTS' | 'STATUS' | 'SIMULATION';

interface ParsedEventDetails {
  id: string;
  timestampFormatted: string;
  eventType: RealtimeEventType;
  incidentId: string | null;
  incidentType: string | null;
  priorityLevel: string | null;
  priorityScore: number | null;
  isSynthetic: boolean;
  summary: string;
  detail: string | null;
  sourceReportIds: string[];
  oldStatus?: string;
  newStatus?: string;
  injectedCount?: number;
  totalSimulated?: number;
  scenario?: string;
  isLatest: boolean;
}

function formatIncidentType(rawType: string): string {
  switch (rawType) {
    case 'FLOOD_FLASH_FLOOD': return 'FLASH FLOOD';
    case 'FIRE_WILDFIRE_EXPLOSION': return 'FIRE / EXPLOSION';
    case 'STRUCTURAL_COLLAPSE': return 'STRUCTURAL COLLAPSE';
    case 'EARTHQUAKE_LANDSLIDE': return 'EARTHQUAKE / LANDSLIDE';
    case 'SEVERE_WEATHER_STORM': return 'SEVERE STORM';
    case 'MEDICAL_EMERGENCY': return 'MEDICAL EMERGENCY';
    case 'CIVIL_UNREST_ACTIVE_THREAT': return 'ACTIVE THREAT';
    case 'UTILITY_INFRASTRUCTURE_FAILURE': return 'UTILITY FAILURE';
    case 'OTHER_GENERAL_INCIDENT': return 'GENERAL INCIDENT';
    default: return rawType.replace(/_/g, ' ');
  }
}

function formatUtcTimestamp(isoString?: string): string {
  if (!isoString) return '--:--:-- UTC';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) {
      if (isoString.length >= 19) {
        return isoString.substring(11, 19) + ' UTC';
      }
      return isoString;
    }
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())} UTC`;
  } catch {
    return '--:--:-- UTC';
  }
}

function parseStreamEvent(evt: RealtimeEvent, isLatest: boolean, index: number): ParsedEventDetails {
  const p = (evt.payload && typeof evt.payload === 'object' ? evt.payload : {}) as Record<string, any>;
  const eventType = evt.event;

  let incidentId: string | null = null;
  let incidentType: string | null = null;
  let priorityLevel: string | null = null;
  let priorityScore: number | null = null;
  let isSynthetic = Boolean(p.is_synthetic);
  let summary = '';
  let detail: string | null = null;
  let sourceReportIds: string[] = [];
  let oldStatus: string | undefined;
  let newStatus: string | undefined;
  let injectedCount: number | undefined;
  let totalSimulated: number | undefined;
  let scenario: string | undefined;

  if (p.incident_id && typeof p.incident_id === 'string') {
    incidentId = p.incident_id;
  }

  if (p.incident_type && typeof p.incident_type === 'string') {
    incidentType = formatIncidentType(p.incident_type);
  }

  if (Array.isArray(p.source_report_ids)) {
    sourceReportIds = p.source_report_ids;
  } else if (p.latest_report_id && typeof p.latest_report_id === 'string') {
    sourceReportIds = [p.latest_report_id];
  }

  switch (eventType) {
    case 'INCIDENT_CREATED': {
      priorityLevel = p.priority?.level || p.urgency || null;
      priorityScore = typeof p.priority?.score === 'number' ? p.priority.score : null;
      const locText = p.location?.text ? `at ${p.location.text}` : '';
      summary = `Incident established${locText ? ` ${locText}` : ''} [${incidentType || 'UNCLASSIFIED'}]`;
      if (p.people_at_risk?.count && p.people_at_risk.count > 0) {
        detail = `${p.people_at_risk.count} civilian(s) at risk. Response: ${(p.required_response || []).join(', ') || 'SEARCH_AND_RESCUE'}.`;
      } else if (p.priority?.explanation) {
        detail = p.priority.explanation;
      }
      break;
    }

    case 'INCIDENT_UPDATED': {
      priorityLevel = p.new_priority_level || p.priority?.level || null;
      priorityScore = typeof p.new_priority_score === 'number'
        ? p.new_priority_score
        : (typeof p.priority?.score === 'number' ? p.priority.score : null);

      if (typeof p.previous_priority_score === 'number' && typeof p.new_priority_score === 'number') {
        const delta = p.new_priority_score - p.previous_priority_score;
        const sign = delta >= 0 ? '+' : '';
        summary = `Priority score shifted: ${p.previous_priority_score.toFixed(1)} → ${p.new_priority_score.toFixed(1)} (${sign}${delta.toFixed(1)})`;
      } else {
        summary = `Incident intelligence updated${incidentType ? ` (${incidentType})` : ''}`;
      }

      if (p.corroboration?.explanation) {
        detail = p.corroboration.explanation;
      } else if (p.explanation) {
        detail = p.explanation;
      } else if (p.corroboration?.report_count) {
        detail = `Corroborated by ${p.corroboration.report_count} linked report(s).`;
      }
      break;
    }

    case 'INCIDENT_STATUS_CHANGED': {
      oldStatus = p.old_status || 'UNKNOWN';
      newStatus = p.new_status || 'UNKNOWN';
      summary = `Status transition: ${oldStatus} → ${newStatus}`;
      detail = `Operational state transitioned by sovereign operator review.`;
      break;
    }

    case 'SIMULATION_PULSE': {
      isSynthetic = true;
      injectedCount = typeof p.injected_count === 'number' ? p.injected_count : 0;
      totalSimulated = typeof p.total_simulated === 'number' ? p.total_simulated : 0;
      scenario = p.scenario || 'emergency_simulation';
      summary = `Synthetic dispatch pulse injected (${injectedCount} reports)`;
      detail = `Scenario: "${scenario}" | Total simulated: ${totalSimulated}.`;
      break;
    }

    case 'PING':
    case 'PONG': {
      summary = `${eventType} keepalive heartbeat frame received`;
      break;
    }

    default: {
      summary = `Operational event [${eventType}] received`;
    }
  }

  return {
    id: `${evt.timestamp || Date.now()}-${eventType}-${index}`,
    timestampFormatted: formatUtcTimestamp(evt.timestamp),
    eventType,
    incidentId,
    incidentType,
    priorityLevel,
    priorityScore,
    isSynthetic,
    summary,
    detail,
    sourceReportIds,
    oldStatus,
    newStatus,
    injectedCount,
    totalSimulated,
    scenario,
    isLatest,
  };
}

const INITIAL_DEMO_EVENTS: RealtimeEvent[] = [
  {
    event: 'INCIDENT_UPDATED',
    timestamp: '2026-09-27T01:53:38Z',
    payload: {
      incident_id: 'inc-78f90e68-a88d-4751-ae3b-920945c13060',
      incident_type: 'STRUCTURAL_COLLAPSE',
      previous_priority_score: 55.0,
      new_priority_score: 60.2,
      new_priority_level: 'HIGH',
      explanation: 'Operator sovereign override: Urgency escalated to CRITICAL. Reason: Verified via drone feed - civilians trapped under rubble in basement.',
      is_synthetic: true,
      corroboration: {
        report_count: 1,
        independent_source_count: 1,
        score: 0.36,
        explanation: 'Single eyewitness report corroborated by operator drone surveillance.'
      }
    }
  },
  {
    event: 'INCIDENT_CREATED',
    timestamp: '2026-09-27T01:53:24Z',
    payload: {
      incident_id: 'inc-78f90e68-a88d-4751-ae3b-920945c13060',
      incident_type: 'STRUCTURAL_COLLAPSE',
      urgency: 'CRITICAL',
      location: { text: 'Patia Square', latitude: 20.355, longitude: 85.818, precision: 'exact' },
      priority: { score: 60.2, level: 'HIGH', explanation: 'Classified as HIGH priority (60.2) driven by Urgency: CRITICAL' },
      is_synthetic: true,
      source_report_ids: ['rep-579046a5-cee5-4b3e-b7fd-8d37452f5596'],
      required_response: ['SEARCH_AND_RESCUE', 'MEDICAL_EMS']
    }
  },
  {
    event: 'INCIDENT_STATUS_CHANGED',
    timestamp: '2026-09-27T01:52:10Z',
    payload: {
      incident_id: 'inc-a2cf1e6b-6e32-41fa-8847-91ddbb2fa9e9',
      old_status: 'NEW',
      new_status: 'ACTIVE'
    }
  },
  {
    event: 'INCIDENT_CREATED',
    timestamp: '2026-09-27T01:51:56Z',
    payload: {
      incident_id: 'inc-a2cf1e6b-6e32-41fa-8847-91ddbb2fa9e9',
      incident_type: 'FLOOD_FLASH_FLOOD',
      urgency: 'CRITICAL',
      location: { text: 'Rasulgarh underpass', latitude: 20.2961, longitude: 85.8245, precision: 'approximate' },
      priority: { score: 57.95, level: 'MEDIUM', explanation: 'Severe flash flooding near underpass, two vehicles submerged' },
      is_synthetic: true,
      source_report_ids: ['rep-0b909e8e-9245-4bfd-9186-314743e62dde', 'rep-d22a6835-2a9b-4d24-ad74-124afd1b6688'],
      required_response: ['SEARCH_AND_RESCUE']
    }
  },
  {
    event: 'INCIDENT_CREATED',
    timestamp: '2026-09-27T01:53:25Z',
    payload: {
      incident_id: 'inc-d2e920b5-bd8f-4e4e-a482-403354bd8bbd',
      incident_type: 'FIRE_WILDFIRE_EXPLOSION',
      urgency: 'MEDIUM',
      location: { text: 'Mancheswar Industrial Estate', latitude: 20.3200, longitude: 85.8500, precision: 'approximate' },
      priority: { score: 28.95, level: 'LOW', explanation: 'Industrial warehouse fire, chemical drums exploding' },
      is_synthetic: true,
      source_report_ids: ['rep-48f8a32d-304b-48ae-94a2-eb417ceb6094'],
      required_response: ['FIRE_HAZMAT']
    }
  },
  {
    event: 'SIMULATION_PULSE',
    timestamp: '2026-09-27T01:53:20Z',
    payload: {
      injected_count: 3,
      total_simulated: 4,
      scenario: 'bhubaneswar_monsoon_crisis'
    }
  }
];

export const IncidentStreamsView: React.FC = () => {
  const { status, events, reconnect, clearEvents } = useWebSocket();
  const { navigateToIncident, setIsSimulatorModalOpen } = useNavigation();

  const [activeFilter, setActiveFilter] = useState<StreamFilterCategory>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showRestoredNotice, setShowRestoredNotice] = useState<boolean>(false);
  const [hasUserCleared, setHasUserCleared] = useState<boolean>(false);

  const prevStatusRef = useRef(status);

  // Monitor connection transitions to truthfully communicate restoration
  useEffect(() => {
    if (
      (prevStatusRef.current === 'DISCONNECTED' || prevStatusRef.current === 'ERROR') &&
      status === 'CONNECTED'
    ) {
      setShowRestoredNotice(true);
      const timer = setTimeout(() => {
        setShowRestoredNotice(false);
      }, 4000);
      return () => clearTimeout(timer);
    }
    prevStatusRef.current = status;
  }, [status]);

  // Use preloaded events when live buffer has zero events (unless explicitly cleared by operator)
  const activeEvents = useMemo(() => {
    if (events.length > 0) return events;
    if (hasUserCleared) return [];
    return INITIAL_DEMO_EVENTS;
  }, [events, hasUserCleared]);

  const isDemoFallback = events.length === 0 && !hasUserCleared;

  // Parse events into high-density models
  const parsedEvents = useMemo(() => {
    return activeEvents.map((evt, idx) => parseStreamEvent(evt, idx === 0, idx));
  }, [activeEvents]);

  // Counts
  const counts = useMemo(() => {
    let incidentCount = 0;
    let statusCount = 0;
    let simCount = 0;

    for (const pe of parsedEvents) {
      if (pe.eventType === 'INCIDENT_CREATED' || pe.eventType === 'INCIDENT_UPDATED') {
        incidentCount++;
      } else if (pe.eventType === 'INCIDENT_STATUS_CHANGED') {
        statusCount++;
      } else if (pe.eventType === 'SIMULATION_PULSE' || pe.isSynthetic) {
        simCount++;
      }
    }

    return { total: parsedEvents.length, incidentCount, statusCount, simCount };
  }, [parsedEvents]);

  // Filter & Search
  const filteredEvents = useMemo(() => {
    let result = parsedEvents;

    if (activeFilter === 'INCIDENTS') {
      result = result.filter(
        (e) => e.eventType === 'INCIDENT_CREATED' || e.eventType === 'INCIDENT_UPDATED'
      );
    } else if (activeFilter === 'STATUS') {
      result = result.filter((e) => e.eventType === 'INCIDENT_STATUS_CHANGED');
    } else if (activeFilter === 'SIMULATION') {
      result = result.filter((e) => e.eventType === 'SIMULATION_PULSE' || e.isSynthetic);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter((e) => {
        return (
          e.summary.toLowerCase().includes(q) ||
          (e.detail && e.detail.toLowerCase().includes(q)) ||
          (e.incidentId && e.incidentId.toLowerCase().includes(q)) ||
          (e.incidentType && e.incidentType.toLowerCase().includes(q)) ||
          e.eventType.toLowerCase().includes(q) ||
          (e.scenario && e.scenario.toLowerCase().includes(q)) ||
          e.sourceReportIds.some((r) => r.toLowerCase().includes(q))
        );
      });
    }

    return result;
  }, [parsedEvents, activeFilter, searchQuery]);

  const getEventBadgeVariant = (eventType: RealtimeEventType): BadgeVariant => {
    switch (eventType) {
      case 'INCIDENT_CREATED': return 'p0-critical';
      case 'INCIDENT_UPDATED': return 'p1-high';
      case 'INCIDENT_STATUS_CHANGED': return 'p2-medium';
      case 'SIMULATION_PULSE': return 'simulation';
      default: return 'neutral';
    }
  };

  const getPriorityBadgeVariant = (level?: string | null): BadgeVariant => {
    switch (level?.toUpperCase()) {
      case 'CRITICAL': return 'p0-critical';
      case 'HIGH': return 'p1-high';
      case 'MEDIUM': return 'p2-medium';
      case 'LOW': return 'p3-low';
      case 'NEEDS_REVIEW': return 'needs-review';
      default: return 'neutral';
    }
  };

  return (
    <div className="incident-streams-view full-width-console" role="region" aria-label="Live Incident Streams">
      {/* 1. Header Bar: Title, Connection Status, Actions */}
      <header className="streams-header">
        <div className="streams-title-group">
          <Rss size={18} className="streams-header-icon" />
          <h1 className="streams-title">LIVE INCIDENT STREAMS</h1>
          <Badge variant="neutral" size="sm" className="streams-count-badge">
            {activeEvents.length} RECORDED
          </Badge>
          {isDemoFallback && (
            <Badge variant="simulation" size="sm" title="Preloaded with existing backend incident records">
              DEMO FEED
            </Badge>
          )}
          {activeEvents.length > 0 && (
            <span className="streams-last-utc">
              LATEST: {parsedEvents[0]?.timestampFormatted}
            </span>
          )}
        </div>

        <div className="streams-header-actions">
          <Badge
            variant={status === 'CONNECTED' ? 'verified' : status === 'CONNECTING' ? 'p2-medium' : 'p0-critical'}
            size="sm"
            className="streams-connection-badge"
          >
            STATUS: {status}
          </Badge>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsSimulatorModalOpen(true)}
            className="streams-action-btn"
            title="Open Simulator to inject crisis reports"
          >
            <Sparkles size={12} style={{ marginRight: 5 }} />
            SIMULATE
          </Button>

          {activeEvents.length > 0 && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                clearEvents();
                setHasUserCleared(true);
              }}
              title="Clear event stream buffer"
              className="streams-action-btn"
            >
              <Trash2 size={12} style={{ marginRight: 4 }} />
              CLEAR
            </Button>
          )}

          {hasUserCleared && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setHasUserCleared(false)}
              title="Restore demo stream events"
              className="streams-action-btn"
            >
              RESTORE DEMO
            </Button>
          )}

          {status !== 'CONNECTED' && (
            <Button
              variant="hazard"
              size="sm"
              onClick={reconnect}
              title="Reconnect to dispatch WebSocket"
              className="streams-action-btn"
            >
              <RefreshCw size={12} style={{ marginRight: 4 }} />
              RECONNECT
            </Button>
          )}
        </div>
      </header>

      {/* Disconnected Alert Banner */}
      {status !== 'CONNECTED' && (
        <div className="streams-alert-banner paused-banner" role="alert">
          <div className="streams-banner-content">
            <AlertTriangle size={15} className="streams-banner-icon" />
            <div className="streams-banner-text">
              <strong>LIVE UPDATES PAUSED</strong> — Connection to dispatch core offline. Automatic reconnect in background.
            </div>
          </div>
          <Button variant="hazard" size="sm" onClick={reconnect}>
            RECONNECT NOW
          </Button>
        </div>
      )}

      {/* Connection Restored Banner */}
      {showRestoredNotice && status === 'CONNECTED' && (
        <div className="streams-alert-banner restored-banner" role="status">
          <div className="streams-banner-content">
            <CheckCircle2 size={15} className="streams-banner-icon text-success" />
            <div className="streams-banner-text">
              <strong>LIVE CONNECTION RESTORED</strong> — Real-time event stream synchronized.
            </div>
          </div>
          <button
            className="streams-banner-dismiss"
            onClick={() => setShowRestoredNotice(false)}
            aria-label="Dismiss notice"
          >
            ✕
          </button>
        </div>
      )}

      {/* 2. Utility & Filter Row */}
      <div className="streams-toolbar">
        <div className="streams-filter-group" role="tablist" aria-label="Event category filters">
          <button
            className={`filter-chip ${activeFilter === 'ALL' ? 'active' : ''}`}
            onClick={() => setActiveFilter('ALL')}
            role="tab"
            aria-selected={activeFilter === 'ALL'}
          >
            ALL [{counts.total}]
          </button>
          <button
            className={`filter-chip ${activeFilter === 'INCIDENTS' ? 'active' : ''}`}
            onClick={() => setActiveFilter('INCIDENTS')}
            role="tab"
            aria-selected={activeFilter === 'INCIDENTS'}
          >
            INCIDENTS [{counts.incidentCount}]
          </button>
          <button
            className={`filter-chip ${activeFilter === 'STATUS' ? 'active' : ''}`}
            onClick={() => setActiveFilter('STATUS')}
            role="tab"
            aria-selected={activeFilter === 'STATUS'}
          >
            STATUS [{counts.statusCount}]
          </button>
          <button
            className={`filter-chip ${activeFilter === 'SIMULATION' ? 'active' : ''}`}
            onClick={() => setActiveFilter('SIMULATION')}
            role="tab"
            aria-selected={activeFilter === 'SIMULATION'}
          >
            SIMULATION [{counts.simCount}]
          </button>
        </div>

        <div className="streams-search-wrap">
          <Search size={13} className="search-icon" />
          <input
            type="text"
            placeholder="Search by ID, keyword, hazard..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="terminal-search-input"
            aria-label="Filter events"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="search-clear-btn"
              title="Clear search"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* 3. Full-Width Event Stream Table / Ledger */}
      <main className="streams-ledger-container">
        {/* Ledger Header Strip */}
        <div className="ledger-header-row">
          <div className="col-time">TIME (UTC)</div>
          <div className="col-event">EVENT TYPE</div>
          <div className="col-id">TARGET ID</div>
          <div className="col-details">OPERATIONAL SUMMARY & TELEMETRY DELTA</div>
          <div className="col-priority">PRIORITY</div>
          <div className="col-source">SOURCE</div>
          <div className="col-action">ACTION</div>
        </div>

        {/* Ledger Body */}
        <div className="ledger-body">
          {activeEvents.length === 0 ? (
            /* Authentic Standby Terminal State */
            <div className="stream-standby-banner" role="status">
              <div className="standby-line">
                <span className="standby-dot" />
                <span className="standby-title">DISPATCH STREAM STANDBY</span>
                <span className="standby-sep">•</span>
                <span className="standby-meta">WS: {status}</span>
                <span className="standby-sep">•</span>
                <span className="standby-meta">ENDPOINT: /ws/events</span>
                <span className="standby-sep">•</span>
                <span className="standby-meta">BUFFER: 0/50</span>
              </div>
              <p className="standby-desc">
                Awaiting incoming field reports, triage correlations, or status transitions from dispatch.
              </p>
              <div className="standby-actions">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setIsSimulatorModalOpen(true)}
                >
                  <Sparkles size={12} style={{ marginRight: 6 }} />
                  TRIGGER TEST PULSE IN SIMULATOR →
                </Button>
              </div>
            </div>
          ) : filteredEvents.length === 0 ? (
            /* Empty Filter State */
            <div className="ledger-empty-filter">
              <span>NO EVENTS MATCHING FILTER [{activeFilter}]{searchQuery ? ` AND QUERY "${searchQuery}"` : ''}</span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setActiveFilter('ALL');
                  setSearchQuery('');
                }}
              >
                RESET FILTERS
              </Button>
            </div>
          ) : (
            filteredEvents.map((evt) => (
              <div
                key={evt.id}
                className={`ledger-row ${evt.isLatest ? 'is-latest' : ''} ${
                  evt.isSynthetic ? 'is-synthetic' : ''
                }`}
              >
                {/* 1. Time */}
                <div className="col-time">
                  <span className="row-timestamp">{evt.timestampFormatted}</span>
                  {evt.isLatest && (
                    <span className="row-latest-tag" title="Most recent event">
                      <span className="pip" /> NEW
                    </span>
                  )}
                </div>

                {/* 2. Event Type */}
                <div className="col-event">
                  <Badge variant={getEventBadgeVariant(evt.eventType)} size="sm">
                    {evt.eventType.replace(/_/g, ' ')}
                  </Badge>
                </div>

                {/* 3. Target ID */}
                <div className="col-id">
                  {evt.incidentId ? (
                    <span className="id-chip">{evt.incidentId.toUpperCase()}</span>
                  ) : evt.scenario ? (
                    <span className="scenario-chip">{evt.scenario}</span>
                  ) : (
                    <span className="dim-chip">—</span>
                  )}
                </div>

                {/* 4. Operational Summary & Details */}
                <div className="col-details">
                  <div className="summary-line">
                    <span className="primary-summary">{evt.summary}</span>
                    {evt.incidentType && (
                      <span className="hazard-chip">{evt.incidentType}</span>
                    )}
                  </div>

                  {evt.detail && (
                    <div className="secondary-detail">{evt.detail}</div>
                  )}

                  {/* Old Status -> New Status */}
                  {evt.oldStatus && evt.newStatus && (
                    <div className="status-flow">
                      <span className="flow-node flow-old">{evt.oldStatus}</span>
                      <ArrowRight size={11} className="flow-arrow" />
                      <span className="flow-node flow-new">{evt.newStatus}</span>
                    </div>
                  )}

                  {/* Linked report IDs */}
                  {evt.sourceReportIds.length > 0 && (
                    <div className="linked-reports">
                      <span className="reports-label">REPORTS:</span>
                      {evt.sourceReportIds.map((rid) => (
                        <span key={rid} className="report-pip">
                          {rid}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* 5. Priority */}
                <div className="col-priority">
                  {evt.priorityLevel ? (
                    <Badge variant={getPriorityBadgeVariant(evt.priorityLevel)} size="sm">
                      {evt.priorityLevel}
                      {evt.priorityScore !== null ? ` ${evt.priorityScore.toFixed(0)}` : ''}
                    </Badge>
                  ) : (
                    <span className="dim-text">—</span>
                  )}
                </div>

                {/* 6. Source */}
                <div className="col-source">
                  {evt.isSynthetic ? (
                    <Badge variant="simulation" size="sm">
                      SYNTHETIC
                    </Badge>
                  ) : (
                    <Badge variant="neutral" size="sm">
                      LIVE
                    </Badge>
                  )}
                </div>

                {/* 7. Action */}
                <div className="col-action">
                  {evt.incidentId ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => evt.incidentId && navigateToIncident(evt.incidentId)}
                      title={`Inspect ${evt.incidentId} in investigation view`}
                      className="inspect-btn"
                    >
                      INSPECT
                      <ArrowRight size={11} style={{ marginLeft: 4 }} />
                    </Button>
                  ) : (
                    <span className="dim-text">—</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
};

export default IncidentStreamsView;
