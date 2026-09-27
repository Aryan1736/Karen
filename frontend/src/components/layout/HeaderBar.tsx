import React from 'react';
import { useNavigation, NavigationView } from '../../context/NavigationContext';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import { useWebSocketStatus } from '../../context/WebSocketContext';
import { getOperatorId } from '../../api/client';
import './HeaderBar.css';

interface NavItem {
  id: NavigationView;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'command-deck', label: 'Command Deck' },
  { id: 'incident-streams', label: 'Live Streams' },
  { id: 'investigation', label: 'Investigation' },
  { id: 'audit-trail', label: 'Audit Ledger' },
  { id: 'briefing', label: 'System Briefing' },
];

export const HeaderBar: React.FC = () => {
  const { activeView, setActiveView } = useNavigation();
  const { isOnline } = useBackendHealth();
  const { status: wsStatus } = useWebSocketStatus();
  const operatorId = getOperatorId();

  const isConnected = isOnline && wsStatus === 'CONNECTED';

  return (
    <header className="header-bar" role="banner">
      <div className="header-left">
        <div
          className="header-brand clickable"
          onClick={() => setActiveView('landing')}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setActiveView('landing');
            }
          }}
          title="Return to Tingle Landing Overview"
          aria-label="Return to Tingle Landing Overview"
        >
          <span className="brand-dot" aria-hidden="true" />
          <span className="brand-logo-text">TINGLE</span>
        </div>

        {/* Small letter size sync element */}
        <div 
          className="header-sync-pill"
          title={`Backend: ${isOnline ? 'Online' : 'Offline'} | WebSocket: ${wsStatus}`}
          aria-label="System Connection Status"
        >
          <span className={`sync-dot ${isConnected ? 'online' : isOnline ? 'standby' : 'offline'}`} />
          <span className="sync-text">
            {isConnected ? 'ONLINE' : isOnline ? 'CONNECTING' : 'OFFLINE'}
          </span>
        </div>
      </div>

      {/* Main navigation tabs */}
      <nav className="header-nav" aria-label="Views Navigation">
        {NAV_ITEMS.map((item) => {
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-tab-btn ${isActive ? 'active' : ''}`}
              onClick={() => setActiveView(item.id)}
              aria-current={isActive ? 'page' : undefined}
            >
              <span className="nav-tab-label">{item.label}</span>
              {isActive && <span className="nav-tab-glow" />}
            </button>
          );
        })}
      </nav>

      <div className="header-right">
        <div className="header-operator-pill" title={`Active Operator Session: ${operatorId}`}>
          <span className="operator-label">OPERATOR</span>
          <span className="operator-id">{operatorId.toUpperCase()}</span>
        </div>
        <button 
          type="button"
          className="header-exit-btn"
          onClick={() => setActiveView('landing')}
          title="Return to Overview"
        >
          Overview
        </button>
      </div>
    </header>
  );
};

export default HeaderBar;
