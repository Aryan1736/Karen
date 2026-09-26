import React, { useState, useEffect } from 'react';
import { Clock, Wifi } from 'lucide-react';
import './FooterBar.css';

export const FooterBar: React.FC = () => {
  const [currentTime, setCurrentTime] = useState<string>(() => 
    new Date().toISOString().substring(11, 19) + ' UTC'
  );

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toISOString().substring(11, 19) + ' UTC');
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <footer className="footer-bar" role="contentinfo">
      <div className="footer-left">
        <span>PRODUCT: TINGLE</span>
        <span>DECISION SUPPORT v1.2</span>
        <span>HUMAN-IN-THE-LOOP SOVEREIGN</span>
      </div>
      <div className="footer-right">
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Clock size={12} />
          {currentTime}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Wifi size={12} />
          WS STANDBY
        </span>
      </div>
    </footer>
  );
};

export default FooterBar;
