import React, { useEffect, useRef, useState, useMemo } from 'react';
import L from 'leaflet';
import { 
  Radar, 
  AlertTriangle, 
  RotateCcw, 
  ChevronDown, 
  ChevronUp
} from 'lucide-react';
import { Incident } from '../../../types/incident';
import { useWebSocket } from '../../../context/WebSocketContext';
import './TacticalMap.css';

export interface TacticalMapProps {
  incidents: Incident[];
  selectedIncidentId: string | null;
  onSelectIncident: (incidentId: string) => void;
  className?: string;
}

// Default center: NYC Metro area (matching Stitch cartographic focus)
const DEFAULT_CENTER: [number, number] = [40.7505, -73.9934];
const DEFAULT_ZOOM = 13;

export const TacticalMap: React.FC<TacticalMapProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
  className = '',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const [isUnmappedDrawerOpen, setIsUnmappedDrawerOpen] = useState(true);
  const [tileError, setTileError] = useState(false);
  const [currentZoom, setCurrentZoom] = useState(DEFAULT_ZOOM);
  const { status: wsStatus } = useWebSocket();

  // Partition real data into mapped vs unmapped strictly without fabricating coordinates
  const { mappedIncidents, unmappedIncidents } = useMemo(() => {
    const mapped: Incident[] = [];
    const unmapped: Incident[] = [];

    incidents.forEach((inc) => {
      const lat = inc.location?.latitude;
      const lng = inc.location?.longitude;
      if (typeof lat === 'number' && typeof lng === 'number' && !isNaN(lat) && !isNaN(lng)) {
        mapped.push(inc);
      } else {
        unmapped.push(inc);
      }
    });

    return { mappedIncidents: mapped, unmappedIncidents: unmapped };
  }, [incidents]);

  // Initialize Leaflet map instance
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      zoomControl: false,
      attributionControl: false,
    });

    // Dark Matter tile layer (CartoDB) matching the Stitch tactical palette
    const tileLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      subdomains: 'abcd',
    });

    tileLayer.on('tileerror', () => {
      setTileError(true);
    });

    tileLayer.on('tileload', () => {
      setTileError(false);
    });

    tileLayer.addTo(map);

    const markersGroup = L.layerGroup().addTo(map);
    markersLayerRef.current = markersGroup;
    mapInstanceRef.current = map;

    map.on('zoomend', () => {
      setCurrentZoom(map.getZoom());
    });

    // Invalidate size on container layout changes
    const resizeObserver = new ResizeObserver(() => {
      map.invalidateSize();
    });
    resizeObserver.observe(mapContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update map markers when mapped incidents or selection changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersGroup = markersLayerRef.current;
    if (!map || !markersGroup) return;

    markersGroup.clearLayers();

    mappedIncidents.forEach((incident) => {
      const lat = incident.location.latitude!;
      const lng = incident.location.longitude!;
      const isSelected = selectedIncidentId === incident.incident_id;
      const isP0 = incident.priority?.level === 'CRITICAL';
      const isReview = incident.status === 'NEEDS_REVIEW';

      let priorityClass = 'medium';
      if (isReview) priorityClass = 'review';
      else if (incident.priority?.level === 'CRITICAL') priorityClass = 'critical';
      else if (incident.priority?.level === 'HIGH') priorityClass = 'high';
      else if (incident.priority?.level === 'LOW') priorityClass = 'low';

      const score = Math.round(incident.priority?.score ?? 0);
      const levelShort = isReview ? 'REV' : (incident.priority?.level ? incident.priority.level.substring(0, 2) : 'P?');

      const iconHtml = `
        <div class="tactical-marker-root ${isSelected ? 'marker-selected' : ''} marker-prio-${priorityClass}">
          ${isSelected ? '<div class="marker-radar-ping"></div>' : ''}
          ${isP0 ? '<div class="marker-beacon-pulse"></div>' : ''}
          <div class="marker-badge-box">
            <span class="marker-badge-lvl">${levelShort}</span>
            <span class="marker-badge-score">${score}</span>
          </div>
          <div class="marker-label-tag">
            <span>${incident.incident_id}</span>
          </div>
        </div>
      `;

      const customIcon = L.divIcon({
        className: 'tactical-div-icon',
        html: iconHtml,
        iconSize: [44, 44],
        iconAnchor: [22, 22],
      });

      const marker = L.marker([lat, lng], { icon: customIcon });
      marker.on('click', () => {
        onSelectIncident(incident.incident_id);
      });

      marker.addTo(markersGroup);
    });
  }, [mappedIncidents, selectedIncidentId, onSelectIncident]);

  // Center on selected incident if coordinates are available
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !selectedIncidentId) return;

    const focused = mappedIncidents.find((i) => i.incident_id === selectedIncidentId);
    if (focused && focused.location.latitude != null && focused.location.longitude != null) {
      map.panTo([focused.location.latitude, focused.location.longitude], { animate: true, duration: 0.8 });
    }
  }, [selectedIncidentId, mappedIncidents]);

  const handleResetView = () => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (mappedIncidents.length > 0) {
      const bounds = L.latLngBounds(mappedIncidents.map((i) => [i.location.latitude!, i.location.longitude!]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    } else {
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    }
  };

  const handleZoomIn = () => {
    mapInstanceRef.current?.zoomIn();
  };

  const handleZoomOut = () => {
    mapInstanceRef.current?.zoomOut();
  };

  const selectedIncident = incidents.find((i) => i.incident_id === selectedIncidentId);
  const selectedHasCoords = selectedIncident && selectedIncident.location?.latitude != null && selectedIncident.location?.longitude != null;

  return (
    <div className={`tactical-map-pane ${className}`} role="region" aria-label="Tactical Cartographic Map">
      {/* Map HUD Status Strip */}
      <div className="map-hud-strip">
        <div className="map-hud-left">
          <span className="map-hud-sector">
            <Radar size={15} className="hud-radar-icon" />
            <span>SECTOR: METRO TACTICAL RUNBOOK</span>
          </span>
          <span className="hud-divider">|</span>
          <span className="map-hud-grid">
            {selectedHasCoords 
              ? `FOCUS: ${selectedIncident.location.latitude!.toFixed(4)}° N, ${selectedIncident.location.longitude!.toFixed(4)}° W`
              : 'GRID REF: 40.7505° N, 73.9934° W'}
          </span>
          <span className="hud-divider">|</span>
          <span className="map-hud-sync">
            <span className="radar-sweep-dot"></span>
            RADAR SWEEP: 3.2s SYNC
          </span>
        </div>
        <div className="map-hud-right">
          <span className="map-layer-tag">
            {tileError ? 'LAYER: OFFLINE TACTICAL GRID' : 'LAYER: CARTO DARK GEO'}
          </span>
          <button 
            type="button" 
            className="hud-btn-reset" 
            onClick={handleResetView}
            title="Fit all mapped incidents in view"
          >
            <RotateCcw size={11} style={{ marginRight: 4 }} />
            RESET VIEW
          </button>
        </div>
      </div>

      {/* Main Map Canvas Area */}
      <div className="map-canvas-container">
        <div ref={mapContainerRef} className="leaflet-map-host" />

        {/* Top-Left Tactical Mini-Compass / Coords Lock Widget */}
        <div className="tac-mini-widget" aria-hidden="true">
          <div className="tac-widget-header">
            <span>TACTICAL RADAR</span>
            <span className="tac-widget-freq">2.4 GHz</span>
          </div>
          <div className="tac-widget-crosshair">
            <div className="crosshair-ring r1"></div>
            <div className="crosshair-ring r2"></div>
            <div className="crosshair-line h"></div>
            <div className="crosshair-line v"></div>
            {mappedIncidents.slice(0, 3).map((_, idx) => (
              <span key={idx} className={`crosshair-blip blip-${idx}`} />
            ))}
          </div>
          <div className="tac-widget-count">
            {mappedIncidents.length} PINS COORD-LOCKED
          </div>
        </div>

        {/* Top-Right Zoom Controls */}
        <div className="map-zoom-dock">
          <button 
            type="button" 
            className="zoom-btn" 
            onClick={handleZoomIn} 
            title="Zoom In"
            aria-label="Zoom In"
          >
            +
          </button>
          <span className="zoom-readout">{Math.round(currentZoom * 8)}%</span>
          <button 
            type="button" 
            className="zoom-btn" 
            onClick={handleZoomOut} 
            title="Zoom Out"
            aria-label="Zoom Out"
          >
            -
          </button>
        </div>

        {/* Bottom-Left: Strict Location Safety Drawer (Unmapped Incidents) */}
        <div className={`unmapped-drawer ${isUnmappedDrawerOpen ? 'open' : 'collapsed'}`}>
          <div 
            className="unmapped-drawer-header" 
            onClick={() => setIsUnmappedDrawerOpen(!isUnmappedDrawerOpen)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setIsUnmappedDrawerOpen(!isUnmappedDrawerOpen);
              }
            }}
            aria-expanded={isUnmappedDrawerOpen}
            aria-label="Toggle unmapped incidents drawer"
          >
            <div className="unmapped-header-title">
              <AlertTriangle size={13} color="var(--color-p0-critical)" />
              <span>UNMAPPED REPORTS (CANNOT PLOT COORDS)</span>
            </div>
            <div className="unmapped-header-ctrl">
              <span className="unmapped-held-pill">{unmappedIncidents.length} HELD</span>
              {isUnmappedDrawerOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
            </div>
          </div>

          {isUnmappedDrawerOpen && (
            <div className="unmapped-drawer-body">
              {unmappedIncidents.length === 0 ? (
                <div className="unmapped-empty-note">
                  0 HELD // ALL DETECTED HAZARDS HAVE VERIFIED GPS COORDINATES
                </div>
              ) : (
                <div className="unmapped-items-list">
                  {unmappedIncidents.map((incident) => {
                    const isSelected = selectedIncidentId === incident.incident_id;
                    const precision = incident.location?.precision || 'unknown';
                    return (
                      <div
                        key={incident.incident_id}
                        className={`unmapped-item-row ${isSelected ? 'selected' : ''}`}
                        onClick={() => onSelectIncident(incident.incident_id)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            onSelectIncident(incident.incident_id);
                          }
                        }}
                      >
                        <div className="unmapped-item-text">
                          <span className="unmapped-tag">
                            {precision === 'approximate' ? '[APPROX]' : '[NO GPS]'}
                          </span>
                          <span className="unmapped-name">
                            {incident.location?.text || incident.incident_type?.replace(/_/g, ' ') || 'Unverified Location'}
                          </span>
                        </div>
                        <span className="unmapped-id">{incident.incident_id}</span>
                      </div>
                    );
                  })}
                </div>
              )}
              <div className="unmapped-safety-notice">
                <span>RULE: GPS PIN REQUIRED PRIOR TO TAC ROUTE</span>
              </div>
            </div>
          )}
        </div>

        {/* Bottom-Right Tactical Map Legend */}
        <div className="map-legend-dock" aria-label="Map Legend">
          <div className="legend-item">
            <span className="legend-swatch prio-p0"></span>
            <span>P0 CRIT</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch prio-p1"></span>
            <span>P1 HIGH</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch prio-p2"></span>
            <span>P2 MED</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch prio-review"></span>
            <span>NEEDS REVIEW</span>
          </div>
        </div>
      </div>

      {/* Map Sub-Bar: Live Operational Telemetry Readout */}
      <div className="map-telemetry-bar">
        <div className="map-telemetry-left">
          <span className="telemetry-synthesis-label">
            <span className="telemetry-pulse-dot"></span>
            INCIDENT SYNTHESIS:
          </span>
          <span className="telemetry-synthesis-val">
            {incidents.length} TOTAL IN QUEUE // {mappedIncidents.length} GEO-LOCKED // {unmappedIncidents.length} UNMAPPED
          </span>
          <span className="hud-divider">/</span>
          <span className="telemetry-ws-val">
            WS: {wsStatus}
          </span>
        </div>
        <div className="map-telemetry-right">
          <span>SAFEGUARD: STRICT LOCATION HONESTY</span>
          <span className="telemetry-ok-tag">[ACTIVE]</span>
        </div>
      </div>
    </div>
  );
};

export default TacticalMap;
