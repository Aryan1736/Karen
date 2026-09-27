import React, { useState, useMemo, useCallback } from 'react';
import { 
  ShieldCheck, 
  ShieldAlert, 
  ArrowRight, 
  RotateCcw, 
  Clock, 
  User, 
  Radio, 
  AlertTriangle,
  Search,
  ChevronDown,
  ChevronUp,
  FileText,
  Lock,
  Database,
  History,
  CheckCircle2
} from 'lucide-react';
import { Badge, Button } from '../ui';
import { useIncidents } from '../../hooks/useIncidents';
import { useNavigation } from '../../context/NavigationContext';
import { getIncidentDetail } from '../../api/incidents';
import { AuditLog } from '../../types/incident';
import './AuditTrailView.css';

type AuditViewTab = 'all' | 'overrides' | 'protocols';

export const AuditTrailView: React.FC = () => {
  const { incidents, isLoading, error, refetch } = useIncidents('ALL');
  const { navigateToIncident } = useNavigation();

  const [activeTab, setActiveTab] = useState<AuditViewTab>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // Expanded incident details map for inline audit logs
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedAuditTrail, setExpandedAuditTrail] = useState<AuditLog[] | null>(null);
  const [loadingAuditId, setLoadingAuditId] = useState<string | null>(null);

  // Active human sovereign overrides
  const overriddenIncidents = useMemo(() => {
    return incidents.filter((inc) => inc.human_override?.active);
  }, [incidents]);

  // Filtered incidents based on tab, search, and status
  const displayedIncidents = useMemo(() => {
    let list = incidents;

    if (activeTab === 'overrides') {
      list = overriddenIncidents;
    }

    if (statusFilter !== 'ALL') {
      list = list.filter((inc) => inc.status === statusFilter);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter((inc) => {
        return (
          inc.incident_id.toLowerCase().includes(q) ||
          (inc.location?.text && inc.location.text.toLowerCase().includes(q)) ||
          (inc.human_override?.updated_by && inc.human_override.updated_by.toLowerCase().includes(q)) ||
          (inc.human_override?.reason && inc.human_override.reason.toLowerCase().includes(q)) ||
          (inc.incident_type && inc.incident_type.toLowerCase().includes(q))
        );
      });
    }

    return list;
  }, [incidents, overriddenIncidents, activeTab, statusFilter, searchQuery]);

  const toggleExpandAudit = useCallback(async (incidentId: string) => {
    if (expandedId === incidentId) {
      setExpandedId(null);
      setExpandedAuditTrail(null);
      return;
    }

    setExpandedId(incidentId);
    setLoadingAuditId(incidentId);
    try {
      const res = await getIncidentDetail(incidentId);
      setExpandedAuditTrail(res.audit_trail || []);
    } catch {
      setExpandedAuditTrail([]);
    } finally {
      setLoadingAuditId(null);
    }
  }, [expandedId]);

  return (
    <div className="audit-trail-view pattern-halftone" role="region" aria-label="Human Sovereign Review and Audit Ledger">
      {/* Header Bar */}
      <header className="audit-header">
        <div className="audit-title-group">
          <div className="audit-badge-tape">AUDIT TRAIL</div>
          <div className="audit-title-combo">
            <ShieldCheck size={20} color="var(--color-system-green)" />
            <h1 className="audit-title font-headline">OPERATOR OVERRIDE & AUDIT LEDGER</h1>
          </div>
          <div className="audit-header-badges">
            <Badge variant={overriddenIncidents.length > 0 ? 'p0-critical' : 'p2-medium'} size="sm">
              {overriddenIncidents.length} SOVEREIGN {overriddenIncidents.length === 1 ? 'OVERRIDE' : 'OVERRIDES'}
            </Badge>
            <span className="audit-total-pill font-mono">{incidents.length} CASES LOGGED</span>
          </div>
        </div>

        <div className="audit-header-actions">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
            title="Refresh incident audit ledger"
            aria-label="Refresh audit ledger"
          >
            <RotateCcw size={13} className={isLoading ? 'spinning' : ''} style={{ marginRight: 6 }} />
            REFRESH LEDGER
          </Button>
        </div>
      </header>

      {/* Tabs & Controls Bar */}
      <div className="audit-controls-bar">
        <div className="audit-tabs">
          <button
            type="button"
            className={`audit-tab-btn font-headline ${activeTab === 'all' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('all')}
          >
            <Database size={13} />
            <span>ALL CATALOGED INCIDENTS</span>
            <span className="audit-tab-count font-mono">{incidents.length}</span>
          </button>

          <button
            type="button"
            className={`audit-tab-btn font-headline ${activeTab === 'overrides' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('overrides')}
          >
            <ShieldAlert size={13} />
            <span>SOVEREIGN OVERRIDES ONLY</span>
            <span className="audit-tab-count font-mono">{overriddenIncidents.length}</span>
          </button>

          <button
            type="button"
            className={`audit-tab-btn font-headline ${activeTab === 'protocols' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('protocols')}
          >
            <Lock size={13} />
            <span>AUDIT INTEGRITY PROTOCOLS</span>
          </button>
        </div>

        {activeTab !== 'protocols' && (
          <div className="audit-filter-row">
            {/* Search Input */}
            <div className="audit-search-box">
              <Search size={14} className="audit-search-icon" />
              <input
                type="text"
                className="audit-search-input font-mono"
                placeholder="SEARCH BY ID, OPERATOR, OR REASON..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search audit records"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="audit-search-clear"
                  onClick={() => setSearchQuery('')}
                  title="Clear search"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Status Pills */}
            <div className="audit-status-filters">
              {['ALL', 'ACTIVE', 'NEEDS_REVIEW', 'VERIFIED', 'RESOLVED'].map((st) => (
                <button
                  key={st}
                  type="button"
                  className={`audit-filter-pill font-headline ${statusFilter === st ? 'is-active' : ''}`}
                  onClick={() => setStatusFilter(st)}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Main Body */}
      <div className="audit-body">
        {/* Loading State */}
        {isLoading && incidents.length === 0 && (
          <div className="audit-loading-container">
            <Radio size={36} color="var(--color-multiverse-cyan)" className="rotating" />
            <span className="audit-loading-text font-mono">
              SYNCHRONIZING CANONICAL AUDIT LEDGER...
            </span>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="audit-error-card" role="alert">
            <AlertTriangle size={36} color="var(--color-p0-critical)" />
            <h2 className="audit-error-title font-headline">AUDIT QUERY ERROR</h2>
            <p className="audit-error-desc font-mono">{error}</p>
            <Button variant="primary" size="sm" onClick={() => refetch()}>
              <RotateCcw size={13} style={{ marginRight: 4 }} />
              RETRY QUERY
            </Button>
          </div>
        )}

        {/* PROTOCOLS TAB */}
        {activeTab === 'protocols' && (
          <div className="audit-protocols-grid">
            <div className="protocol-card">
              <div className="protocol-card-header">
                <Lock size={16} className="text-cyan" />
                <h3 className="font-headline">1. ATOMIC ROW-LEVEL CONCURRENCY</h3>
              </div>
              <p className="font-body">
                Every operator status transition and parameter override executes inside an atomic database transaction with strict row locking (<code>FOR UPDATE</code>). This guarantees zero race conditions or phantom updates between competing dispatchers.
              </p>
              <div className="protocol-stamp font-mono">[TRANSACTION ISOLATION: GUARANTEED]</div>
            </div>

            <div className="protocol-card">
              <div className="protocol-card-header">
                <FileText size={16} className="text-dispatch-yellow" />
                <h3 className="font-headline">2. MANDATORY OPERATOR JUSTIFICATION</h3>
              </div>
              <p className="font-body">
                Anonymous state mutations are strictly rejected by the backend validation firewall. Every sovereign override requires an authenticated Operator ID and recorded rationale stored permanently in the immutable audit log table.
              </p>
              <div className="protocol-stamp font-mono">[NON-REPUDIATION: ENFORCED]</div>
            </div>

            <div className="protocol-card">
              <div className="protocol-card-header">
                <History size={16} className="text-green" />
                <h3 className="font-headline">3. IMMUTABLE CHRONOLOGICAL AUDIT</h3>
              </div>
              <p className="font-body">
                Historical records are never overwritten or deleted. Previous values and subsequent values are preserved side-by-side with millisecond UTC timestamps for full retrospective incident analysis and legal compliance.
              </p>
              <div className="protocol-stamp font-mono">[APPEND-ONLY LOG: SHA-256 SAFE]</div>
            </div>

            <div className="protocol-card">
              <div className="protocol-card-header">
                <CheckCircle2 size={16} className="text-hazard" />
                <h3 className="font-headline">4. SOVEREIGN HUMAN AUTHORITY</h3>
              </div>
              <p className="font-body">
                Algorithmic consensus serves exclusively as situational decision support. The human dispatcher holds supreme operational authority to adjust triage urgency, classification, or required response units at any stage.
              </p>
              <div className="protocol-stamp font-mono">[OPERATOR SUPREMACY: ACTIVE]</div>
            </div>
          </div>
        )}

        {/* INCIDENTS LEDGER TAB */}
        {activeTab !== 'protocols' && !isLoading && !error && displayedIncidents.length > 0 && (
          <div className="audit-ledger-container">
            {/* Banner */}
            <div className="audit-ledger-banner">
              <ShieldCheck size={16} className="text-cyan" />
              <span className="font-mono text-xs">
                DISPLAYING {displayedIncidents.length} OF {incidents.length} AUDIT RECORDS · IMMUTABLE RELATIONAL LEDGER
              </span>
            </div>

            {/* List of Cards */}
            <div className="audit-ledger-cards">
              {displayedIncidents.map((incident) => {
                const override = incident.human_override;
                const isOverridden = override?.active === true;
                const isExpanded = expandedId === incident.incident_id;
                const isLoadingAudit = loadingAuditId === incident.incident_id;

                const timeFormatted = override?.updated_at
                  ? new Date(override.updated_at).toUTCString().replace('GMT', 'UTC')
                  : incident.updated_at
                  ? new Date(incident.updated_at).toUTCString().replace('GMT', 'UTC')
                  : '--';

                const shortId = incident.incident_id.replace(/^inc-/, '').substring(0, 8).toUpperCase();

                return (
                  <article 
                    key={incident.incident_id} 
                    className={`audit-ledger-card ${isOverridden ? 'is-overridden' : ''}`}
                  >
                    {/* Top Identity Row */}
                    <div className="audit-card-top">
                      <div className="audit-card-identity">
                        <span className="audit-incident-id font-mono font-bold">
                          #{shortId}
                        </span>
                        
                        {isOverridden ? (
                          <Badge variant="p0-critical" size="sm">SOVEREIGN OVERRIDE ACTIVE</Badge>
                        ) : (
                          <span className="audit-autonomous-badge font-mono">AUTONOMOUS CONSENSUS</span>
                        )}

                        <Badge variant="neutral" size="sm">STATUS: {incident.status}</Badge>

                        {incident.priority?.level && (
                          <Badge 
                            variant={incident.priority.level === 'CRITICAL' ? 'p0-critical' : incident.priority.level === 'HIGH' ? 'p1-high' : 'p2-medium'} 
                            size="sm"
                          >
                            P{incident.priority.level === 'CRITICAL' ? '0' : incident.priority.level === 'HIGH' ? '1' : '2'} · {Math.round(incident.priority.score)} PTS
                          </Badge>
                        )}
                      </div>

                      <div className="audit-card-actions">
                        <button
                          type="button"
                          className="audit-inspect-toggle-btn font-headline"
                          onClick={() => toggleExpandAudit(incident.incident_id)}
                        >
                          <History size={13} />
                          <span>{isExpanded ? 'COLLAPSE AUDIT LOG' : 'VIEW AUDIT LOG'}</span>
                          {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                        </button>

                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => navigateToIncident(incident.incident_id)}
                          title={`Inspect full evidence and telemetry for ${incident.incident_id}`}
                          aria-label={`Inspect evidence and audit trail for incident ${incident.incident_id}`}
                        >
                          <span>INVESTIGATE</span>
                          <ArrowRight size={13} style={{ marginLeft: 4 }} />
                        </Button>
                      </div>
                    </div>

                    {/* Metadata Strip */}
                    <div className="audit-card-meta font-mono">
                      <div className="audit-meta-entry">
                        <User size={12} className="text-muted" />
                        <span className="text-muted">OPERATOR:</span>
                        <strong className={isOverridden ? 'text-cyan' : 'text-secondary'}>
                          {isOverridden ? (override?.updated_by || 'SYSTEM') : 'AUTONOMOUS TRIAGE'}
                        </strong>
                      </div>
                      <span className="meta-sep">|</span>
                      <div className="audit-meta-entry">
                        <Clock size={12} className="text-muted" />
                        <span className="text-muted">MUTATED AT:</span>
                        <span>{timeFormatted}</span>
                      </div>
                      <span className="meta-sep">|</span>
                      <div className="audit-meta-entry">
                        <span className="text-muted">LOCATION:</span>
                        <span className="text-dispatch-yellow">{incident.location?.text || 'Bhubaneswar Central Sector'}</span>
                      </div>
                    </div>

                    {/* Override Justification or Consensus Notice */}
                    {isOverridden ? (
                      <div className="audit-card-reason">
                        <span className="audit-reason-tag font-mono">OPERATOR JUSTIFICATION:</span>
                        <p className="audit-reason-text font-body">
                          "{override?.reason || 'No justification recorded'}"
                        </p>
                      </div>
                    ) : (
                      <div className="audit-card-consensus font-mono text-xs">
                        <span className="text-muted">GOVERNANCE MODE:</span> 
                        <span> Machine triage corroborated by {incident.corroboration?.report_count || 1} multi-source dispatch reports.</span>
                      </div>
                    )}

                    {/* Expanded Inline Audit Trail Log */}
                    {isExpanded && (
                      <div className="audit-expanded-drawer">
                        <div className="audit-drawer-header font-headline">
                          <History size={14} className="text-dispatch-yellow" />
                          <span>CHRONOLOGICAL AUDIT LOG ENTRIES FOR #{shortId}</span>
                        </div>

                        {isLoadingAudit ? (
                          <div className="audit-drawer-loading font-mono">
                            <Radio size={16} className="rotating text-cyan mr-2" />
                            Fetching immutable database audit records...
                          </div>
                        ) : expandedAuditTrail && expandedAuditTrail.length > 0 ? (
                          <div className="audit-drawer-table-wrap">
                            <table className="audit-drawer-table font-mono">
                              <thead>
                                <tr>
                                  <th>TIMESTAMP (UTC)</th>
                                  <th>OPERATOR</th>
                                  <th>FIELD MUTATED</th>
                                  <th>PREVIOUS VALUE</th>
                                  <th>NEW VALUE</th>
                                  <th>JUSTIFICATION</th>
                                </tr>
                              </thead>
                              <tbody>
                                {expandedAuditTrail.map((log) => {
                                  const logTime = log.created_at
                                    ? new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                                    : '--';

                                  return (
                                    <tr key={log.override_id}>
                                      <td className="text-muted">{logTime}</td>
                                      <td className="text-cyan font-bold">{log.operator_id}</td>
                                      <td>
                                        <span className="audit-field-badge">{log.field}</span>
                                      </td>
                                      <td className="text-muted">{String(log.previous_value ?? '—')}</td>
                                      <td className="text-dispatch-yellow font-bold">{String(log.new_value)}</td>
                                      <td className="audit-log-reason">"{log.reason}"</td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div className="audit-drawer-empty font-mono text-xs text-muted">
                            No discrete manual audit overrides recorded for this incident yet. All parameters reflect verified initial ingestion.
                          </div>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </div>
        )}

        {/* Empty Search/Filter State */}
        {activeTab !== 'protocols' && !isLoading && !error && displayedIncidents.length === 0 && (
          <div className="audit-empty-card">
            <div className="audit-empty-icon">
              <FileText size={48} color="var(--color-dispatch-yellow)" />
            </div>
            <h2 className="audit-empty-title font-headline">NO MATCHING AUDIT RECORDS</h2>
            <p className="audit-empty-desc font-body">
              {searchQuery || statusFilter !== 'ALL'
                ? `No records matched query "${searchQuery}" with status "${statusFilter}". Try resetting your search filters.`
                : 'No incidents are currently recorded in the active ledger. Awaiting incoming citizen radio streams.'}
            </p>
            <div className="audit-empty-actions">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => { setSearchQuery(''); setStatusFilter('ALL'); }}
              >
                RESET FILTERS
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuditTrailView;
