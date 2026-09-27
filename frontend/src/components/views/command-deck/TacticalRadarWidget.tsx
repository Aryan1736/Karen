import React, { useMemo } from 'react';
import { Globe, Crosshair } from 'lucide-react';
import { Incident } from '../../../types/incident';
import './TacticalRadarWidget.css';

export interface TacticalRadarWidgetProps {
  incidents: Incident[];
  selectedIncidentId: string | null;
  mapCenter: { lat: number; lng: number };
  onSelectIncident: (id: string) => void;
  onGlobalView: () => void;
  onCenterView: () => void;
  className?: string;
}

/**
 * Calculates geodetically truthful initial bearing (0-360°) and distance (km)
 * between two GPS coordinates using the Haversine spherical formula.
 */
function calculateRealBearingAndDistance(
  fromLat: number,
  fromLng: number,
  toLat: number,
  toLng: number
): { bearing: number; distanceKm: number; compassDir: string } {
  const R = 6371; // Earth's mean radius in km
  const dLat = ((toLat - fromLat) * Math.PI) / 180;
  const dLng = ((toLng - fromLng) * Math.PI) / 180;
  const lat1 = (fromLat * Math.PI) / 180;
  const lat2 = (toLat * Math.PI) / 180;

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.sin(dLng / 2) * Math.sin(dLng / 2) * Math.cos(lat1) * Math.cos(lat2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const distanceKm = R * c;

  const y = Math.sin(dLng) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
  let brng = (Math.atan2(y, x) * 180) / Math.PI;
  brng = (brng + 360) % 360;

  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const index = Math.round(brng / 45) % 8;

  return {
    bearing: Math.round(brng),
    distanceKm: Math.round(distanceKm * 10) / 10,
    compassDir: directions[index],
  };
}

export const TacticalRadarWidget: React.FC<TacticalRadarWidgetProps> = ({
  incidents,
  selectedIncidentId,
  mapCenter,
  onSelectIncident,
  onGlobalView,
  onCenterView,
  className = '',
}) => {
  // SVG Geometry constants
  const size = 130;
  const cx = 65;
  const cy = 65;
  const outerR = 52;
  const sides = 12;

  // Filter valid mapped incidents strictly
  const mappedIncidents = useMemo(() => {
    return incidents.filter(
      (inc) =>
        typeof inc.location?.latitude === 'number' &&
        typeof inc.location?.longitude === 'number' &&
        !isNaN(inc.location.latitude) &&
        !isNaN(inc.location.longitude)
    );
  }, [incidents]);

  // Selected incident details
  const selectedIncident = useMemo(() => {
    return incidents.find((i) => i.incident_id === selectedIncidentId);
  }, [incidents, selectedIncidentId]);

  const selectedTelemetry = useMemo(() => {
    if (
      !selectedIncident ||
      selectedIncident.location?.latitude == null ||
      selectedIncident.location?.longitude == null
    ) {
      return null;
    }
    return calculateRealBearingAndDistance(
      mapCenter.lat,
      mapCenter.lng,
      selectedIncident.location.latitude,
      selectedIncident.location.longitude
    );
  }, [selectedIncident, mapCenter]);

  // Compute maximum distance for radar scope scaling (minimum 5 km)
  const maxDistanceKm = useMemo(() => {
    let max = 5;
    mappedIncidents.forEach((inc) => {
      const d = calculateRealBearingAndDistance(
        mapCenter.lat,
        mapCenter.lng,
        inc.location.latitude!,
        inc.location.longitude!
      ).distanceKm;
      if (d > max) max = d;
    });
    return Math.min(max, 50); // cap max scale at 50km
  }, [mappedIncidents, mapCenter]);

  // Compute target pips for all mapped incidents
  const targetPips = useMemo(() => {
    return mappedIncidents.map((inc) => {
      const { bearing, distanceKm } = calculateRealBearingAndDistance(
        mapCenter.lat,
        mapCenter.lng,
        inc.location.latitude!,
        inc.location.longitude!
      );

      // Map distance to radial distance on scope (between 12px and outerR - 4px)
      const normalizedDist = Math.min(distanceKm / maxDistanceKm, 1);
      const r = 12 + normalizedDist * (outerR - 16);

      // Angle on SVG where 0° North is straight UP (-90°)
      const angleRad = ((bearing - 90) * Math.PI) / 180;
      const x = cx + r * Math.cos(angleRad);
      const y = cy + r * Math.sin(angleRad);

      const isSelected = selectedIncidentId === inc.incident_id;
      const isP0 = inc.priority?.level === 'CRITICAL';
      const isHigh = inc.priority?.level === 'HIGH';
      const isMed = inc.priority?.level === 'MEDIUM';

      let pipColor = '#38bdf8'; // LOW / default cyan
      if (isP0) pipColor = '#ef4444';
      else if (isHigh) pipColor = '#f97316';
      else if (isMed) pipColor = '#eab308';
      else if (inc.status === 'NEEDS_REVIEW') pipColor = '#c084fc';

      return {
        id: inc.incident_id,
        x,
        y,
        color: pipColor,
        isSelected,
        distanceKm,
        bearing,
      };
    });
  }, [mappedIncidents, selectedIncidentId, mapCenter, maxDistanceKm]);

  // Outer polygon points
  const outerPolygonPoints = useMemo(() => {
    const pts: string[] = [];
    for (let i = 0; i < sides; i++) {
      const angle = ((i * 360) / sides - 90) * (Math.PI / 180);
      const x = (cx + outerR * Math.cos(angle)).toFixed(1);
      const y = (cy + outerR * Math.sin(angle)).toFixed(1);
      pts.push(`${x},${y}`);
    }
    return pts.join(' ');
  }, []);

  // Concentric spiderweb rings with inward curved catenary dips
  const webRings = useMemo(() => {
    const ringRadii = [outerR * 0.28, outerR * 0.52, outerR * 0.76];
    return ringRadii.map((r) => {
      let d = '';
      for (let i = 0; i < sides; i++) {
        const a1 = ((i * 360) / sides - 90) * (Math.PI / 180);
        const a2 = (((i + 1) * 360) / sides - 90) * (Math.PI / 180);
        const amid = (((i + 0.5) * 360) / sides - 90) * (Math.PI / 180);

        const p1x = cx + r * Math.cos(a1);
        const p1y = cy + r * Math.sin(a1);
        const p2x = cx + r * Math.cos(a2);
        const p2y = cy + r * Math.sin(a2);
        // Slight inward dip to create the spiderweb curve from reference
        const qx = cx + r * 0.91 * Math.cos(amid);
        const qy = cy + r * 0.91 * Math.sin(amid);

        if (i === 0) {
          d += `M ${p1x.toFixed(1)} ${p1y.toFixed(1)} `;
        }
        d += `Q ${qx.toFixed(1)} ${qy.toFixed(1)} ${p2x.toFixed(1)} ${p2y.toFixed(1)} `;
      }
      return d + 'Z';
    });
  }, []);

  // 12 Radial Spoke Lines
  const radialSpokes = useMemo(() => {
    const spokes: { x1: number; y1: number; x2: number; y2: number }[] = [];
    for (let i = 0; i < sides; i++) {
      const angle = ((i * 360) / sides - 90) * (Math.PI / 180);
      spokes.push({
        x1: cx,
        y1: cy,
        x2: cx + outerR * Math.cos(angle),
        y2: cy + outerR * Math.sin(angle),
      });
    }
    return spokes;
  }, []);

  // Vector Sweep Line (Direct line to active target, or animated radar sweep)
  const sweepAngle = selectedTelemetry ? selectedTelemetry.bearing : null;

  return (
    <div className={`tactical-radar-container ${className}`} aria-label="Tactical Target Radar">
      <div className="radar-web-frame">
        <svg
          className="radar-web-svg"
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
        >
          <defs>
            {/* Background radial gradient */}
            <radialGradient id="radarDarkGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#092847" stopOpacity="0.85" />
              <stop offset="70%" stopColor="#061527" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#030a14" stopOpacity="1" />
            </radialGradient>

            {/* Glowing sweep filter */}
            <filter id="cyanGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Dodecagon Background */}
          <polygon
            points={outerPolygonPoints}
            fill="url(#radarDarkGlow)"
            stroke="#38bdf8"
            strokeWidth="1.8"
            className="radar-poly-bg"
          />

          {/* Concentric Spiderweb Rings */}
          {webRings.map((d, idx) => (
            <path
              key={`ring-${idx}`}
              d={d}
              fill="none"
              stroke="#0ea5e9"
              strokeWidth="0.9"
              strokeOpacity={0.45 + idx * 0.1}
            />
          ))}

          {/* 12 Radial Spokes */}
          {radialSpokes.map((spoke, idx) => (
            <line
              key={`spoke-${idx}`}
              x1={spoke.x1}
              y1={spoke.y1}
              x2={spoke.x2}
              y2={spoke.y2}
              stroke="#0ea5e9"
              strokeWidth="0.9"
              strokeOpacity="0.5"
            />
          ))}

          {/* Active Bearing Vector Ray (Points accurately to selected target) */}
          {sweepAngle != null ? (
            <g>
              <line
                x1={cx}
                y1={cy}
                x2={cx + outerR * Math.cos(((sweepAngle - 90) * Math.PI) / 180)}
                y2={cy + outerR * Math.sin(((sweepAngle - 90) * Math.PI) / 180)}
                stroke="#00f0ff"
                strokeWidth="2.2"
                filter="url(#cyanGlow)"
              />
              <circle
                cx={cx + outerR * Math.cos(((sweepAngle - 90) * Math.PI) / 180)}
                cy={cy + outerR * Math.sin(((sweepAngle - 90) * Math.PI) / 180)}
                r="3"
                fill="#00f0ff"
              />
            </g>
          ) : (
            /* Ambient 360° Live Radar Sweep when no incident is explicitly locked */
            <g className="radar-ambient-sweep">
              <line
                x1={cx}
                y1={cy}
                x2={cx}
                y2={cy - outerR}
                stroke="#00f0ff"
                strokeWidth="1.8"
                filter="url(#cyanGlow)"
              />
            </g>
          )}

          {/* Real Plotted Incident Target Pips */}
          {targetPips.map((pip) => (
            <g
              key={pip.id}
              className="radar-target-pip"
              onClick={() => onSelectIncident(pip.id)}
              style={{ cursor: 'pointer' }}
            >
              {pip.isSelected && (
                <circle
                  cx={pip.x}
                  cy={pip.y}
                  r="7"
                  fill="none"
                  stroke="#00f0ff"
                  strokeWidth="1.5"
                  className="radar-pip-pulse"
                />
              )}
              <circle
                cx={pip.x}
                cy={pip.y}
                r={pip.isSelected ? 3.5 : 2.5}
                fill={pip.color}
                stroke="#000000"
                strokeWidth="0.8"
              />
            </g>
          ))}

          {/* Center Hub Dot */}
          <circle cx={cx} cy={cy} r="3.5" fill="#00f0ff" filter="url(#cyanGlow)" />
          <circle cx={cx} cy={cy} r="1.5" fill="#ffffff" />
        </svg>

        {/* Tactical Perimeter Action Buttons directly from Reference Image */}
        {/* 1. Globe Button on Right Edge (Switch to Global View) */}
        <button
          type="button"
          className="radar-edge-btn btn-globe"
          onClick={onGlobalView}
          title="Switch to global view"
          aria-label="Switch to global view"
        >
          <Globe size={13} className="radar-btn-icon" />
        </button>

        {/* 2. Target Button on Lower-Right Edge (Switch to Center / Neighborhood View) */}
        <button
          type="button"
          className={`radar-edge-btn btn-target ${selectedTelemetry ? 'locked' : ''}`}
          onClick={onCenterView}
          title="Switch to center view (neighborhood)"
          aria-label="Switch to center view"
        >
          <Crosshair size={13} className="radar-btn-icon" />
        </button>
      </div>

      {/* Real Mathematical Telemetry Readout Below Radar (Zero Hallucinated Numbers) */}
      <div className="radar-telemetry-readout">
        {selectedTelemetry && selectedIncident ? (
          <div className="radar-telemetry-locked">
            <span className="telemetry-pill-target">TRK: {selectedIncident.incident_id}</span>
            <span className="telemetry-vals">
              BRG: {selectedTelemetry.bearing}° {selectedTelemetry.compassDir} // RNG: {selectedTelemetry.distanceKm} KM
            </span>
          </div>
        ) : (
          <div className="radar-telemetry-idle">
            <span className="telemetry-pill-idle">
              SCOPE: {maxDistanceKm.toFixed(0)} KM
            </span>
            <span className="telemetry-vals">
              {mappedIncidents.length} TARGETS GEO-LOCKED
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default TacticalRadarWidget;
