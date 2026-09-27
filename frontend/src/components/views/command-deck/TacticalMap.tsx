import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import L from 'leaflet';
import { 
  Radar, 
  AlertTriangle, 
  RotateCcw, 
  ChevronDown, 
  ChevronUp,
  Layers,
  Compass
} from 'lucide-react';
import { Incident } from '../../../types/incident';
import { useWebSocketStatus } from '../../../context/WebSocketContext';
import { 
  DEFAULT_MAP_CENTER, 
  DEFAULT_MAP_ZOOM, 
  TACTICAL_TILE_URL, 
  TACTICAL_TILE_OPTIONS 
} from './mapStyles';
import './TacticalMap.css';

export interface TacticalMapProps {
  incidents: Incident[];
  selectedIncidentId: string | null;
  onSelectIncident: (incidentId: string) => void;
  className?: string;
}

export const TacticalMap: React.FC<TacticalMapProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
  className = '',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const [isUnmappedDrawerOpen, setIsUnmappedDrawerOpen] = useState(false);
  const [currentZoom, setCurrentZoom] = useState(DEFAULT_MAP_ZOOM);
  const { status: wsStatus } = useWebSocketStatus();

  // Leaflet instance and layer group refs
  const leafletMapRef = useRef<L.Map | null>(null);
  const leafletMarkersGroupRef = useRef<L.LayerGroup | null>(null);
  const leafletCirclesGroupRef = useRef<L.LayerGroup | null>(null);

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

  // =========================================================================
  // LEAFLET MAP INITIALIZATION & TEARDOWN
  // =========================================================================
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!leafletMapRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [DEFAULT_MAP_CENTER.lat, DEFAULT_MAP_CENTER.lng],
        zoom: DEFAULT_MAP_ZOOM,
        zoomControl: false,
        attributionControl: false,
      });

      // CartoDB Dark Matter tile layer with tactical navy chromatic styling
      const tileLayer = L.tileLayer(TACTICAL_TILE_URL, TACTICAL_TILE_OPTIONS);
      tileLayer.addTo(map);

      const circlesGroup = L.layerGroup().addTo(map);
      const markersGroup = L.layerGroup().addTo(map);
      leafletCirclesGroupRef.current = circlesGroup;
      leafletMarkersGroupRef.current = markersGroup;
      leafletMapRef.current = map;

      map.on('zoomend', () => {
        setCurrentZoom(map.getZoom());
      });

      const resizeObserver = new ResizeObserver(() => {
        map.invalidateSize();
      });
      resizeObserver.observe(mapContainerRef.current);

      return () => {
        resizeObserver.disconnect();
        map.remove();
        leafletMapRef.current = null;
        leafletMarkersGroupRef.current = null;
        leafletCirclesGroupRef.current = null;
      };
    }
  }, []);

  // =========================================================================
  // UPDATE TACTICAL MARKERS & APPROXIMATE RADIUS CIRCLES
  // =========================================================================
  useEffect(() => {
    const map = leafletMapRef.current;
    const markersGroup = leafletMarkersGroupRef.current;
    const circlesGroup = leafletCirclesGroupRef.current;
    if (!map || !markersGroup || !circlesGroup) return;

    markersGroup.clearLayers();
    circlesGroup.clearLayers();

    mappedIncidents.forEach((incident) => {
      const lat = incident.location.latitude!;
      const lng = incident.location.longitude!;
      const isSelected = selectedIncidentId === incident.incident_id;
      const isP0 = incident.priority?.level === 'CRITICAL';
      const isReview = incident.status === 'NEEDS_REVIEW';
      const isApprox = incident.location?.precision === 'approximate';

      let priorityClass = 'medium';
      if (isReview) priorityClass = 'review';
      else if (incident.priority?.level === 'CRITICAL') priorityClass = 'critical';
      else if (incident.priority?.level === 'HIGH') priorityClass = 'high';
      else if (incident.priority?.level === 'LOW') priorityClass = 'low';

      const score = Math.round(incident.priority?.score ?? 0);
      const levelShort = isReview ? 'REV' : (incident.priority?.level ? incident.priority.level.substring(0, 2) : 'P?');

      // If location is approximate, draw dashed uncertainty zone
      if (isApprox) {
        const circle = L.circle([lat, lng], {
          radius: 450,
          color: isP0 ? '#FF2B4A' : isSelected ? '#00F0FF' : '#FF5C00',
          weight: 1.5,
          dashArray: '4, 6',
          fillColor: isP0 ? '#FF2B4A' : '#00F0FF',
          fillOpacity: isSelected ? 0.16 : 0.08,
          interactive: false,
        });
        circle.addTo(circlesGroup);
      }

      // Tactical incident marker inspired by the reference design
      const iconHtml = `
        <div class="tactical-marker-root ${isSelected ? 'marker-selected' : ''} marker-prio-${priorityClass}">
          ${isSelected ? '<div class="marker-star-halo"></div><div class="marker-radar-ping"></div>' : ''}
          ${isP0 ? '<div class="marker-beacon-pulse"></div>' : ''}
          <div class="marker-badge-box">
            <span class="marker-badge-lvl">${levelShort}</span>
            <span class="marker-badge-score">${score}</span>
          </div>
          <div class="marker-label-tag">
            <span>${incident.incident_id}</span>
            ${isApprox ? '<span class="marker-approx-pip">[APPROX]</span>' : ''}
          </div>
        </div>
      `;

      const customIcon = L.divIcon({
        className: 'tactical-div-icon',
        html: iconHtml,
        iconSize: [48, 48],
        iconAnchor: [24, 24],
      });

      const marker = L.marker([lat, lng], { icon: customIcon });
      marker.on('click', () => {
        onSelectIncident(incident.incident_id);
      });

      marker.addTo(markersGroup);
    });
  }, [mappedIncidents, selectedIncidentId, onSelectIncident]);

  // =========================================================================
  // CENTER ON SELECTED INCIDENT
  // =========================================================================
  useEffect(() => {
    const map = leafletMapRef.current;
    if (!map || !selectedIncidentId) return;

    const focused = mappedIncidents.find((i) => i.incident_id === selectedIncidentId);
    if (focused && focused.location.latitude != null && focused.location.longitude != null) {
      map.panTo([focused.location.latitude, focused.location.longitude], { animate: true, duration: 0.6 });
    }
  }, [selectedIncidentId, mappedIncidents]);

  // =========================================================================
  // VIEWPORT CONTROLS
  // =========================================================================
  const handleResetView = useCallback(() => {
    const map = leafletMapRef.current;
    if (!map) return;

    if (mappedIncidents.length > 1) {
      const bounds = L.latLngBounds(mappedIncidents.map((i) => [i.location.latitude!, i.location.longitude!]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    } else if (mappedIncidents.length === 1) {
      map.setView([mappedIncidents[0].location.latitude!, mappedIncidents[0].location.longitude!], 14, { animate: true });
    } else {
      map.setView([DEFAULT_MAP_CENTER.lat, DEFAULT_MAP_CENTER.lng], DEFAULT_MAP_ZOOM, { animate: true });
    }
  }, [mappedIncidents]);

  const handleZoomIn = () => {
    leafletMapRef.current?.zoomIn();
  };

  const handleZoomOut = () => {
    leafletMapRef.current?.zoomOut();
  };

  const selectedIncident = incidents.find((i) => i.incident_id === selectedIncidentId);
  const selectedHasCoords = selectedIncident && selectedIncident.location?.latitude != null && selectedIncident.location?.longitude != null;

  return (
    <div className={`tactical-map-pane ${className}`} role="region" aria-label="Tactical Cartographic Map">
      {/* Top Tactical HUD Framing Bar */}
      <div className="map-hud-strip">
        <div className="map-hud-left">
          <div className="map-hud-brand-pill">
            <Radar size={13} className="hud-radar-icon" />
            <span className="brand-pill-text">TINGLE RADAR</span>
          </div>
          <span className="hud-divider">|</span>
          <span className="map-hud-grid">
            {selectedHasCoords 
              ? `FOCUS: ${selectedIncident.location.latitude!.toFixed(4)}° N, ${Math.abs(selectedIncident.location.longitude!).toFixed(4)}° W`
              : `GRID REF: ${DEFAULT_MAP_CENTER.lat.toFixed(4)}° N, ${Math.abs(DEFAULT_MAP_CENTER.lng).toFixed(4)}° W`}
          </span>
          <span className="hud-divider">|</span>
          <span className="map-hud-sync">
            <span className="radar-sweep-dot" />
            LIVE TELEMETRY
          </span>
        </div>

        <div className="map-hud-right">
          <div className="map-layer-tag">
            <Layers size={11} style={{ marginRight: 4 }} />
            ENGINE: LEAFLET TACTICAL
          </div>

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

      {/* Main Map Viewport with Tactical HUD Bezel */}
      <div className="map-canvas-container">
        {/* The Host Container for Leaflet */}
        <div ref={mapContainerRef} className="tactical-map-host" />

        {/* Tactical Coordinate Grid Overlay (Latitude & Longitude Gridlines inspired by reference) */}
        <div className="tactical-grid-overlay" aria-hidden="true">
          <div className="grid-lat-line lat-1"><span className="grid-coord-label">40° 48' N</span></div>
          <div className="grid-lat-line lat-2"><span className="grid-coord-label">40° 45' N</span></div>
          <div className="grid-lat-line lat-3"><span className="grid-coord-label">40° 42' N</span></div>
          <div className="grid-lng-line lng-1"><span className="grid-coord-label-v">74° 02' W</span></div>
          <div className="grid-lng-line lng-2"><span className="grid-coord-label-v">73° 59' W</span></div>
          <div className="grid-lng-line lng-3"><span className="grid-coord-label-v">73° 56' W</span></div>

          {/* Perimeter Coordinate Degree Ticks */}
          <div className="grid-ticks top-ticks" />
          <div className="grid-ticks bottom-ticks" />
          <div className="grid-ticks left-ticks" />
          <div className="grid-ticks right-ticks" />

          {/* Corner Brackets matching Spidey Tracker reference */}
          <div className="hud-corner-bracket top-left" />
          <div className="hud-corner-bracket top-right" />
          <div className="hud-corner-bracket bottom-left" />
          <div className="hud-corner-bracket bottom-right" />
        </div>

        {/* Top-Right Tactical Zoom & Readout Dock */}
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
          <span className="zoom-readout">{Math.round(currentZoom * 7.5)}%</span>
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

        {/* Bottom-Right Tactical Compass & Target Radar Widget (from reference) */}
        <div className="tac-radar-widget" aria-hidden="true">
          <div className="radar-disc">
            <div className="radar-grid-concentric c1" />
            <div className="radar-grid-concentric c2" />
            <div className="radar-grid-concentric c3" />
            <div className="radar-crosshair-h" />
            <div className="radar-crosshair-v" />
            <div className="radar-sweep-beam" />
            <span className="radar-target-dot" />
          </div>
          <div className="radar-meta-row">
            <Compass size={11} className="text-cyan" />
            <span>BEARING: 042° // SECTOR METRO</span>
          </div>
        </div>

        {/* Bottom-Left: Strict Location Honesty Drawer (Unmapped Incidents) */}
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
            aria-label="Toggle unmapped reports drawer"
          >
            <div className="unmapped-header-title">
              <AlertTriangle size={13} color="var(--color-p0-critical)" />
              <span>UNMAPPED REPORTS ({unmappedIncidents.length})</span>
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
                  ALL INCIDENTS HAVE VERIFIED GPS COORDINATES
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
                <span>STRICT POLICY: NO FAKE / HALLUCINATED MAP PINS</span>
              </div>
            </div>
          )}
        </div>

        {/* Bottom-Center Tactical Map Legend */}
        <div className="map-legend-dock" aria-label="Map Legend">
          <div className="legend-item">
            <span className="legend-swatch prio-p0" />
            <span>P0 CRIT</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch prio-p1" />
            <span>P1 HIGH</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch prio-p2" />
            <span>P2 MED</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch prio-p3" />
            <span>P3 LOW</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch prio-review" />
            <span>REVIEW</span>
          </div>
        </div>
      </div>

      {/* Map Sub-Bar: Live Operational Telemetry Readout */}
      <div className="map-telemetry-bar">
        <div className="map-telemetry-left">
          <span className="telemetry-synthesis-label">
            <span className="telemetry-pulse-dot" />
            GRID TELEMETRY:
          </span>
          <span className="telemetry-synthesis-val">
            {incidents.length} TOTAL QUEUE // {mappedIncidents.length} GEO-LOCKED // {unmappedIncidents.length} UNMAPPED
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
