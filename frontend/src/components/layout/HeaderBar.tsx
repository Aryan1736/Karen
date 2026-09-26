import React from 'react';
import {
  Badge,
  StatusIndicator,
  AudioVisualizerBar
} from '../ui';
import { useNavigation, NavigationView } from '../../context/NavigationContext';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import { useWebSocket } from '../../context/WebSocketContext';
import { getOperatorId } from '../../api/client';
import './HeaderBar.css';

interface NavItem {
  id: NavigationView;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'command-deck', label: 'Deck' },
  { id: 'incident-streams', label: 'Streams' },
  { id: 'investigation', label: 'Investigation' },
  { id: 'audit-trail', label: 'Audit Trail' },
  { id: 'briefing', label: 'Briefing' },
];

export const HeaderBar: React.FC = () => {
  const { activeView, setActiveView } = useNavigation();
  const { isOnline } = useBackendHealth();
  const { status: wsStatus } = useWebSocket();
  const operatorId = getOperatorId();

  // Map API health probe state truthfully
  const engineIndicatorStatus = isOnline === true ? 'online' : isOnline === false ? 'offline' : 'standby';
  const engineIndicatorLabel = isOnline === true ? 'API ONLINE' : isOnline === false ? 'API OFFLINE' : 'CHECKING...';

  // Map WebSocket connection state truthfully
  const wsIndicatorStatus = wsStatus === 'CONNECTED' ? 'online' : (wsStatus === 'DISCONNECTED' || wsStatus === 'ERROR') ? 'offline' : 'standby';
  const wsIndicatorLabel = `WS ${wsStatus}`;

  return (
    <header className="header-bar" role="banner">
      <div className="header-left">
        <div
          className="header-brand-group clickable"
          onClick={() => setActiveView('landing')}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setActiveView('landing');
            }
          }}
          title="Return to Tingle Landing Page"
          aria-label="Return to Tingle Landing Page"
        >
          <span className="brand-logo-badge">TINGLE</span>
          <Badge variant="p2-medium" size="sm">TAC-OPS</Badge>
        </div>
        <div className="header-hud-metrics">
          <StatusIndicator status={engineIndicatorStatus} label={engineIndicatorLabel} />
          <StatusIndicator status={wsIndicatorStatus} label={wsIndicatorLabel} />
        </div>
      </div>

      <nav className="header-nav" aria-label="Tactical Views Navigation">
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
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="header-right">
        <div className="header-channel-monitor">
          <span className="channel-label">RF MONITOR:</span>
          <AudioVisualizerBar active={false} />
          <span className="channel-freq">STANDBY</span>
        </div>
        <div className="operator-badge">
          OP: {operatorId.toUpperCase()}
        </div>
      </div>
    </header>
  );
};

export default HeaderBar;
