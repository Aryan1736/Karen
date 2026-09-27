import React, { useState, useCallback } from 'react';
import { 
  Search, 
  ArrowLeft, 
  ShieldAlert, 
  AlertTriangle, 
  Radio, 
  WifiOff,
  RotateCcw,
  LayoutDashboard,
  FileText,
  History,
  ShieldCheck,
  CheckCircle2
} from 'lucide-react';
import { Button } from '../ui';
import { useNavigation } from '../../context/NavigationContext';
import { useIncidentDetail } from '../../hooks/useIncidentDetail';
import { useIncidents } from '../../hooks/useIncidents';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import {
  InvestigationHeader,
  IncidentFactPanel,
  EvidenceReportList,
  IncidentTimeline,
  AuditTracePanel,
  InvestigationActionWizard
} from './investigation';
import './InvestigationView.css';

type InvestigationTab = 'overview' | 'reports' | 'timeline' | 'action' | 'audit';

export const InvestigationView: React.FC = () => {
  const { 
    selectedIncidentId, 
    setSelectedIncidentId, 
    setActiveView 
  } = useNavigation();

  const { isOnline, checkHealth } = useBackendHealth();
  const { incidents: availableIncidents } = useIncidents('ALL');
  const { data, isLoading, error, refetch } = useIncidentDetail(selectedIncidentId);

  const [activeTab, setActiveTab] = useState<InvestigationTab>('overview');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterSeverity, setFilterSeverity] = useState<'ALL' | 'CRITICAL' | 'HIGH' | 'NEEDS_REVIEW' | 'VERIFIED'>('ALL');

  const handleBackToDeck = useCallback(() => {
    setActiveView('command-deck');
  }, [setActiveView]);

  const handleMutationSuccess = useCallback(async () => {
    // Re-fetch incident detail from backend to synchronize incident, full audit trail, and priority recalculations
    await refetch();
  }, [refetch]);

  // Filter available incidents for forensic case directory
  const filteredIncidents = availableIncidents.filter((inc) => {
    const matchesSearch = !searchQuery.trim() || 
      inc.incident_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (inc.location?.text && inc.location.text.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (inc.incident_type && inc.incident_type.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;

    if (filterSeverity === 'CRITICAL') return inc.priority?.level === 'CRITICAL' || inc.urgency === 'CRITICAL';
    if (filterSeverity === 'HIGH') return inc.priority?.level === 'HIGH' || inc.urgency === 'HIGH';
    if (filterSeverity === 'NEEDS_REVIEW') return inc.status === 'NEEDS_REVIEW';
    if (filterSeverity === 'VERIFIED') return inc.status === 'VERIFIED';
    return true;
  });

  // STATE 1: No Incident Selected — Render Forensic Evidence Board & Dossier Directory
  if (!selectedIncidentId) {
    return (
      <div className="investigation-view pattern-halftone" role="region" aria-label="Investigation Evidence Board">
        <header className="investigation-top-header">
          <div className="investigation-header-badge-group">
            <span className="inv-badge-tape">EVIDENCE ROOM</span>
            <div className="investigation-title-combo">
              <Search size={18} className="text-cyan" />
              <h1 className="investigation-main-heading">INCIDENT FORENSIC DOSSIERS</h1>
            </div>
            <span className="inv-count-pill font-mono">{availableIncidents.length} CASE FILES</span>
          </div>
          <div className="investigation-header-actions">
            <Button 
              type="button"
              variant="secondary" 
              size="sm" 
              onClick={handleBackToDeck}
              aria-label="Return to Command Deck"
            >
              <ArrowLeft size={14} style={{ marginRight: 6 }} />
              RETURN TO COMMAND DECK
            </Button>
          </div>
        </header>

        <main className="investigation-dossier-workspace">
          {/* Dossier Control Filter Bar */}
          <div className="dossier-filter-strip">
            <div className="dossier-search-bar">
              <Search size={14} className="dossier-search-icon" />
              <input
                type="text"
                className="dossier-search-input font-mono"
                placeholder="SEARCH DOSSIERS BY ID, LOCATION, OR DISPATCH TYPE..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search incident dossiers"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="dossier-search-clear"
                  onClick={() => setSearchQuery('')}
                  title="Clear search"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="dossier-filter-buttons">
              {(['ALL', 'CRITICAL', 'HIGH', 'NEEDS_REVIEW', 'VERIFIED'] as const).map((sev) => (
                <button
                  key={sev}
                  type="button"
                  className={`dossier-filter-btn font-headline ${filterSeverity === sev ? 'is-active' : ''}`}
                  onClick={() => setFilterSeverity(sev)}
                >
                  {sev.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Dossier Grid */}
          {filteredIncidents.length > 0 ? (
            <div className="dossier-grid">
              {filteredIncidents.map((inc) => {
                const priorityScore = inc.priority?.score != null ? Math.round(inc.priority.score) : 0;
                const priorityLevel = inc.priority?.level || 'MEDIUM';
                const reportsCount = inc.source_report_ids?.length || inc.corroboration?.report_count || 1;
                const shortId = inc.incident_id.replace(/^inc-/, '').substring(0, 8).toUpperCase();
                const isCritical = priorityLevel === 'CRITICAL' || inc.urgency === 'CRITICAL';

                return (
                  <article 
                    key={inc.incident_id} 
                    className={`dossier-card ${isCritical ? 'dossier-critical' : ''}`}
                    onClick={() => {
                      setSelectedIncidentId(inc.incident_id);
                      setActiveTab('overview');
                    }}
                  >
                    {/* Top Case Tape Header */}
                    <div className="dossier-card-topbar">
                      <div className="dossier-file-tag font-mono">
                        <span>DOSSIER // #{shortId}</span>
                      </div>
                      <div className="dossier-badges-wrap">
                        <span className={`dossier-status-pill status-${inc.status.toLowerCase()}`}>
                          {inc.status}
                        </span>
                        <span className={`dossier-tier-pill tier-${priorityLevel.toLowerCase()}`}>
                          P{priorityLevel === 'CRITICAL' ? '0' : priorityLevel === 'HIGH' ? '1' : priorityLevel === 'MEDIUM' ? '2' : '3'}
                        </span>
                      </div>
                    </div>

                    {/* Main Content */}
                    <div className="dossier-card-content">
                      <h2 className="dossier-incident-type font-headline">
                        {inc.incident_type ? inc.incident_type.replace(/_/g, ' ') : 'EMERGENCY INCIDENT'}
                      </h2>

                      <div className="dossier-location-row font-mono">
                        <span className="dossier-loc-pin">📍</span>
                        <span className="dossier-loc-text">{inc.location?.text || 'Bhubaneswar Central Sector'}</span>
                      </div>

                      {/* Tactical Metrics Bar */}
                      <div className="dossier-metrics-strip font-mono">
                        <div className="dossier-metric-block">
                          <span className="metric-tag">PRIORITY</span>
                          <span className="metric-data text-dispatch-yellow">{priorityScore}/100</span>
                        </div>
                        <div className="dossier-metric-block">
                          <span className="metric-tag">DISPATCHES</span>
                          <span className="metric-data text-cyan">{reportsCount} REPORTS</span>
                        </div>
                        <div className="dossier-metric-block">
                          <span className="metric-tag">AT RISK</span>
                          <span className="metric-data">{inc.people_at_risk?.count != null ? inc.people_at_risk.count : '—'}</span>
                        </div>
                      </div>

                      {/* Progress Meter */}
                      <div className="dossier-progress-track">
                        <div 
                          className={`dossier-progress-bar bar-${priorityLevel.toLowerCase()}`}
                          style={{ width: `${Math.min(100, Math.max(5, priorityScore))}%` }}
                        />
                      </div>
                    </div>

                    {/* Card Footer Button */}
                    <div className="dossier-card-footer">
                      <button 
                        type="button" 
                        className="dossier-open-btn font-headline"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedIncidentId(inc.incident_id);
                          setActiveTab('overview');
                        }}
                      >
                        INSPECT EVIDENCE DOSSIER →
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="dossier-empty-state">
              <ShieldAlert size={48} className="text-dispatch-yellow mb-3" />
              <h2 className="dossier-empty-title font-headline">NO INCIDENT DOSSIERS FOUND</h2>
              <p className="dossier-empty-text font-body">
                {searchQuery 
                  ? `No emergency cases matched "${searchQuery}". Clear your search query or reset filters.` 
                  : 'All incident streams are currently synchronized. Awaiting new citizen radio calls or sensor signals.'}
              </p>
              {searchQuery && (
                <Button 
                  type="button" 
                  variant="secondary" 
                  size="sm" 
                  onClick={() => { setSearchQuery(''); setFilterSeverity('ALL'); }}
                >
                  RESET SEARCH FILTERS
                </Button>
              )}
            </div>
          )}
        </main>
      </div>
    );
  }

  const incident = data?.incident;
  const reports = data?.source_reports || [];
  const auditTrail = data?.audit_trail || [];

  return (
    <div className="investigation-view" role="region" aria-label={`Investigation for ${selectedIncidentId}`}>
      {/* Backend Disconnected Warning Banner */}
      {isOnline === false && (
        <aside className="inv-offline-banner" role="alert" aria-live="assertive">
          <WifiOff size={16} className="inv-offline-icon" />
          <span className="font-mono inv-offline-msg">
            BACKEND SERVICE DISCONNECTED — REAL-TIME TELEMETRY UNREACHABLE
          </span>
          <button
            type="button"
            className="inv-offline-reconnect-btn font-headline"
            onClick={() => { checkHealth(); refetch(); }}
          >
            Reconnect
          </button>
        </aside>
      )}

      {/* Investigation Header */}
      <InvestigationHeader
        incident={incident || null}
        selectedIncidentId={selectedIncidentId}
        onBackToDeck={handleBackToDeck}
        onRefetch={refetch}
        onTakeAction={() => setActiveTab('action')}
        isLoading={isLoading}
      />

      {/* Sub Navigation Bar / Tabs */}
      {incident && (
        <nav className="inv-subnav-bar" aria-label="Investigation Sections">
          <div className="inv-subnav-inner">
            <button
              type="button"
              className={`inv-tab-btn font-headline ${activeTab === 'overview' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              <LayoutDashboard size={14} />
              <span>EVIDENCE DOSSIER</span>
            </button>

            <button
              type="button"
              className={`inv-tab-btn font-headline ${activeTab === 'reports' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('reports')}
            >
              <FileText size={14} />
              <span>CITIZEN DISPATCHES</span>
              <span className="inv-tab-count font-mono">{reports.length}</span>
            </button>

            <button
              type="button"
              className={`inv-tab-btn font-headline ${activeTab === 'timeline' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('timeline')}
            >
              <History size={14} />
              <span>TIMELINE ENGINE</span>
            </button>

            <button
              type="button"
              className={`inv-tab-btn font-headline ${activeTab === 'action' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('action')}
            >
              <ShieldCheck size={14} />
              <span>COMMAND PROTOCOLS</span>
            </button>

            <button
              type="button"
              className={`inv-tab-btn font-headline ${activeTab === 'audit' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('audit')}
            >
              <CheckCircle2 size={14} />
              <span>IMMUTABLE AUDIT LOG</span>
              {auditTrail.length > 0 && (
                <span className="inv-tab-count font-mono">{auditTrail.length}</span>
              )}
            </button>
          </div>
        </nav>
      )}

      {/* STATE 2: Loading State */}
      {isLoading && !data && (
        <main className="investigation-empty-container">
          <Radio size={36} className="text-cyan spinning" />
          <p className="font-mono text-sm mt-3 text-secondary">
            Fetching incident evidence and telemetry...
          </p>
        </main>
      )}

      {/* STATE 3: API Error State */}
      {!isLoading && error && !data && (
        <main className="investigation-empty-container">
          <div className="investigation-empty-card card-error">
            <AlertTriangle size={36} className="text-crimson" />
            <h2 className="investigation-empty-title text-crimson mt-2">
              Unable to Load Incident Data
            </h2>
            <p className="investigation-empty-text font-mono">
              {error}
            </p>
            <div className="flex gap-2">
              <Button type="button" variant="primary" size="md" onClick={() => refetch()}>
                <RotateCcw size={14} style={{ marginRight: 6 }} />
                Retry
              </Button>
              <Button type="button" variant="secondary" size="md" onClick={handleBackToDeck}>
                Back to Command Deck
              </Button>
            </div>
          </div>
        </main>
      )}

      {/* STATE 4: Tab Content Workspace */}
      {incident && (
        <main className="investigation-workspace-body">
          {activeTab === 'overview' && (
            <div className="tab-pane-fade">
              <IncidentFactPanel incident={incident} />

              {/* Bottom Tactical Shortcuts */}
              <div className="overview-shortcuts-grid">
                <div className="shortcut-card">
                  <div className="shortcut-header">
                    <FileText size={16} className="text-cyan" />
                    <h4 className="font-headline">PINNED CITIZEN EVIDENCE ({reports.length})</h4>
                  </div>
                  <p>
                    {reports.length > 0 
                      ? `${reports.length} citizen dispatch transcript(s) correlated with this incident.`
                      : 'No raw source transcripts recorded yet.'}
                  </p>
                  <button 
                    type="button" 
                    className="shortcut-link-btn font-headline"
                    onClick={() => setActiveTab('reports')}
                  >
                    INSPECT DISPATCH EVIDENCE ({reports.length}) →
                  </button>
                </div>

                <div className="shortcut-card">
                  <div className="shortcut-header">
                    <ShieldCheck size={16} className="text-dispatch-yellow" />
                    <h4 className="font-headline">SOVEREIGN COMMAND ACTION</h4>
                  </div>
                  <p>
                    Current Status: <strong>{incident.status}</strong> · Urgency: <strong>{incident.urgency}</strong>. Escalate units, adjust severity, or execute operator field overrides.
                  </p>
                  <button 
                    type="button" 
                    className="shortcut-link-btn text-dispatch-yellow font-headline"
                    onClick={() => setActiveTab('action')}
                  >
                    LAUNCH ACTION WIZARD →
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'reports' && (
            <div className="tab-pane-fade">
              <EvidenceReportList reports={reports} />
            </div>
          )}

          {activeTab === 'timeline' && (
            <div className="tab-pane-fade">
              <IncidentTimeline incidentId={selectedIncidentId} />
            </div>
          )}

          {activeTab === 'action' && (
            <div className="tab-pane-fade">
              <InvestigationActionWizard
                incident={incident}
                onActionSuccess={handleMutationSuccess}
                isOnline={isOnline}
              />
            </div>
          )}

          {activeTab === 'audit' && (
            <div className="tab-pane-fade">
              <AuditTracePanel
                auditTrail={auditTrail}
                humanOverride={incident.human_override}
              />
            </div>
          )}
        </main>
      )}
    </div>
  );
};

export default InvestigationView;
