/**
 * TINGLE Tactical Map — Visual Styles & Configuration
 * 
 * Inspired by the Spidey Tracker Reference:
 * - Deep tactical navy/black water (#050d18)
 * - Muted dark blue geographic land areas (#0c253d)
 * - Cyan/electric blue accents (#00f0ff)
 * - Coordinate grid / HUD framing
 * - 100% Free, zero API key, no watermark tile architecture
 */

export const DEFAULT_MAP_CENTER = {
  lat: 20.5937,
  lng: 78.9629,
};

export const DEFAULT_MAP_ZOOM = 5;

/**
 * Esri World Dark Gray Canvas tile layer configuration
 * Completely free, high performance, no API keys, zero watermarks.
 */
export const TACTICAL_BASE_TILE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}';

export const TACTICAL_REFERENCE_TILE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}';

export const TACTICAL_TILE_OPTIONS = {
  maxZoom: 16,
  minZoom: 2,
  className: 'tactical-leaflet-tiles',
  attribution: '&copy; Esri &mdash; Tactical Emergency Basemap',
};

export const TACTICAL_LABEL_OPTIONS = {
  maxZoom: 16,
  minZoom: 2,
  className: 'tactical-leaflet-labels',
  opacity: 0.85,
  interactive: false,
};
