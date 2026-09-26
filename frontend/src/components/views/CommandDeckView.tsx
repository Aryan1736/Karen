import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Search, Globe } from 'lucide-react';
import { useNavigation, IncidentPriorityFilter } from '../../context/NavigationContext';
import { useIncidents } from '../../hooks/useIncidents';
import { TacticalInput } from '../ui';
import { 
  TacticalMap, 
  IncidentQueueRail, 
  TacticalCommandBar 
} from './command-deck';
import './CommandDeckView.css';

interface FilterOption {
  id: IncidentPriorityFilter;
  label: string;
}

const FILTER_OPTIONS: FilterOption[] = [
  { id: 'ALL', label: 'ALL' },
  { id: 'CRITICAL', label: 'P0 CRITICAL' },
  { id: 'HIGH', label: 'P1 HIGH' },
  { id: 'MEDIUM', label: 'P2 MED' },
  { id: 'NEEDS_REVIEW', label: 'NEEDS REVIEW' },
];

export const CommandDeckView: React.FC = () => {
  const { 
    activeFilter, 
    setActiveFilter, 
    selectedIncidentId, 
    setSelectedIncidentId, 
    navigateToIncident 
  } = useNavigation();

  const { incidents, totalCount, criticalCount, isLoading, error, refetch } = useIncidents(activeFilter);
  const [searchQuery, setSearchQuery] = useState('');
  const [isWebVectorsActive, setIsWebVectorsActive] = useState(true);

  // Compute counts for filter chips
  const counts = useMemo(() => {
    let p0 = 0;
    let p1 = 0;
    let p2 = 0;
    let review = 0;

    incidents.forEach((inc) => {
      if (inc.status === 'NEEDS_REVIEW') {
        review++;
      } else if (inc.priority?.level === 'CRITICAL') {
        p0++;
      } else if (inc.priority?.level === 'HIGH') {
        p1++;
      } else if (inc.priority?.level === 'MEDIUM') {
        p2++;
      }
    });

    return {
      ALL: totalCount || incidents.length,
      CRITICAL: criticalCount || p0,
      HIGH: p1,
      MEDIUM: p2,
      NEEDS_REVIEW: review,
    };
  }, [incidents, totalCount, criticalCount]);

  // Derive highest-priority incident deterministically from the real incident list
  const highestPriorityIncident = useMemo(() => {
    if (incidents.length === 0) return null;
    const sorted = [...incidents].sort((a, b) => {
      const scoreA = a.priority?.score ?? 0;
      const scoreB = b.priority?.score ?? 0;
      if (scoreB !== scoreA) return scoreB - scoreA;
      // Secondary tie-break: latest updated_at
      const timeA = new Date(a.updated_at || a.created_at || 0).getTime();
      const timeB = new Date(b.updated_at || b.created_at || 0).getTime();
      return timeB - timeA;
    });
    return sorted[0];
  }, [incidents]);

  // Active selected incident: use selectedIncidentId if valid, else default to highestPriorityIncident
  const activeSelectedIncident = useMemo(() => {
    if (selectedIncidentId) {
      const found = incidents.find((i) => i.incident_id === selectedIncidentId);
      if (found) return found;
    }
    return highestPriorityIncident;
  }, [incidents, selectedIncidentId, highestPriorityIncident]);

  // Auto-focus highest-priority incident if no active selection exists
  useEffect(() => {
    if (!selectedIncidentId && highestPriorityIncident) {
      setSelectedIncidentId(highestPriorityIncident.incident_id);
    }
  }, [selectedIncidentId, highestPriorityIncident, setSelectedIncidentId]);

  const handleSelectIncident = useCallback((incidentId: string) => {
    setSelectedIncidentId(incidentId);
  }, [setSelectedIncidentId]);

  return (
    <div className="command-deck-view" role="region" aria-label="Tactical Command Center">
      {/* Operational Filter & Quick Search Bar */}
      <div className="triage-filter-bar">
        {/* Search Input */}
        <div className="filter-search-container">
          <TacticalInput
            leftIcon={<Search size={15} color="var(--color-text-muted)" />}
            placeholder="SEARCH INCIDENTS, LOCATIONS, TAC-CHANNELS..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="filter-search-input"
            aria-label="Search incidents and locations"
          />
        </div>

        {/* Triage Filter Chips */}
        <div className="filter-chip-group" role="group" aria-label="Priority filters">
          {FILTER_OPTIONS.map((filter) => {
            const isActive = activeFilter === filter.id;
            const count = counts[filter.id] ?? 0;
            const isCriticalFilter = filter.id === 'CRITICAL';
            const isReviewFilter = filter.id === 'NEEDS_REVIEW';

            return (
              <button
                key={filter.id}
                type="button"
                className={`filter-chip-btn ${isActive ? 'active' : ''} ${isCriticalFilter ? 'chip-critical' : ''} ${isReviewFilter ? 'chip-review' : ''}`}
                onClick={() => setActiveFilter(filter.id)}
                aria-pressed={isActive}
              >
                {isCriticalFilter && isActive && <span className="chip-beacon-dot"></span>}
                <span>{filter.label}</span>
                <span className="filter-chip-count">{count}</span>
              </button>
            );
          })}

          <div className="chip-separator"></div>

          {/* Web Vectors / Tactical Layer Toggle */}
          <button
            type="button"
            className={`filter-layer-btn ${isWebVectorsActive ? 'active' : ''}`}
            onClick={() => setIsWebVectorsActive(!isWebVectorsActive)}
            aria-pressed={isWebVectorsActive}
            title="Toggle tactical web vector telemetry overlay"
          >
            <Globe size={13} />
            <span>WEB VECTORS: {isWebVectorsActive ? 'ON' : 'OFF'}</span>
          </button>
        </div>
      </div>

      {/* Main Multi-Pane Tactical Layout (65% Map Dominant / 35% Priority Rail) */}
      <main className="workspace-split">
        {/* Left Pane (65%): Tactical Cartographic Map Canvas */}
        <TacticalMap
          incidents={incidents}
          selectedIncidentId={activeSelectedIncident?.incident_id ?? null}
          onSelectIncident={handleSelectIncident}
          className="deck-map-pane"
        />

        {/* Right Pane (35%): Incident Priority Rail & Triage Dock */}
        <IncidentQueueRail
          incidents={incidents}
          selectedIncident={activeSelectedIncident}
          selectedIncidentId={activeSelectedIncident?.incident_id ?? null}
          onSelectIncident={handleSelectIncident}
          onInvestigateIncident={navigateToIncident}
          searchQuery={searchQuery}
          isLoading={isLoading}
          error={error}
          onRetry={() => refetch()}
          criticalCount={criticalCount}
          className="deck-queue-pane"
        />
      </main>

      {/* Bottom Command Bar: Audio Monitor & Quick Controls */}
      <TacticalCommandBar />
    </div>
  );
};

export default CommandDeckView;
