import React from 'react';
import './FooterBar.css';

export const FooterBar: React.FC = () => {
  return (
    <footer className="footer-bar" role="contentinfo">
      <div className="footer-left">
        <span className="footer-brand">TINGLE</span>
        <span className="footer-dot">•</span>
        <span className="footer-muted">Emergency Operations Console</span>
        <span className="footer-dot">•</span>
        <span className="footer-muted">Realtime Triage Feed</span>
      </div>
      <div className="footer-right">
        <span className="footer-version">v1.2</span>
        <span className="footer-dot">•</span>
        <span className="footer-status">
          <span className="footer-status-dot" />
          <span>Operational</span>
        </span>
      </div>
    </footer>
  );
};

export default FooterBar;
