/**
 * TINGLE Tactical Map — Visual Styles & Configuration
 * 
 * Inspired by the Spidey Tracker Reference:
 * - Deep tactical navy/black water (#050d18)
 * - Muted dark blue geographic land areas (#0c253d)
 * - Cyan/electric blue accents (#00f0ff)
 * - Coordinate grid / HUD framing
 * - 100% Leaflet engine (zero API keys, zero external quotas)
 */

export const DEFAULT_MAP_CENTER = {
  lat: 40.7505,
  lng: -73.9934,
};

export const DEFAULT_MAP_ZOOM = 13;

/**
 * CartoDB Dark Matter tile layer configuration
 * High-performance dark tactical basemap tailored for emergency dispatch overlays
 */
export const TACTICAL_TILE_URL = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

export const TACTICAL_TILE_OPTIONS = {
  maxZoom: 19,
  minZoom: 3,
  subdomains: 'abcd',
  className: 'tactical-leaflet-tiles',
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
};
