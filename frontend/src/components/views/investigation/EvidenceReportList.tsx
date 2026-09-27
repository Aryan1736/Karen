import React, { useState, useMemo } from 'react';
import { 
  Search, 
  MapPin, 
  Clock, 
  Info,
  Filter,
  Tag
} from 'lucide-react';
import { RawReport } from '../../../types/incident';
import './EvidenceReportList.css';

export interface EvidenceReportListProps {
  reports: RawReport[];
}

export const EvidenceReportList: React.FC<EvidenceReportListProps> = ({ reports }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sourceFilter, setSourceFilter] = useState<string>('ALL');

  const availableSources = useMemo(() => {
    const s = new Set<string>();
    reports.forEach((r) => {
      if (r.source) s.add(r.source);
    });
    return Array.from(s);
  }, [reports]);

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
    <div className="evidence-container">
      {/* Evidence Controls */}
      <div className="evidence-controls-bar">
        <div className="evidence-search-box">
          <Search size={14} className="search-icon" />
          <input
            type="text"
            className="search-input font-body"
            placeholder="Search reports or locations..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            aria-label="Filter evidence reports"
          />
        </div>

        {availableSources.length > 1 && (
          <div className="evidence-filter-box">
            <Filter size={13} className="filter-icon" />
            <select
              className="filter-select font-mono"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              aria-label="Filter by source"
            >
              <option value="ALL">All Sources</option>
              {availableSources.map((src) => (
                <option key={src} value={src}>
                  {src.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Reports List */}
      {reports.length === 0 ? (
        <div className="evidence-empty-card">
          <Info size={28} className="text-muted" />
          <h4>No Linked Source Reports</h4>
          <p>No raw citizen or sensory dispatches are correlated with this incident record.</p>
        </div>
      ) : filteredReports.length === 0 ? (
        <div className="evidence-empty-card">
          <Search size={28} className="text-muted" />
          <h4>No Matching Reports</h4>
          <p>No reports match your current filter query "{searchTerm}".</p>
          <button 
            type="button" 
            className="reset-filter-btn"
            onClick={() => { setSearchTerm(''); setSourceFilter('ALL'); }}
          >
            Clear Filters
          </button>
        </div>
      ) : (
        <div className="evidence-list">
          {filteredReports.map((report) => {
            const reportedAt = report.reported_at
              ? new Date(report.reported_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
              : '--';

            const hasLocationHint = report.location_hint && (
              report.location_hint.raw_text ||
              (report.location_hint.latitude != null && report.location_hint.longitude != null)
            );

            const metadataEntries = report.metadata
              ? Object.entries(report.metadata)
              : [];

            const shortReportId = report.report_id.length > 14
              ? `#${report.report_id.replace(/^rep-/, '').substring(0, 8)}`
              : report.report_id;

            return (
              <article key={report.report_id} className="evidence-card">
                {/* Card Top Metadata */}
                <div className="evidence-card-top">
                  <div className="evidence-source-group">
                    <span className="report-id-pill font-mono">{shortReportId}</span>
                    <span className={`source-pill ${report.is_synthetic ? 'source-synthetic' : 'source-field'}`}>
                      {report.is_synthetic ? 'Simulation Pulse' : report.source?.toUpperCase() || 'Field Report'}
                    </span>
                  </div>

                  <div className="evidence-timestamp font-mono">
                    <Clock size={12} className="text-muted" />
                    <span>{reportedAt}</span>
                  </div>
                </div>

                {/* Verbatim Content */}
                <blockquote className="evidence-quote font-body">
                  "{report.text}"
                </blockquote>

                {/* Location Hint if available */}
                {hasLocationHint && (
                  <div className="evidence-loc-row">
                    <MapPin size={12} className="text-cyan" />
                    <span className="evidence-loc-label font-mono">Location Reference:</span>
                    <span className="evidence-loc-text">
                      {report.location_hint?.raw_text || ''}
                      {report.location_hint?.latitude != null && report.location_hint?.longitude != null && (
                        <span className="coords-text font-mono">
                          {' '}({report.location_hint.latitude.toFixed(4)}, {report.location_hint.longitude.toFixed(4)})
                        </span>
                      )}
                    </span>
                  </div>
                )}

                {/* Metadata Tags */}
                {metadataEntries.length > 0 && (
                  <div className="evidence-meta-row">
                    <Tag size={11} className="text-muted" />
                    <div className="meta-tags-list">
                      {metadataEntries.map(([k, v]) => (
                        <span key={k} className="meta-tag font-mono">
                          {k}: <strong>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</strong>
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
    </div>
  );
};

export default EvidenceReportList;
