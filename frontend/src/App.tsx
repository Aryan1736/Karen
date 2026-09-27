import React from 'react';
import { NavigationProvider, useNavigation } from './context/NavigationContext';
import { WebSocketProvider } from './context/WebSocketContext';
import { HeaderBar, FooterBar } from './components/layout';
import {
  LandingPageView,
  CommandDeckView,
  IncidentStreamsView,
  InvestigationView,
  AuditTrailView,
  BriefingView
} from './components/views';
import { SimulationModal } from './components/simulator/SimulationModal';
import './App.css';

const AppViewport: React.FC = () => {
  const { activeView } = useNavigation();

  if (activeView === 'landing') {
    return (
      <>
        <LandingPageView />
        <SimulationModal />
      </>
    );
  }

  return (
    <div className="command-center">
      {/* Primary Header with Branding & View Navigation Tabs */}
      <HeaderBar />

      {/* Dynamic Viewport displaying active structural view */}
      <div className="command-center-viewport">
        {activeView === 'command-deck' && <CommandDeckView />}
        {activeView === 'incident-streams' && <IncidentStreamsView />}
        {activeView === 'investigation' && <InvestigationView />}
        {activeView === 'audit-trail' && <AuditTrailView />}
        {activeView === 'briefing' && <BriefingView />}
      </div>

      {/* Footer Telemetry & Status Bar */}
      <FooterBar />

      {/* Global Interactive Disaster Simulator Modal */}
      <SimulationModal />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <NavigationProvider>
      <WebSocketProvider>
        <AppViewport />
      </WebSocketProvider>
    </NavigationProvider>
  );
};

export default App;
