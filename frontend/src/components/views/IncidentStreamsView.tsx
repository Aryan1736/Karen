import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  Rss,
  Radio,
  Trash2,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  Search,
  Activity,
  Filter,
  Sparkles,
  ShieldAlert,
  SlidersHorizontal,
} from 'lucide-react';
import { Badge, BadgeVariant, Button } from '../ui';
import { useWebSocket } from '../../context/WebSocketContext';
import { useNavigation } from '../../context/NavigationContext';
import { RealtimeEvent, RealtimeEventType } from '../../types/incident';
import './IncidentStreamsView.css';

export type StreamFilterCategory = 'ALL' | 'INCIDENTS' | 'STATUS' | 'SIMULATION' | 'SYSTEM';

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
      summary = `New Incident Created${locText ? ` ${locText}` : ''} [${incidentType || 'UNCLASSIFIED'}]`;
      if (p.people_at_risk?.count && p.people_at_risk.count > 0) {
        detail = `${p.people_at_risk.count} civilian(s) assessed at risk. Response required: ${(p.required_response || []).join(', ') || 'SEARCH_AND_RESCUE'}.`;
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
        summary = `Priority shifted: ${p.previous_priority_score.toFixed(1)} → ${p.new_priority_score.toFixed(1)} (${sign}${delta.toFixed(1)})`;
      } else {
        summary = `Incident intelligence updated${incidentType ? ` for ${incidentType}` : ''}`;
      }

      if (p.corroboration?.explanation) {
        detail = p.corroboration.explanation;
      } else if (p.explanation) {
        detail = p.explanation;
      } else if (p.corroboration?.report_count) {
        detail = `Corroborated by ${p.corroboration.report_count} linked report(s). Corroboration score: ${Math.round((p.corroboration.score || 0) * 100)}%.`;
      }
      break;
    }

    case 'INCIDENT_STATUS_CHANGED': {
      oldStatus = p.old_status || 'UNKNOWN';
      newStatus = p.new_status || 'UNKNOWN';
      summary = `Status transition: ${oldStatus} → ${newStatus}`;
      detail = `Operational state transitioned by sovereign operator review or automated escalation rule.`;
      break;
    }

    case 'SIMULATION_PULSE': {
      isSynthetic = true;
      injectedCount = typeof p.injected_count === 'number' ? p.injected_count : 0;
      totalSimulated = typeof p.total_simulated === 'number' ? p.total_simulated : 0;
      scenario = p.scenario || 'emergency_simulation';
      summary = `Synthetic crisis dispatch pulse injected (${injectedCount} reports)`;
      detail = `Scenario: "${scenario}" | Cumulative simulated reports: ${totalSimulated}.`;
      break;
    }

    case 'PING':
    case 'PONG': {
      summary = `${eventType} keepalive heartbeat frame received`;
      detail = `Transport WebSocket duplex communication channel verified operational.`;
      break;
    }

    default: {
      summary = `Operational event [${eventType}] received`;
      try {
        detail = JSON.stringify(p);
      } catch {
        detail = null;
      }
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

export const IncidentStreamsView: React.FC = () => {
  const { status, events, reconnect, clearEvents } = useWebSocket();
  const { navigateToIncident, setIsSimulatorModalOpen } = useNavigation();

  const [activeFilter, setActiveFilter] = useState<StreamFilterCategory>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showRestoredNotice, setShowRestoredNotice] = useState<boolean>(false);

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
      }, 5000);
      return () => clearTimeout(timer);
    }
    prevStatusRef.current = status;
  }, [status]);

  // Parse all events into high-signal structured models
  const parsedEvents = useMemo(() => {
    return events.map((evt, idx) => parseStreamEvent(evt, idx === 0, idx));
  }, [events]);

  // Real metric breakdowns across buffer
  const metrics = useMemo(() => {
    const total = parsedEvents.length;
    let incidentCount = 0;
    let statusCount = 0;
    let simCount = 0;
    let systemCount = 0;

    for (const pe of parsedEvents) {
      if (pe.eventType === 'INCIDENT_CREATED' || pe.eventType === 'INCIDENT_UPDATED') {
        incidentCount++;
      } else if (pe.eventType === 'INCIDENT_STATUS_CHANGED') {
        statusCount++;
      } else if (pe.eventType === 'SIMULATION_PULSE' || pe.isSynthetic) {
        simCount++;
      } else if (pe.eventType === 'PING' || pe.eventType === 'PONG') {
        systemCount++;
      }
    }

    return { total, incidentCount, statusCount, simCount, systemCount };
  }, [parsedEvents]);

  // Apply active category filter and search query
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
    } else if (activeFilter === 'SYSTEM') {
      result = result.filter((e) => e.eventType === 'PING' || e.eventType === 'PONG');
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
      case 'PING':
      case 'PONG': return 'neutral';
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
    <div className="incident-streams-view" role="region" aria-label="Live Incident Streams">
      {/* 1. Header: Live Incident Streams, Event Count, Truthful Connection Status */}
      <header className="streams-header">
        <div className="streams-title-group">
          <Rss size={20} className="streams-header-icon" />
          <h1 className="streams-title">LIVE INCIDENT STREAMS</h1>
          <Badge variant="neutral" size="sm" className="streams-count-badge">
            {events.length} EVENTS RECORDED
          </Badge>
          {events.length > 0 && (
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

          {events.length > 0 && (
            <Button
              variant="secondary"
              size="sm"
              onClick={clearEvents}
              title="Clear event stream buffer"
              className="streams-action-btn"
            >
              <Trash2 size={13} style={{ marginRight: 5 }} />
              CLEAR STREAM
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
              <RefreshCw size={13} style={{ marginRight: 5 }} />
              RECONNECT
            </Button>
          )}
        </div>
      </header>

      {/* Disconnected Notice Banner */}
      {status !== 'CONNECTED' && (
        <div className="streams-alert-banner paused-banner" role="alert">
          <div className="streams-banner-content">
            <AlertTriangle size={16} className="streams-banner-icon" />
            <div className="streams-banner-text">
              <strong>LIVE UPDATES PAUSED</strong> — Connection to dispatch server lost. Background retry active (exponential backoff).
            </div>
          </div>
          <Button variant="hazard" size="sm" onClick={reconnect}>
            RECONNECT NOW
          </Button>
        </div>
      )}

      {/* Restored Connection Notice Banner */}
      {showRestoredNotice && status === 'CONNECTED' && (
        <div className="streams-alert-banner restored-banner" role="status">
          <div className="streams-banner-content">
            <CheckCircle2 size={16} className="streams-banner-icon text-success" />
            <div className="streams-banner-text">
              <strong>LIVE CONNECTION RESTORED</strong> — Real-time event stream synchronized with emergency dispatch core.
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

      {/* 2. Main Two-Column Layout */}
      <div className="streams-layout-grid">
        {/* Left / Main Area: Chronological Event Stream */}
        <main className="streams-main-column">
          {/* Quick Filter Bar */}
          <div className="streams-filter-bar">
            <div className="streams-category-tabs" role="tablist" aria-label="Event category filters">
              <button
                className={`streams-tab-btn ${activeFilter === 'ALL' ? 'active' : ''}`}
                onClick={() => setActiveFilter('ALL')}
                role="tab"
                aria-selected={activeFilter === 'ALL'}
              >
                ALL <span className="tab-count">{metrics.total}</span>
              </button>
              <button
                className={`streams-tab-btn ${activeFilter === 'INCIDENTS' ? 'active' : ''}`}
                onClick={() => setActiveFilter('INCIDENTS')}
                role="tab"
                aria-selected={activeFilter === 'INCIDENTS'}
              >
                INCIDENTS <span className="tab-count">{metrics.incidentCount}</span>
              </button>
              <button
                className={`streams-tab-btn ${activeFilter === 'STATUS' ? 'active' : ''}`}
                onClick={() => setActiveFilter('STATUS')}
                role="tab"
                aria-selected={activeFilter === 'STATUS'}
              >
                STATUS <span className="tab-count">{metrics.statusCount}</span>
              </button>
              <button
                className={`streams-tab-btn ${activeFilter === 'SIMULATION' ? 'active' : ''}`}
                onClick={() => setActiveFilter('SIMULATION')}
                role="tab"
                aria-selected={activeFilter === 'SIMULATION'}
              >
                SIMULATION <span className="tab-count">{metrics.simCount}</span>
              </button>
              {metrics.systemCount > 0 && (
                <button
                  className={`streams-tab-btn ${activeFilter === 'SYSTEM' ? 'active' : ''}`}
                  onClick={() => setActiveFilter('SYSTEM')}
                  role="tab"
                  aria-selected={activeFilter === 'SYSTEM'}
                >
                  SYSTEM <span className="tab-count">{metrics.systemCount}</span>
                </button>
              )}
            </div>

            <div className="streams-search-box">
              <Search size={14} className="streams-search-icon" />
              <input
                type="text"
                placeholder="Filter events by ID, hazard, or keyword..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="streams-search-input"
                aria-label="Filter events"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="streams-search-clear"
                  title="Clear search"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Event Stream List */}
          <div className="streams-feed-container">
            {events.length === 0 ? (
              /* Compact, intentional tactical empty state */
              <div className="streams-empty-card" role="status">
                <div className="streams-empty-header">
                  <div className="streams-empty-beacon-icon">
                    <Radio size={28} className="pulse-svg" />
                  </div>
                  <div>
                    <h2 className="streams-empty-title">NO EVENTS YET</h2>
                    <p className="streams-empty-desc">
                      Live events will appear here when Tingle receives or processes reports.
                    </p>
                  </div>
                </div>

                <div className="streams-empty-footer">
                  <div className="streams-empty-tags">
                    <span className="tech-tag">WS: {status}</span>
                    <span className="tech-tag">DISPATCH FEED: ACTIVE</span>
                    <span className="tech-tag">BUFFER: 0/50</span>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setIsSimulatorModalOpen(true)}
                  >
                    <Sparkles size={12} style={{ marginRight: 5 }} />
                    LAUNCH SIMULATOR →
                  </Button>
                </div>
              </div>
            ) : filteredEvents.length === 0 ? (
              /* Empty filter state */
              <div className="streams-empty-filter-card">
                <Filter size={24} style={{ color: 'var(--color-text-muted)', marginBottom: 8 }} />
                <h3 className="empty-filter-title">NO MATCHING EVENTS</h3>
                <p className="empty-filter-desc">
                  No events found matching category <strong>{activeFilter}</strong>
                  {searchQuery ? ` and query "${searchQuery}"` : ''}.
                </p>
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
              <div className="streams-event-card-list">
                {filteredEvents.map((evt, idx) => (
                  <article
                    key={evt.id}
                    className={`stream-card ${evt.isLatest ? 'is-latest' : ''} ${
                      evt.isSynthetic ? 'is-synthetic' : ''
                    }`}
                  >
                    {/* Event Card Header */}
                    <div className="card-top-row">
                      <div className="card-top-left">
                        <span className="card-timestamp">{evt.timestampFormatted}</span>
                        <Badge variant={getEventBadgeVariant(evt.eventType)} size="sm">
                          {evt.eventType.replace(/_/g, ' ')}
                        </Badge>
                        {evt.isLatest && (
                          <span className="latest-indicator">
                            <span className="latest-dot" /> LATEST
                          </span>
                        )}
                      </div>

                      <div className="card-top-right">
                        {evt.isSynthetic ? (
                          <Badge variant="simulation" size="sm">
                            SYNTHETIC
                          </Badge>
                        ) : (
                          <Badge variant="neutral" size="sm">
                            LIVE DISPATCH
                          </Badge>
                        )}

                        {evt.priorityLevel && (
                          <Badge variant={getPriorityBadgeVariant(evt.priorityLevel)} size="sm">
                            {evt.priorityLevel}
                            {evt.priorityScore !== null && ` (${evt.priorityScore.toFixed(0)})`}
                          </Badge>
                        )}
                      </div>
                    </div>

                    {/* Event Card Body */}
                    <div className="card-body-section">
                      <div className="card-subject-row">
                        {evt.incidentId && (
                          <span className="card-id-pill">
                            {evt.incidentId.toUpperCase()}
                          </span>
                        )}

                        {evt.incidentType && (
                          <span className="card-hazard-pill">
                            {evt.incidentType}
                          </span>
                        )}

                        {evt.scenario && (
                          <span className="card-scenario-pill">
                            SCENARIO: {evt.scenario}
                          </span>
                        )}
                      </div>

                      <div className="card-narrative-box">
                        <p className="card-summary">{evt.summary}</p>
                        {evt.detail && <p className="card-detail">{evt.detail}</p>}
                      </div>

                      {/* Status Transition Visual */}
                      {evt.oldStatus && evt.newStatus && (
                        <div className="card-status-transition">
                          <span className="status-node status-node-old">{evt.oldStatus}</span>
                          <ArrowRight size={13} className="status-arrow-icon" />
                          <span className="status-node status-node-new">{evt.newStatus}</span>
                        </div>
                      )}

                      {/* Linked Report IDs */}
                      {evt.sourceReportIds.length > 0 && (
                        <div className="card-reports-line">
                          <span className="reports-label">LINKED REPORTS:</span>
                          {evt.sourceReportIds.map((rid) => (
                            <span key={rid} className="report-id-chip">
                              {rid}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Event Card Footer */}
                    <div className="card-bottom-row">
                      <span className="card-seq-num">
                        SEQ #{events.length - idx}
                      </span>

                      {evt.incidentId && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => evt.incidentId && navigateToIncident(evt.incidentId)}
                          title={`Open investigation view for ${evt.incidentId}`}
                          className="view-incident-btn"
                        >
                          VIEW INCIDENT
                          <ArrowRight size={12} style={{ marginLeft: 6 }} />
                        </Button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </main>

        {/* Right / Secondary Area: Live Connection, Feed Summary, and Tactical Context */}
        <aside className="streams-secondary-column" aria-label="Live Stream Controls and Metrics">
          {/* Panel 1: Live Connection & Dispatch Status */}
          <div className="tactical-panel connection-panel">
            <div className="panel-header">
              <Activity size={14} className="panel-header-icon" />
              <h2 className="panel-title">DISPATCH CONNECTION</h2>
            </div>
            <div className="panel-body">
              <div className="connection-row">
                <span className="connection-key">WEBSOCKET STATUS:</span>
                <span className={`connection-val val-${status.toLowerCase()}`}>
                  <span className={`status-orb orb-${status.toLowerCase()}`} />
                  {status}
                </span>
              </div>
              <div className="connection-row">
                <span className="connection-key">PROTOCOL / ENDPOINT:</span>
                <span className="connection-val tech-code">/ws/events</span>
              </div>
              <div className="connection-row">
                <span className="connection-key">DISPATCH FEED:</span>
                <span className="connection-val text-cyan">ACTIVE</span>
              </div>
              <div className="connection-row">
                <span className="connection-key">RECONNECT POLICY:</span>
                <span className="connection-val">EXPONENTIAL (MAX 15S)</span>
              </div>

              {status !== 'CONNECTED' ? (
                <Button
                  variant="hazard"
                  size="sm"
                  onClick={reconnect}
                  className="panel-action-btn"
                >
                  <RefreshCw size={13} style={{ marginRight: 6 }} />
                  RECONNECT WEBSOCKET
                </Button>
              ) : (
                <div className="connection-health-note">
                  <CheckCircle2 size={13} color="var(--color-system-green)" />
                  <span>Real-time event pipe connected & healthy</span>
                </div>
              )}
            </div>
          </div>

          {/* Panel 2: Live Stream Metrics */}
          <div className="tactical-panel metrics-panel">
            <div className="panel-header">
              <SlidersHorizontal size={14} className="panel-header-icon" />
              <h2 className="panel-title">STREAM BUFFER METRICS</h2>
            </div>
            <div className="panel-body">
              <div className="metric-grid">
                <div className="metric-cell">
                  <span className="metric-val">{metrics.total}</span>
                  <span className="metric-lbl">TOTAL BUFFER (MAX 50)</span>
                </div>
                <div className="metric-cell">
                  <span className="metric-val text-critical">{metrics.incidentCount}</span>
                  <span className="metric-lbl">INCIDENT EVENTS</span>
                </div>
                <div className="metric-cell">
                  <span className="metric-val text-warning">{metrics.statusCount}</span>
                  <span className="metric-lbl">STATUS TRANSITIONS</span>
                </div>
                <div className="metric-cell">
                  <span className="metric-val text-sim">{metrics.simCount}</span>
                  <span className="metric-lbl">SYNTHETIC PULSES</span>
                </div>
              </div>

              <div className="panel-controls-row">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setIsSimulatorModalOpen(true)}
                  className="panel-btn-full"
                >
                  <Sparkles size={13} style={{ marginRight: 6 }} />
                  INJECT SIMULATION
                </Button>
                {events.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={clearEvents}
                    className="panel-btn-clear"
                    title="Clear in-memory event buffer"
                  >
                    <Trash2 size={13} />
                  </Button>
                )}
              </div>
            </div>
          </div>

          {/* Panel 3: Tactical Architecture Boundaries (Product Clarity) */}
          <div className="tactical-panel reference-panel">
            <div className="panel-header">
              <ShieldAlert size={14} className="panel-header-icon" />
              <h2 className="panel-title">OPERATIONAL CONTEXT</h2>
            </div>
            <div className="panel-body context-guide-body">
              <div className="context-item">
                <span className="context-badge">COMMAND CENTER</span>
                <span className="context-text">Active incidents and tactical geographic triage.</span>
              </div>
              <div className="context-item active-context-item">
                <span className="context-badge badge-active">LIVE STREAMS</span>
                <span className="context-text">Real-time incoming dispatches and state updates.</span>
              </div>
              <div className="context-item">
                <span className="context-badge">INVESTIGATION</span>
                <span className="context-text">Forensic evidence, corroboration, and NLP factors.</span>
              </div>
              <div className="context-item">
                <span className="context-badge">AUDIT LEDGER</span>
                <span className="context-text">Immutable record of operator sovereign overrides.</span>
              </div>
              <div className="context-item">
                <span className="context-badge">SYSTEM BRIEFING</span>
                <span className="context-text">Current overall situation and executive summary.</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default IncidentStreamsView;
