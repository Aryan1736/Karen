import React, { useState, useEffect } from 'react';
import { 
  Play, 
  Square, 
  Zap, 
  Activity, 
  X, 
  CheckCircle2, 
  AlertTriangle,
  Sliders,
  Layers,
  Sparkles
} from 'lucide-react';
import { useNavigation } from '../../context/NavigationContext';
import { useWebSocket } from '../../context/WebSocketContext';
import { 
  fetchSimulationScenarios, 
  fetchSimulationStatus, 
  startSimulation, 
  stopSimulation, 
  injectSimulationPulse 
} from '../../api/simulation';
import { 
  SimulationScenario, 
  SimulationStatusData, 
  SimulationSpeed 
} from '../../types/simulation';
import './SimulationModal.css';

export const SimulationModal: React.FC = () => {
  const { isSimulatorModalOpen, setIsSimulatorModalOpen } = useNavigation();
  const { lastEvent } = useWebSocket();

  const [scenarios, setScenarios] = useState<SimulationScenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('flood_rasulgarh');
  const [selectedSpeed, setSelectedSpeed] = useState<SimulationSpeed>('burst');
  const [statusData, setStatusData] = useState<SimulationStatusData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [pulseLoading, setPulseLoading] = useState<boolean>(false);
  const [lastDispatchedInfo, setLastDispatchedInfo] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Load scenarios on open
  useEffect(() => {
    if (!isSimulatorModalOpen) return;

    let mounted = true;
    async function loadData() {
      try {
        const [scList, stData] = await Promise.all([
          fetchSimulationScenarios(),
          fetchSimulationStatus(),
        ]);
        if (mounted) {
          setScenarios(scList);
          setStatusData(stData);
          if (stData.scenario_id) {
            setSelectedScenarioId(stData.scenario_id);
          } else if (scList.length > 0 && !selectedScenarioId) {
            setSelectedScenarioId(scList[0].id);
          }
        }
      } catch (err) {
        console.error('Failed to load simulation metadata:', err);
      }
    }
    loadData();

    return () => {
      mounted = false;
    };
  }, [isSimulatorModalOpen]);

  // Synchronize on incoming WebSocket events (SIMULATION_PULSE or INCIDENT_CREATED)
  useEffect(() => {
    if (!lastEvent) return;

    if (lastEvent.event === 'SIMULATION_PULSE') {
      const p = lastEvent.payload as { injected_count?: number; total_simulated?: number; scenario?: string };
      setStatusData((prev) => prev ? ({
        ...prev,
        reports_injected: p.total_simulated ?? (prev.reports_injected + 1),
        scenario_id: p.scenario ?? prev.scenario_id,
        is_running: true,
        status: 'RUNNING',
      }) : null);
    } else if (lastEvent.event === 'INCIDENT_CREATED' || lastEvent.event === 'INCIDENT_UPDATED') {
      const inc = lastEvent.payload as any;
      if (inc?.location?.text) {
        setLastDispatchedInfo(`Dispatched: ${inc.incident_type || 'INCIDENT'} at ${inc.location.text}`);
      }
    }
  }, [lastEvent]);

  // Periodic status poll when modal is open and simulation is active
  useEffect(() => {
    if (!isSimulatorModalOpen || !statusData?.is_running) return;

    const interval = setInterval(async () => {
      try {
        const latest = await fetchSimulationStatus();
        setStatusData(latest);
      } catch (e) {
        // ignore periodic poll errors
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [isSimulatorModalOpen, statusData?.is_running]);

  const handleStart = async () => {
    setIsLoading(true);
    setFeedbackMessage(null);
    try {
      const res = await startSimulation({
        scenario_id: selectedScenarioId,
        speed: selectedSpeed,
      });
      setStatusData({
        status: 'RUNNING',
        is_running: true,
        simulation_id: res.simulation_id,
        scenario_id: res.scenario_id,
        reports_injected: 0,
        total_events: activeScenario?.total_events ?? 15,
        started_at: res.started_at,
        ended_at: null,
      });
      setFeedbackMessage({
        text: `Simulation started: streaming ${activeScenario?.name || selectedScenarioId}...`,
        type: 'success',
      });
    } catch (err: any) {
      setFeedbackMessage({
        text: err?.message || 'Failed to start simulation',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    setIsLoading(true);
    try {
      const stopped = await stopSimulation();
      setStatusData(stopped);
      setFeedbackMessage({
        text: 'Simulation playback stopped.',
        type: 'info',
      });
    } catch (err: any) {
      setFeedbackMessage({
        text: err?.message || 'Failed to stop simulation',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handlePulse = async () => {
    setPulseLoading(true);
    setFeedbackMessage(null);
    try {
      const pulseRes = await injectSimulationPulse({
        scenario_id: selectedScenarioId,
      });
      setLastDispatchedInfo(
        `Injected step #${pulseRes.event_index + 1}: ${pulseRes.report_id} (${pulseRes.relationship || 'DISPATCH'})`
      );
      setFeedbackMessage({
        text: `Pulse injected into incident ${pulseRes.incident_id.substring(0, 12)}...`,
        type: 'success',
      });
      setStatusData((prev) => prev ? ({
        ...prev,
        reports_injected: prev.reports_injected + 1,
      }) : null);
    } catch (err: any) {
      setFeedbackMessage({
        text: err?.message || 'Failed to inject simulation pulse',
        type: 'error',
      });
    } finally {
      setPulseLoading(false);
    }
  };

  if (!isSimulatorModalOpen) return null;

  const activeScenario = scenarios.find((s) => s.id === selectedScenarioId);
  const totalEvents = activeScenario?.total_events || statusData?.total_events || 15;
  const currentInjected = statusData?.reports_injected || 0;
  const progressPercent = Math.min(100, Math.round((currentInjected / totalEvents) * 100));

  return (
    <div className="sim-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="sim-modal-title">
      <div className="sim-modal-card">
        {/* Header */}
        <div className="sim-modal-header">
          <div className="sim-modal-title-wrap">
            <span className="sim-tag-tape">CRISIS TEST HARNESS</span>
            <div className="sim-title-flex">
              <Activity size={18} className="text-cyan sim-spin-slow" />
              <h2 id="sim-modal-title" className="sim-modal-title">DISASTER SCENARIO SIMULATOR</h2>
            </div>
          </div>
          <button 
            type="button" 
            className="sim-close-btn"
            onClick={() => setIsSimulatorModalOpen(false)}
            aria-label="Close Simulator"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body Content */}
        <div className="sim-modal-body">
          {/* Active Status Ribbon */}
          <div className="sim-status-banner">
            <div className="sim-status-left">
              <span className={`sim-beacon-dot ${statusData?.is_running ? 'beacon-pulse' : ''}`} />
              <span className="sim-status-label">STATUS:</span>
              <span className={`sim-status-val status-${(statusData?.status || 'IDLE').toLowerCase()}`}>
                {statusData?.status || 'IDLE'}
              </span>
            </div>
            <div className="sim-status-right font-mono">
              <span>DISPATCHES INJECTED: </span>
              <strong className="text-cyan">{currentInjected} / {totalEvents}</strong>
            </div>
          </div>

          {/* Progress Track */}
          <div className="sim-progress-track">
            <div 
              className={`sim-progress-fill ${statusData?.is_running ? 'fill-animated' : ''}`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Scenario Selection */}
          <div className="sim-section">
            <label className="sim-section-label">
              <Layers size={13} style={{ marginRight: 6 }} />
              SELECT CRISIS SCENARIO:
            </label>
            <div className="sim-scenario-grid">
              {scenarios.map((sc) => (
                <div 
                  key={sc.id}
                  className={`sim-scenario-card ${selectedScenarioId === sc.id ? 'is-selected' : ''}`}
                  onClick={() => setSelectedScenarioId(sc.id)}
                >
                  <div className="sim-scenario-top">
                    <span className="sim-sc-name font-headline">{sc.name}</span>
                    <span className="sim-sc-badge font-mono">{sc.total_events} EVENTS</span>
                  </div>
                  <p className="sim-sc-desc">{sc.description}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Speed Selector */}
          <div className="sim-section">
            <label className="sim-section-label">
              <Sliders size={13} style={{ marginRight: 6 }} />
              PLAYBACK SPEED / CADENCE:
            </label>
            <div className="sim-speed-options">
              {(['burst', '10x', '5x', '2x', '1x'] as SimulationSpeed[]).map((spd) => (
                <button
                  key={spd}
                  type="button"
                  className={`sim-speed-btn font-mono ${selectedSpeed === spd ? 'is-selected' : ''}`}
                  onClick={() => setSelectedSpeed(spd)}
                >
                  {spd === 'burst' ? '⚡ Burst Mode' : `${spd} Speed`}
                </button>
              ))}
            </div>
          </div>

          {/* Feedback & Dispatched Telemetry */}
          {feedbackMessage && (
            <div className={`sim-feedback-banner feedback-${feedbackMessage.type} font-mono`}>
              {feedbackMessage.type === 'success' && <CheckCircle2 size={14} style={{ marginRight: 6 }} />}
              {feedbackMessage.type === 'error' && <AlertTriangle size={14} style={{ marginRight: 6 }} />}
              {feedbackMessage.text}
            </div>
          )}

          {lastDispatchedInfo && (
            <div className="sim-telemetry-chip font-mono">
              <Sparkles size={12} className="text-dispatch-yellow" style={{ marginRight: 6 }} />
              <span>{lastDispatchedInfo}</span>
            </div>
          )}
        </div>

        {/* Modal Actions Footer */}
        <div className="sim-modal-footer">
          <button
            type="button"
            className="sim-action-btn sim-pulse-btn"
            onClick={handlePulse}
            disabled={pulseLoading || isLoading}
            title="Inject a single event immediately for step-by-step verification"
          >
            <Zap size={14} style={{ marginRight: 6 }} />
            {pulseLoading ? 'Injecting...' : 'Inject Single Step'}
          </button>

          {statusData?.is_running ? (
            <button
              type="button"
              className="sim-action-btn sim-stop-btn"
              onClick={handleStop}
              disabled={isLoading}
            >
              <Square size={14} style={{ marginRight: 6 }} />
              Halt Simulation
            </button>
          ) : (
            <button
              type="button"
              className="sim-action-btn sim-start-btn"
              onClick={handleStart}
              disabled={isLoading || scenarios.length === 0}
            >
              <Play size={14} style={{ marginRight: 6 }} />
              {isLoading ? 'Starting...' : 'Start Scenario Stream'}
            </button>
          )}

          <button
            type="button"
            className="sim-cancel-btn"
            onClick={() => setIsSimulatorModalOpen(false)}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
