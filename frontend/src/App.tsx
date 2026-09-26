import React from 'react';
import { NavigationProvider, useNavigation } from './context/NavigationContext';
import { WebSocketProvider } from './context/WebSocketContext';
import { SimulationStrip, HeaderBar, FooterBar } from './components/layout';
import {
  CommandDeckView,
  IncidentStreamsView,
  InvestigationView,
  AuditTrailView,
  BriefingView
} from './components/views';
import './App.css';

const AppViewport: React.FC = () => {
  const { activeView } = useNavigation();

  return (
    <div className="command-center">
      {/* Tactical Drill Runbook Banner */}
      <SimulationStrip />

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
