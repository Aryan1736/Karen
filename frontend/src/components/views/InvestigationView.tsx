import React, { useCallback } from 'react';
import { 
  Search, 
  ArrowLeft, 
  ShieldAlert, 
  AlertTriangle, 
  Radio, 
  WifiOff,
  RotateCcw
} from 'lucide-react';
import { Button } from '../ui';
import { useNavigation } from '../../context/NavigationContext';
import { useIncidentDetail } from '../../hooks/useIncidentDetail';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import {
  InvestigationHeader,
  IncidentFactPanel,
  EvidenceReportList,
  IncidentTimeline,
  AuditTracePanel
} from './investigation';
import './InvestigationView.css';

export const InvestigationView: React.FC = () => {
  const { 
    selectedIncidentId, 
    setSelectedIncidentId, 
    setActiveView 
  } = useNavigation();

  const { isOnline, checkHealth } = useBackendHealth();
  const { data, isLoading, error, refetch } = useIncidentDetail(selectedIncidentId);

  const handleBackToDeck = useCallback(() => {
    setActiveView('command-deck');
  }, [setActiveView]);

  const handleNavigateToStreams = useCallback(() => {
    setActiveView('incident-streams');
  }, [setActiveView]);

  const handleNavigateToAudit = useCallback(() => {
    setActiveView('audit-trail');
  }, [setActiveView]);

  const handleClearSelection = useCallback(() => {
    setSelectedIncidentId(null);
  }, [setSelectedIncidentId]);

  // STATE 1: No Incident Selected
  if (!selectedIncidentId) {
    return (
      <div className="investigation-view" role="region" aria-label="Investigation Evidence Board">
        <header className="investigation-empty-header">
          <div className="investigation-empty-title-group">
            <Search size={18} className="text-cyan" />
            <h1 className="investigation-empty-heading">INCIDENT INVESTIGATION & EVIDENCE BOARD</h1>
          </div>
          <Button 
            type="button"
            variant="secondary" 
            size="sm" 
            onClick={handleBackToDeck}
            aria-label="Return to Command Deck"
          >
            <ArrowLeft size={14} style={{ marginRight: 6 }} />
            BACK TO COMMAND DECK
          </Button>
        </header>

        <main className="investigation-empty-container">
          <div className="investigation-empty-card">
            <div className="investigation-empty-icon">
              <ShieldAlert size={48} color="var(--color-hazard-orange)" />
            </div>
            <h2 className="investigation-empty-title">NO INCIDENT SELECTED</h2>
            <p className="investigation-empty-text">
              Select an active incident from the Command Deck triage queue or tactical map to examine multi-source signal triangulation, explainable priority factors, fused raw dispatches, and chronological incident timelines.
            </p>
            <Button 
              type="button"
              variant="primary" 
              size="md" 
              onClick={handleBackToDeck}
              aria-label="Open Command Deck Queue"
            >
              OPEN COMMAND DECK QUEUE
            </Button>
          </div>
        </main>
      </div>
    );
  }

  const incident = data?.incident;
  const reports = data?.source_reports || [];
  const auditTrail = data?.audit_trail || [];

  return (
    <div className="investigation-view" role="region" aria-label={`Investigation Evidence Board for ${selectedIncidentId}`}>
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
            RECONNECT
          </button>
        </aside>
      )}

      {/* Investigation Header */}
      <InvestigationHeader
        incident={incident || null}
        selectedIncidentId={selectedIncidentId}
        onBackToDeck={handleBackToDeck}
        onNavigateToStreams={handleNavigateToStreams}
        onNavigateToAudit={handleNavigateToAudit}
        onRefetch={refetch}
        onClearSelection={handleClearSelection}
        isLoading={isLoading}
      />

      {/* STATE 2: Loading State */}
      {isLoading && !data && (
        <main className="investigation-empty-container">
          <Radio size={40} className="text-cyan spinning" />
          <p className="font-mono text-sm mt-3">
            FETCHING INCIDENT EVIDENCE [{selectedIncidentId}]...
          </p>
        </main>
      )}

      {/* STATE 3: API Error State */}
      {!isLoading && error && !data && (
        <main className="investigation-empty-container">
          <div className="investigation-empty-card card-error">
            <AlertTriangle size={42} className="text-crimson" />
            <h2 className="investigation-empty-title text-crimson mt-2">
              EVIDENCE FETCH FAILURE
            </h2>
            <p className="investigation-empty-text font-mono">
              {error}
            </p>
            <div className="flex gap-2">
              <Button type="button" variant="primary" size="md" onClick={() => refetch()}>
                <RotateCcw size={14} style={{ marginRight: 6 }} />
                RETRY FETCH
              </Button>
              <Button type="button" variant="secondary" size="md" onClick={handleBackToDeck}>
                RETURN TO DECK
              </Button>
            </div>
          </div>
        </main>
      )}

      {/* STATE 4: Populated Evidence Workspace */}
      {incident && (
        <main className="investigation-workspace-body">
          {/* Fact Panel & Priority Dossier */}
          <IncidentFactPanel incident={incident} />

          {/* Dual Evidence & Chronological Timeline Matrix */}
          <div className="investigation-dual-matrix">
            <div className="matrix-col">
              <EvidenceReportList reports={reports} />
            </div>
            <div className="matrix-col">
              <IncidentTimeline incidentId={selectedIncidentId} />
            </div>
          </div>

          {/* Traceability & Immutable Audit Trail */}
          <AuditTracePanel
            auditTrail={auditTrail}
            humanOverride={incident.human_override}
          />
        </main>
      )}
    </div>
  );
};

export default InvestigationView;
