import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

export type NavigationView = 
  | 'landing'
  | 'command-deck' 
  | 'incident-streams' 
  | 'investigation' 
  | 'audit-trail' 
  | 'briefing';

export type IncidentPriorityFilter = 'ALL' | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'NEEDS_REVIEW';

export interface NavigationContextValue {
  activeView: NavigationView;
  setActiveView: (view: NavigationView) => void;
  selectedIncidentId: string | null;
  setSelectedIncidentId: (id: string | null) => void;
  activeFilter: IncidentPriorityFilter;
  setActiveFilter: (filter: IncidentPriorityFilter) => void;
  isSimulatorModalOpen: boolean;
  setIsSimulatorModalOpen: (open: boolean) => void;
  isReportModalOpen: boolean;
  setIsReportModalOpen: (open: boolean) => void;
  navigateToIncident: (incidentId: string) => void;
}

const VIEW_HASH_MAP: Record<NavigationView, string> = {
  'landing': '#landing',
  'command-deck': '#deck',
  'incident-streams': '#streams',
  'investigation': '#investigation',
  'audit-trail': '#audit',
  'briefing': '#briefing',
};

const HASH_VIEW_MAP: Record<string, NavigationView> = {
  '#landing': 'landing',
  '#deck': 'command-deck',
  '#streams': 'incident-streams',
  '#investigation': 'investigation',
  '#audit': 'audit-trail',
  '#briefing': 'briefing',
};

const getViewFromHash = (hash: string): NavigationView => {
  if (!hash) return 'landing';
  const cleanHash = hash.split('?')[0].replace(/\/+$/, '').toLowerCase();
  if (!cleanHash || cleanHash === '#' || cleanHash === '#landing') {
    return 'landing';
  }
  return HASH_VIEW_MAP[cleanHash] || 'landing';
};

const getIncidentIdFromHash = (hash: string): string | null => {
  if (!hash || !hash.includes('?')) return null;
  try {
    const queryPart = hash.split('?')[1];
    const params = new URLSearchParams(queryPart);
    const id = params.get('id') || params.get('incident_id') || params.get('incidentId');
    return id ? id.trim() : null;
  } catch {
    return null;
  }
};

const NavigationContext = createContext<NavigationContextValue | undefined>(undefined);

export const NavigationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeView, setActiveViewState] = useState<NavigationView>(() => 
    typeof window !== 'undefined' ? getViewFromHash(window.location.hash) : 'landing'
  );
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(() =>
    typeof window !== 'undefined' ? getIncidentIdFromHash(window.location.hash) : null
  );
  const [activeFilter, setActiveFilter] = useState<IncidentPriorityFilter>('ALL');
  const [isSimulatorModalOpen, setIsSimulatorModalOpen] = useState<boolean>(false);
  const [isReportModalOpen, setIsReportModalOpen] = useState<boolean>(false);

  // Sync state when browser hash changes (e.g. back/forward buttons, direct deep links)
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash;
      const newView = getViewFromHash(hash);
      setActiveViewState(newView);
      const incId = getIncidentIdFromHash(hash);
      if (incId) {
        setSelectedIncidentId(incId);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const setActiveView = useCallback((view: NavigationView) => {
    setActiveViewState(view);
    const baseHash = VIEW_HASH_MAP[view];
    const targetHash = (view === 'investigation' && selectedIncidentId)
      ? `${baseHash}?id=${encodeURIComponent(selectedIncidentId)}`
      : baseHash;
    if (window.location.hash !== targetHash) {
      window.location.hash = targetHash;
    }
  }, [selectedIncidentId]);

  const navigateToIncident = useCallback((incidentId: string) => {
    setSelectedIncidentId(incidentId);
    setActiveViewState('investigation');
    const targetHash = `#investigation?id=${encodeURIComponent(incidentId)}`;
    if (window.location.hash !== targetHash) {
      window.location.hash = targetHash;
    }
  }, []);

  return (
    <NavigationContext.Provider
      value={{
        activeView,
        setActiveView,
        selectedIncidentId,
        setSelectedIncidentId,
        activeFilter,
        setActiveFilter,
        isSimulatorModalOpen,
        setIsSimulatorModalOpen,
        isReportModalOpen,
        setIsReportModalOpen,
        navigateToIncident,
      }}
    >
      {children}
    </NavigationContext.Provider>
  );
};

export const useNavigation = (): NavigationContextValue => {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error('useNavigation must be used within a NavigationProvider');
  }
  return context;
};
