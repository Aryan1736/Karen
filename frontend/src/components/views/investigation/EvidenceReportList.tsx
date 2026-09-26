import React, { useState, useMemo } from 'react';
import { 
  FileText, 
  Search, 
  MapPin, 
  Clock, 
  Info,
  Filter
} from 'lucide-react';
import { RawReport } from '../../../types/incident';
import './EvidenceReportList.css';

export interface EvidenceReportListProps {
  reports: RawReport[];
}

export const EvidenceReportList: React.FC<EvidenceReportListProps> = ({ reports }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sourceFilter, setSourceFilter] = useState<string>('ALL');

  // Discover all unique sources from actual report data
  const availableSources = useMemo(() => {
    const s = new Set<string>();
    reports.forEach((r) => {
      if (r.source) s.add(r.source);
    });
    return Array.from(s);
  }, [reports]);

  // Filter reports truthfully by user input
  const filteredReports = useMemo(() => {
    return reports.filter((r) => {
      if (sourceFilter !== 'ALL' && r.source !== sourceFilter) return false;
      if (!searchTerm) return true;
      const lower = searchTerm.toLowerCase();
      return (
        r.report_id.toLowerCase().includes(lower) ||
        r.text.toLowerCase().includes(lower) ||
        (r.location_hint?.raw_text && r.location_hint.raw_text.toLowerCase().includes(lower))
      );
    });
  }, [reports, searchTerm, sourceFilter]);

  return (
    <section className="inv-evidence-section" aria-label="Incident Source Evidence Feed">
      {/* Evidence Section Header */}
      <div className="evidence-header">
        <div className="evidence-title-group">
          <FileText size={16} className="evidence-title-icon" />
          <h2 className="evidence-title">EVIDENCE / SOURCE REPORTS</h2>
          <span className="evidence-count-badge font-mono">
            {filteredReports.length} {filteredReports.length === 1 ? 'RECORD' : 'RECORDS'}
          </span>
        </div>

        {/* Search & Filter Controls */}
        <div className="evidence-controls">
          <div className="evidence-search-wrap">
            <Search size={14} className="evidence-search-icon" />
            <input
              type="text"
              className="evidence-search-input font-mono"
              placeholder="Filter reports by keyword or ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              aria-label="Filter evidence reports"
            />
          </div>

          {availableSources.length > 1 && (
            <div className="evidence-filter-wrap">
              <Filter size={12} className="evidence-filter-icon" />
              <select
                className="evidence-filter-select font-mono"
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                aria-label="Filter by source type"
              >
                <option value="ALL">ALL SOURCES</option>
                {availableSources.map((src) => (
                  <option key={src} value={src}>
                    {src.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Reports List */}
      {reports.length === 0 ? (
        <div className="evidence-empty-card">
          <Info size={32} className="evidence-empty-icon" />
          <h3 className="evidence-empty-heading">NO SOURCE REPORTS LINKED</h3>
          <p className="evidence-empty-text">
            No raw citizen or sensory dispatches are correlated with this incident record in the database.
          </p>
        </div>
      ) : filteredReports.length === 0 ? (
        <div className="evidence-empty-card">
          <Search size={32} className="evidence-empty-icon" />
          <h3 className="evidence-empty-heading">NO MATCHING EVIDENCE</h3>
          <p className="evidence-empty-text">
            No source reports match the search filter "{searchTerm}".
          </p>
          <button 
            type="button" 
            className="evidence-reset-btn"
            onClick={() => { setSearchTerm(''); setSourceFilter('ALL'); }}
          >
            RESET FILTERS
          </button>
        </div>
      ) : (
        <div className="evidence-grid">
          {filteredReports.map((report) => {
            const reportedAt = report.reported_at
              ? new Date(report.reported_at).toUTCString().replace('GMT', 'UTC')
              : '--';

            const hasLocationHint = report.location_hint && (
              report.location_hint.raw_text ||
              (report.location_hint.latitude != null && report.location_hint.longitude != null)
            );

            const metadataEntries = report.metadata
              ? Object.entries(report.metadata)
              : [];

            return (
              <article key={report.report_id} className="evidence-card" aria-label={`Report ${report.report_id}`}>
                {/* Top Card Tape */}
                <div className="evidence-card-tape">
                  <div className="evidence-tape-left">
                    <span className="evidence-report-id font-mono">
                      {report.report_id}
                    </span>
                    <span className="evidence-source-tag font-mono">
                      SOURCE: {report.source ? report.source.toUpperCase() : 'UNKNOWN'}
                    </span>
                    <span className={`evidence-provenance-tag font-mono ${report.is_synthetic ? 'provenance-synthetic' : 'provenance-field'}`}>
                      {report.is_synthetic ? 'SYNTHETIC' : 'MANUAL / FIELD'}
                    </span>
                  </div>

                  <div className="evidence-tape-right font-mono">
                    <Clock size={12} className="evidence-clock-icon" />
                    <span>{reportedAt}</span>
                  </div>
                </div>

                {/* Verbatim Content Body */}
                <div className="evidence-body">
                  <div className="evidence-body-label font-mono">
                    [ RAW INCOMING DISPATCH TEXT // VERBATIM ]
                  </div>
                  <blockquote className="evidence-verbatim-text">
                    "{report.text}"
                  </blockquote>
                </div>

                {/* Optional Location Hint (only if genuine) */}
                {hasLocationHint && (
                  <div className="evidence-location-hint">
                    <MapPin size={13} className="evidence-loc-icon" />
                    <span className="evidence-loc-label font-mono">LOCATION HINT:</span>
                    <span className="evidence-loc-val">
                      {report.location_hint?.raw_text || ''}
                      {report.location_hint?.latitude != null && report.location_hint?.longitude != null && (
                        <span className="evidence-loc-coords font-mono">
                          {' '}[{report.location_hint.latitude.toFixed(4)}° N, {report.location_hint.longitude.toFixed(4)}° W]
                        </span>
                      )}
                      {report.location_hint?.precision && (
                        <span className="evidence-loc-precision font-mono">
                          {' '}({report.location_hint.precision})
                        </span>
                      )}
                    </span>
                  </div>
                )}

                {/* Optional Metadata (only if genuine) */}
                {metadataEntries.length > 0 && (
                  <div className="evidence-metadata-row">
                    <span className="evidence-meta-title font-mono">METADATA:</span>
                    <div className="evidence-meta-chips">
                      {metadataEntries.map(([k, v]) => (
                        <span key={k} className="evidence-meta-chip font-mono">
                          <strong>{k}:</strong> {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
};
