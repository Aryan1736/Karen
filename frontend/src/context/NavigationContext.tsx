import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

export type NavigationView = 
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
  'command-deck': '#deck',
  'incident-streams': '#streams',
  'investigation': '#investigation',
  'audit-trail': '#audit',
  'briefing': '#briefing',
};

const HASH_VIEW_MAP: Record<string, NavigationView> = {
  '#deck': 'command-deck',
  '#streams': 'incident-streams',
  '#investigation': 'investigation',
  '#audit': 'audit-trail',
  '#briefing': 'briefing',
};

const getViewFromHash = (hash: string): NavigationView => {
  return HASH_VIEW_MAP[hash.toLowerCase()] || 'command-deck';
};

const NavigationContext = createContext<NavigationContextValue | undefined>(undefined);

export const NavigationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeView, setActiveViewState] = useState<NavigationView>(() => 
    typeof window !== 'undefined' ? getViewFromHash(window.location.hash) : 'command-deck'
  );
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<IncidentPriorityFilter>('ALL');
  const [isSimulatorModalOpen, setIsSimulatorModalOpen] = useState<boolean>(false);
  const [isReportModalOpen, setIsReportModalOpen] = useState<boolean>(false);

  // Sync state when browser hash changes (e.g. back/forward buttons)
  useEffect(() => {
    const handleHashChange = () => {
      const newView = getViewFromHash(window.location.hash);
      setActiveViewState(newView);
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const setActiveView = useCallback((view: NavigationView) => {
    setActiveViewState(view);
    const targetHash = VIEW_HASH_MAP[view];
    if (window.location.hash !== targetHash) {
      window.location.hash = targetHash;
    }
  }, []);

  const navigateToIncident = useCallback((incidentId: string) => {
    setSelectedIncidentId(incidentId);
    setActiveView('investigation');
  }, [setActiveView]);

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
