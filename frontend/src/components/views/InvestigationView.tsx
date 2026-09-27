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

  const handleBackToDeck = useCallback(() => {
    setActiveView('command-deck');
  }, [setActiveView]);

  const handleMutationSuccess = useCallback(async () => {
    // Re-fetch incident detail from backend to synchronize incident, full audit trail, and priority recalculations
    await refetch();
  }, [refetch]);

  // STATE 1: No Incident Selected
  if (!selectedIncidentId) {
    return (
      <div className="investigation-view" role="region" aria-label="Investigation Evidence Board">
        <header className="investigation-empty-header">
          <div className="investigation-empty-title-group">
            <Search size={18} className="text-cyan" />
            <h1 className="investigation-empty-heading">Incident Investigation</h1>
          </div>
          <Button 
            type="button"
            variant="secondary" 
            size="sm" 
            onClick={handleBackToDeck}
            aria-label="Return to Command Deck"
          >
            <ArrowLeft size={14} style={{ marginRight: 6 }} />
            Back to Command Deck
          </Button>
        </header>

        <main className="investigation-empty-container">
          <div className="investigation-empty-card">
            <div className="investigation-empty-icon">
              <ShieldAlert size={42} color="var(--color-hazard-orange)" />
            </div>
            <h2 className="investigation-empty-title">Select an Incident to Investigate</h2>
            <p className="investigation-empty-text">
              Choose an active incident from the triage queue or map to inspect verified reports, priority factor contributions, timeline events, and operator review actions.
            </p>
            <Button 
              type="button"
              variant="primary" 
              size="md" 
              onClick={handleBackToDeck}
              aria-label="Open Command Deck Queue"
            >
              Open Command Deck Queue
            </Button>

            {availableIncidents.length > 0 && (
              <div className="investigation-quick-select">
                <span className="quick-select-label">Or Inspect Active Incident:</span>
                <div className="quick-select-list">
                  {availableIncidents.map((inc) => (
                    <button
                      key={inc.incident_id}
                      type="button"
                      className="quick-select-item"
                      onClick={() => {
                        setSelectedIncidentId(inc.incident_id);
                        setActiveTab('overview');
                      }}
                    >
                      <span className="quick-id" title={inc.incident_id}>
                        {inc.incident_id.length > 14
                          ? `#${inc.incident_id.replace(/^inc-/, '').substring(0, 8)}`
                          : inc.incident_id}
                      </span>
                      <span className="quick-type">
                        {inc.incident_type ? inc.incident_type.replace(/_/g, ' ') : 'Unclassified'}
                      </span>
                      <span className="quick-loc">{inc.location?.text || 'Bhubaneswar'}</span>
                      <span className="quick-action">Inspect →</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
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
              className={`inv-tab-btn ${activeTab === 'overview' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              <LayoutDashboard size={14} />
              <span>Overview</span>
            </button>

            <button
              type="button"
              className={`inv-tab-btn ${activeTab === 'reports' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('reports')}
            >
              <FileText size={14} />
              <span>Reports & Evidence</span>
              <span className="inv-tab-count">{reports.length}</span>
            </button>

            <button
              type="button"
              className={`inv-tab-btn ${activeTab === 'timeline' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('timeline')}
            >
              <History size={14} />
              <span>Timeline</span>
            </button>

            <button
              type="button"
              className={`inv-tab-btn ${activeTab === 'action' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('action')}
            >
              <ShieldCheck size={14} />
              <span>Take Action</span>
            </button>

            <button
              type="button"
              className={`inv-tab-btn ${activeTab === 'audit' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('audit')}
            >
              <CheckCircle2 size={14} />
              <span>Audit History</span>
              {auditTrail.length > 0 && (
                <span className="inv-tab-count">{auditTrail.length}</span>
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

              {/* Bottom Quick-Action Shortcuts */}
              <div className="overview-shortcuts-grid">
                <div className="shortcut-card">
                  <div className="shortcut-header">
                    <FileText size={16} className="text-cyan" />
                    <h4>Incoming Evidence</h4>
                  </div>
                  <p>
                    {reports.length > 0 
                      ? `${reports.length} citizen dispatch report(s) correlated with this incident.`
                      : 'No source reports recorded yet.'}
                  </p>
                  <button 
                    type="button" 
                    className="shortcut-link-btn"
                    onClick={() => setActiveTab('reports')}
                  >
                    View All Reports ({reports.length}) →
                  </button>
                </div>

                <div className="shortcut-card">
                  <div className="shortcut-header">
                    <ShieldCheck size={16} className="text-dispatch-yellow" />
                    <h4>Operator Verification</h4>
                  </div>
                  <p>
                    Current status: <strong>{incident.status}</strong>. Verify details, escalate urgency, or override parameters.
                  </p>
                  <button 
                    type="button" 
                    className="shortcut-link-btn text-dispatch-yellow"
                    onClick={() => setActiveTab('action')}
                  >
                    Open Action Wizard →
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
