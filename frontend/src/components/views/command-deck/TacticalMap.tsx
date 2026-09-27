import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import L from 'leaflet';
import { 
  AlertTriangle, 
  RotateCcw, 
  ChevronDown, 
  ChevronUp,
  Send,
  X,
  Radio,
  CheckCircle2,
  Activity,
  PlusCircle
} from 'lucide-react';
import { Incident, ReportSource } from '../../../types/incident';
import { useNavigation } from '../../../context/NavigationContext';
import { submitReport } from '../../../api/reports';
import { 
  DEFAULT_MAP_CENTER, 
  DEFAULT_MAP_ZOOM, 
  TACTICAL_BASE_TILE_URL, 
  TACTICAL_REFERENCE_TILE_URL,
  TACTICAL_TILE_OPTIONS,
  TACTICAL_LABEL_OPTIONS
} from './mapStyles';
import { TacticalRadarWidget } from './TacticalRadarWidget';
import './TacticalMap.css';

export interface TacticalMapProps {
  incidents: Incident[];
  selectedIncidentId: string | null;
  onSelectIncident: (incidentId: string) => void;
  onRefreshIncidents?: () => void;
  className?: string;
}

export const TacticalMap: React.FC<TacticalMapProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
  onRefreshIncidents,
  className = '',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const [isUnmappedDrawerOpen, setIsUnmappedDrawerOpen] = useState(false);
  const [isNavDrawerOpen, setIsNavDrawerOpen] = useState(false);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [isActivityModalOpen, setIsActivityModalOpen] = useState(false);

  // Report Sighting Form State
  const [reportText, setReportText] = useState('');
  const [reportLocation, setReportLocation] = useState('');
  const [reportSource, setReportSource] = useState<ReportSource>('manual');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const [currentZoom, setCurrentZoom] = useState(DEFAULT_MAP_ZOOM);
  const [mapCenter, setMapCenter] = useState(DEFAULT_MAP_CENTER);
  const [tacticalToast, setTacticalToast] = useState<string | null>(null);
  const toastTimeoutRef = useRef<number | null>(null);
  
  const { setActiveView, navigateToIncident } = useNavigation();

  const triggerToast = useCallback((msg: string) => {
    if (toastTimeoutRef.current) {
      window.clearTimeout(toastTimeoutRef.current);
    }
    setTacticalToast(msg);
    toastTimeoutRef.current = window.setTimeout(() => {
      setTacticalToast(null);
    }, 2600);
  }, []);

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

      // Esri Dark Gray Base geometry layer
      const baseLayer = L.tileLayer(TACTICAL_BASE_TILE_URL, TACTICAL_TILE_OPTIONS);
      baseLayer.addTo(map);

      // Esri Dark Gray Reference labels layer
      const labelsLayer = L.tileLayer(TACTICAL_REFERENCE_TILE_URL, TACTICAL_LABEL_OPTIONS);
      labelsLayer.addTo(map);

      const circlesGroup = L.layerGroup().addTo(map);
      const markersGroup = L.layerGroup().addTo(map);
      leafletCirclesGroupRef.current = circlesGroup;
      leafletMarkersGroupRef.current = markersGroup;
      leafletMapRef.current = map;

      map.on('zoomend', () => {
        setCurrentZoom(map.getZoom());
      });

      map.on('moveend', () => {
        const center = map.getCenter();
        setMapCenter({ lat: center.lat, lng: center.lng });
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

      // Determine icon type matching Spider-Man tracker reference
      const isHigh = incident.priority?.level === 'HIGH';
      let badgeType = 'spidey-green';
      let iconInnerSvg = `
        <svg viewBox="0 0 24 24" width="19" height="19" fill="#061a10">
          <circle cx="12" cy="7.5" r="2.2" />
          <ellipse cx="12" cy="13.5" rx="3.4" ry="4.5" />
          <path d="M10 7.5 C6.5 4.5 4 4 3 6.5 M9.5 9.5 C5.5 8 3.5 9.5 2.5 12.5 M9.5 11.5 C5.5 12.5 3.5 15 3 18.5 M10 13.5 C6.5 16.5 5.5 19 5.5 22" fill="none" stroke="#061a10" stroke-width="1.6" stroke-linecap="round" />
          <path d="M14 7.5 C17.5 4.5 20 4 21 6.5 M14.5 9.5 C18.5 8 20.5 9.5 21.5 12.5 M14.5 11.5 C18.5 12.5 20.5 15 21 18.5 M14 13.5 C17.5 16.5 18.5 19 18.5 22" fill="none" stroke="#061a10" stroke-width="1.6" stroke-linecap="round" />
        </svg>
      `;

      if (isReview) {
        badgeType = 'spidey-star';
        iconInnerSvg = `
          <svg viewBox="0 0 24 24" width="17" height="17" fill="#ffffff">
            <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
          </svg>
        `;
      } else if (isP0 || isHigh) {
        badgeType = 'spidey-red';
        iconInnerSvg = `
          <svg viewBox="0 0 24 24" width="19" height="19" fill="#1f0606">
            <circle cx="12" cy="7.5" r="2.2" />
            <ellipse cx="12" cy="13.5" rx="3.4" ry="4.5" />
            <path d="M10 7.5 C6.5 4.5 4 4 3 6.5 M9.5 9.5 C5.5 8 3.5 9.5 2.5 12.5 M9.5 11.5 C5.5 12.5 3.5 15 3 18.5 M10 13.5 C6.5 16.5 5.5 19 5.5 22" fill="none" stroke="#1f0606" stroke-width="1.6" stroke-linecap="round" />
            <path d="M14 7.5 C17.5 4.5 20 4 21 6.5 M14.5 9.5 C18.5 8 20.5 9.5 21.5 12.5 M14.5 11.5 C18.5 12.5 20.5 15 21 18.5 M14 13.5 C17.5 16.5 18.5 19 18.5 22" fill="none" stroke="#1f0606" stroke-width="1.6" stroke-linecap="round" />
          </svg>
        `;
      }

      const hoverTitle = `${incident.incident_type?.replace(/_/g, ' ') || 'Incident'} (${incident.priority?.level || 'PRIO'}): ${incident.location?.text || 'Location'}`;

      // Spidey tactical badge marker directly matching Reference Image 3
      const iconHtml = `
        <div class="spidey-marker-badge ${badgeType} ${isSelected ? 'selected' : ''}" title="${hoverTitle}">
          ${isSelected ? '<div class="spidey-marker-halo"></div>' : ''}
          ${isP0 ? '<div class="spidey-marker-pulse"></div>' : ''}
          <div class="spidey-badge-disc">
            ${iconInnerSvg}
          </div>
        </div>
      `;

      const customIcon = L.divIcon({
        className: 'spidey-div-icon',
        html: iconHtml,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
        popupAnchor: [0, -17],
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
    triggerToast('view reset to all active incidents');
  }, [mappedIncidents, triggerToast]);

  const handleZoomIn = () => {
    leafletMapRef.current?.zoomIn();
  };

  const handleZoomOut = () => {
    leafletMapRef.current?.zoomOut();
  };

  const selectedIncident = incidents.find((i) => i.incident_id === selectedIncidentId);

  const handleGlobalView = useCallback(() => {
    const map = leafletMapRef.current;
    if (!map) return;
    map.setView([20, 0], 2, { animate: true });
    triggerToast('centering to global view');
  }, [triggerToast]);

  const handleCenterView = useCallback(() => {
    const map = leafletMapRef.current;
    if (!map) return;
    if (selectedIncident && selectedIncident.location?.latitude != null && selectedIncident.location?.longitude != null) {
      map.setView([selectedIncident.location.latitude, selectedIncident.location.longitude], 14, { animate: true });
      triggerToast('centering to incident location');
    } else {
      map.setView([DEFAULT_MAP_CENTER.lat, DEFAULT_MAP_CENTER.lng], DEFAULT_MAP_ZOOM, { animate: true });
      triggerToast('centering to headquarters');
    }
  }, [selectedIncident, triggerToast]);

  // Handle report submission
  const handleSubmitReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reportText.trim()) return;

    try {
      setIsSubmitting(true);
      await submitReport({
        text: reportText.trim(),
        source: reportSource,
        is_synthetic: false,
        reported_at: new Date().toISOString(),
        location_hint: reportLocation.trim() ? { raw_text: reportLocation.trim() } : undefined,
      });

      setSubmitSuccess(true);
      triggerToast('Sighting ingested into triage engine');
      setTimeout(() => {
        setSubmitSuccess(false);
        setIsReportModalOpen(false);
        setReportText('');
        setReportLocation('');
        onRefreshIncidents?.();
      }, 1200);
    } catch (err) {
      triggerToast('Error dispatching report');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={`tactical-map-pane ${className}`} role="region" aria-label="Tactical Cartographic Map">
      {/* Main Map Viewport with Tactical HUD Bezel */}
      <div className="map-canvas-container">
        {/* The Host Container for Leaflet */}
        <div ref={mapContainerRef} className="tactical-map-host" />

        {/* Tactical Coordinate Grid Overlay (Latitude & Longitude Gridlines inspired by reference) */}
        <div className="tactical-grid-overlay" aria-hidden="true">
          <div className="grid-lat-line lat-1"><span className="grid-coord-label">28° 38' N</span></div>
          <div className="grid-lat-line lat-2"><span className="grid-coord-label">20° 35' N</span></div>
          <div className="grid-lat-line lat-3"><span className="grid-coord-label">12° 58' N</span></div>
          <div className="grid-lng-line lng-1"><span className="grid-coord-label-v">72° 50' E</span></div>
          <div className="grid-lng-line lng-2"><span className="grid-coord-label-v">78° 57' E</span></div>
          <div className="grid-lng-line lng-3"><span className="grid-coord-label-v">85° 10' E</span></div>

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

        {/* Circular Menu Toggle Button (Reference Image 2) */}
        <button
          type="button"
          className={`spider-menu-toggle-btn ${isNavDrawerOpen ? 'active' : ''}`}
          onClick={() => setIsNavDrawerOpen(!isNavDrawerOpen)}
          title={isNavDrawerOpen ? 'Close Menu' : 'Open Tactical Menu'}
          aria-expanded={isNavDrawerOpen}
          aria-label="Toggle tactical navigation drawer"
        >
          {isNavDrawerOpen ? (
            <div className="spider-menu-icon close-icon">
              <span className="close-bar bar-1" />
              <span className="close-bar bar-2" />
            </div>
          ) : (
            <div className="spider-menu-icon hamburger-icon">
              <span className="burger-bar" />
              <span className="burger-bar" />
              <span className="burger-bar" />
            </div>
          )}
        </button>

        {/* Slide-Out Navigation Drawer Navbar (Reference Image 3) */}
        <div className={`spider-slide-drawer ${isNavDrawerOpen ? 'open' : ''}`} aria-hidden={!isNavDrawerOpen}>
          <div className="drawer-header">
            <button
              type="button"
              className="drawer-close-circle-btn"
              onClick={() => setIsNavDrawerOpen(false)}
              title="Close Menu"
              aria-label="Close Menu"
            >
              <div className="spider-menu-icon close-icon">
                <span className="close-bar bar-1" />
                <span className="close-bar bar-2" />
              </div>
            </button>
            <span className="drawer-header-title">TACTICAL OPS</span>
          </div>

          <nav className="drawer-nav-list" aria-label="Tactical Navigation Drawer">
            <button
              type="button"
              className="drawer-nav-item"
              onClick={() => {
                setIsNavDrawerOpen(false);
                setIsActivityModalOpen(true);
              }}
            >
              <span>ACTIVITY LOG</span>
            </button>
            <div className="drawer-divider-dotted" />

            <button
              type="button"
              className="drawer-nav-item"
              onClick={() => {
                setIsNavDrawerOpen(false);
                setIsReportModalOpen(true);
              }}
            >
              <span>REPORT SIGHTINGS</span>
            </button>
            <div className="drawer-divider-dotted" />

            <button
              type="button"
              className="drawer-nav-item"
              onClick={() => {
                setIsNavDrawerOpen(false);
                setActiveView('incident-streams');
              }}
            >
              <span>LIVE STREAMS</span>
            </button>
            <div className="drawer-divider-dotted" />

            <button
              type="button"
              className="drawer-nav-item"
              onClick={() => {
                setIsNavDrawerOpen(false);
                if (selectedIncidentId) {
                  navigateToIncident(selectedIncidentId);
                } else {
                  setActiveView('investigation');
                }
              }}
            >
              <span>INVESTIGATION & EVIDENCE</span>
            </button>
            <div className="drawer-divider-dotted" />

            <button
              type="button"
              className="drawer-nav-item"
              onClick={() => {
                setIsNavDrawerOpen(false);
                setActiveView('audit-trail');
              }}
            >
              <span>AUDIT LEDGER</span>
            </button>
            <div className="drawer-divider-dotted" />

            <button
              type="button"
              className="drawer-nav-item"
              onClick={() => {
                setIsNavDrawerOpen(false);
                setActiveView('briefing');
              }}
            >
              <span>SYSTEM BRIEFING</span>
            </button>
            <div className="drawer-divider-dotted" />

            <button
              type="button"
              className="drawer-nav-item drawer-nav-action"
              onClick={() => {
                setIsNavDrawerOpen(false);
                handleResetView();
              }}
            >
              <span>RESET MAP VIEW</span>
            </button>
          </nav>
        </div>

        {/* Drawer Backdrop Overlay */}
        {isNavDrawerOpen && (
          <div 
            className="spider-drawer-backdrop" 
            onClick={() => setIsNavDrawerOpen(false)}
            aria-hidden="true"
          />
        )}

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
          <button
            type="button"
            className="zoom-btn zoom-btn-reset"
            onClick={handleResetView}
            title="Reset map view (fit all incidents)"
            aria-label="Reset map view"
          >
            <RotateCcw size={12} />
          </button>
        </div>

        {/* Bottom-Right Tactical Spiderweb Radar Widget (Reference Design with Real Telemetry) */}
        <TacticalRadarWidget
          incidents={incidents}
          selectedIncidentId={selectedIncidentId}
          mapCenter={mapCenter}
          onSelectIncident={onSelectIncident}
          onGlobalView={handleGlobalView}
          onCenterView={handleCenterView}
        />

        {/* Tactical Centering Toast Capsule */}
        {tacticalToast && (
          <div className="tactical-hud-toast" role="status" aria-live="polite">
            <span className="toast-text">{tacticalToast}</span>
          </div>
        )}

        {/* Bottom-Left: Strict Location Honesty Drawer (Only shown when unmapped incidents exist) */}
        {unmappedIncidents.length > 0 && (
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
                        <span className="unmapped-id">#{incident.incident_id.substring(4, 12)}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="unmapped-safety-notice">
                  <span>LOCATION HONESTY: NO FAKE MAP PINS</span>
                </div>
              </div>
            )}
          </div>
        )}

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

      {/* REPORT SIGHTINGS MODAL */}
      {isReportModalOpen && (
        <div className="tactical-modal-backdrop" onClick={() => setIsReportModalOpen(false)}>
          <div 
            className="tactical-modal-card" 
            onClick={(e) => e.stopPropagation()} 
            role="dialog" 
            aria-label="Report Sighting"
          >
            <div className="tactical-modal-header">
              <div className="modal-title-wrap">
                <PlusCircle size={16} color="var(--color-dispatch-yellow)" />
                <span className="modal-title">REPORT SIGHTING // DISPATCH</span>
              </div>
              <button 
                type="button" 
                className="modal-close-btn" 
                onClick={() => setIsReportModalOpen(false)}
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            {submitSuccess ? (
              <div className="modal-success-banner">
                <CheckCircle2 size={24} color="var(--color-system-green)" />
                <span>Sighting dispatched to triage pipeline successfully.</span>
              </div>
            ) : (
              <form onSubmit={handleSubmitReport} className="modal-form">
                <div className="modal-field">
                  <label className="modal-label">INCIDENT SIGHTING DESCRIPTION *</label>
                  <textarea
                    className="modal-textarea"
                    placeholder="Describe observed hazard (e.g. Structure collapsed near market square, citizens calling for help)..."
                    value={reportText}
                    onChange={(e) => setReportText(e.target.value)}
                    required
                    rows={3}
                  />
                </div>

                <div className="modal-field">
                  <label className="modal-label">LOCATION ESTIMATE</label>
                  <input
                    type="text"
                    className="modal-input"
                    placeholder="e.g. Rasulgarh underpass, Bhubaneswar"
                    value={reportLocation}
                    onChange={(e) => setReportLocation(e.target.value)}
                  />
                </div>

                <div className="modal-field">
                  <label className="modal-label">SOURCE CHANNEL</label>
                  <select
                    className="modal-select"
                    value={reportSource}
                    onChange={(e) => setReportSource(e.target.value as ReportSource)}
                  >
                    <option value="manual">EYEWITNESS / FIELD DISPATCH</option>
                    <option value="simulator">INCIDENT SIMULATOR</option>
                    <option value="other">RADAR & REMOTE SENSOR</option>
                  </select>
                </div>

                <div className="modal-actions">
                  <button 
                    type="button" 
                    className="modal-btn-cancel" 
                    onClick={() => setIsReportModalOpen(false)}
                  >
                    CANCEL
                  </button>
                  <button 
                    type="submit" 
                    className="modal-btn-submit" 
                    disabled={isSubmitting || !reportText.trim()}
                  >
                    {isSubmitting ? (
                      <>
                        <Radio size={14} className="rotating" />
                        <span>DISPATCHING...</span>
                      </>
                    ) : (
                      <>
                        <Send size={14} />
                        <span>DISPATCH REPORT</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ACTIVITY LOG & TRIAGE BREAKDOWN MODAL */}
      {isActivityModalOpen && (
        <div className="tactical-modal-backdrop" onClick={() => setIsActivityModalOpen(false)}>
          <div 
            className="tactical-modal-card activity-log-card" 
            onClick={(e) => e.stopPropagation()} 
            role="dialog" 
            aria-label="Activity Log"
          >
            <div className="tactical-modal-header">
              <div className="modal-title-wrap">
                <Activity size={16} color="var(--color-multiverse-cyan)" />
                <span className="modal-title">OPERATIONAL ACTIVITY LOG</span>
              </div>
              <button 
                type="button" 
                className="modal-close-btn" 
                onClick={() => setIsActivityModalOpen(false)}
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            <div className="activity-modal-body">
              {selectedIncident ? (
                <div className="activity-incident-detail">
                  <div className="detail-header-tape">
                    <span className="detail-id">{selectedIncident.incident_id}</span>
                    <span className="detail-prio">{selectedIncident.priority?.level || 'PRIORITY'} ({Math.round(selectedIncident.priority?.score ?? 0)} PTS)</span>
                  </div>

                  <h3 className="detail-headline">
                    {selectedIncident.incident_type?.replace(/_/g, ' ') || 'UNCLASSIFIED HAZARD'}
                  </h3>

                  <div className="triage-factors-grid">
                    <div className="factor-box">
                      <span className="factor-label">URGENCY FACTOR</span>
                      <span className="factor-val">{selectedIncident.priority?.level === 'CRITICAL' ? 'LIFE SAFETY (+35)' : 'TACTICAL MONITOR'}</span>
                    </div>
                    <div className="factor-box">
                      <span className="factor-label">CORROBORATION</span>
                      <span className="factor-val">{selectedIncident.corroboration?.report_count ?? 1} DISPATCHES</span>
                    </div>
                    <div className="factor-box">
                      <span className="factor-label">PEOPLE AT RISK</span>
                      <span className="factor-val">{selectedIncident.people_at_risk?.count != null ? `~${selectedIncident.people_at_risk.count} CIVILIANS` : 'UNASSESSED'}</span>
                    </div>
                    <div className="factor-box">
                      <span className="factor-label">STATUS</span>
                      <span className="factor-val tel-cyan">{selectedIncident.status}</span>
                    </div>
                  </div>

                  <div className="activity-explanation-box">
                    <span className="explanation-label">TRIAGE SYNTHESIS:</span>
                    <p className="explanation-text">
                      {selectedIncident.priority?.explanation || 'Incident prioritized according to multi-source risk weights and emergency responder protocols.'}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="activity-empty-state">
                  Select an incident to view deep triage breakdown and audit history.
                </div>
              )}
            </div>

            <div className="modal-actions">
              <button 
                type="button" 
                className="modal-btn-submit" 
                onClick={() => setIsActivityModalOpen(false)}
              >
                CLOSE
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TacticalMap;
