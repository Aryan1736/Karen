/**
 * TINGLE Tactical Map — Visual Styles & Color System
 * 
 * Inspired by the Spidey Tracker Reference:
 * - Deep navy/black water (#050d18 / #061224)
 * - Muted dark blue geographic land areas (#0c253d / #0d2840)
 * - Cyan/electric blue accents (#00f0ff)
 * - Coordinate grid / HUD framing
 */

export const DEFAULT_MAP_CENTER = {
  lat: 40.7505,
  lng: -73.9934,
};

export const DEFAULT_MAP_ZOOM = 13;

/**
 * Custom Google Maps JavaScript API styling array
 * Meticulously matching the Spidey Tracker reference image
 */
export const TACTICAL_DARK_GOOGLE_MAPS_STYLE = [
  {
    elementType: "geometry",
    stylers: [{ color: "#061325" }]
  },
  {
    elementType: "labels.text.stroke",
    stylers: [{ color: "#050e1b" }, { weight: 3 }]
  },
  {
    elementType: "labels.text.fill",
    stylers: [{ color: "#4f7b9e" }]
  },
  {
    featureType: "administrative",
    elementType: "geometry.stroke",
    stylers: [{ color: "#143a59" }, { weight: 1 }]
  },
  {
    featureType: "administrative.country",
    elementType: "geometry.stroke",
    stylers: [{ color: "#1a4a70" }, { weight: 1.2 }]
  },
  {
    featureType: "administrative.country",
    elementType: "labels.text.fill",
    stylers: [{ color: "#6ba2c9" }]
  },
  {
    featureType: "administrative.locality",
    elementType: "labels.text.fill",
    stylers: [{ color: "#00f0ff" }]
  },
  {
    featureType: "landscape",
    elementType: "geometry",
    stylers: [{ color: "#0c253d" }]
  },
  {
    featureType: "landscape.man_made",
    elementType: "geometry",
    stylers: [{ color: "#0e2942" }]
  },
  {
    featureType: "landscape.natural",
    elementType: "geometry",
    stylers: [{ color: "#0b2238" }]
  },
  {
    featureType: "poi",
    elementType: "geometry",
    stylers: [{ color: "#0e2d48" }]
  },
  {
    featureType: "poi",
    elementType: "labels",
    stylers: [{ visibility: "off" }]
  },
  {
    featureType: "road",
    elementType: "geometry",
    stylers: [{ color: "#113350" }]
  },
  {
    featureType: "road",
    elementType: "geometry.stroke",
    stylers: [{ color: "#061325" }, { weight: 0.5 }]
  },
  {
    featureType: "road",
    elementType: "labels.text.fill",
    stylers: [{ color: "#457599" }]
  },
  {
    featureType: "road.highway",
    elementType: "geometry",
    stylers: [{ color: "#17456d" }]
  },
  {
    featureType: "road.highway",
    elementType: "labels.text.fill",
    stylers: [{ color: "#6ba2c9" }]
  },
  {
    featureType: "transit",
    elementType: "geometry",
    stylers: [{ color: "#0f2f4c" }]
  },
  {
    featureType: "transit.station",
    elementType: "labels.text.fill",
    stylers: [{ color: "#00e5ff" }]
  },
  {
    featureType: "water",
    elementType: "geometry",
    stylers: [{ color: "#050d18" }]
  },
  {
    featureType: "water",
    elementType: "labels.text.fill",
    stylers: [{ color: "#2d5e82" }]
  }
];

let googleMapsScriptPromise: Promise<boolean> | null = null;

/**
 * Dynamically loads Google Maps JavaScript API without exposing the key in code.
 * Reuses active promise to avoid duplicate injections.
 */
export function loadGoogleMapsScript(apiKey: string): Promise<boolean> {
  if (typeof window === 'undefined') return Promise.resolve(false);
  
  if ((window as any).google?.maps) {
    return Promise.resolve(true);
  }

  if (googleMapsScriptPromise) {
    return googleMapsScriptPromise;
  }

  if (!apiKey || apiKey.trim() === '') {
    return Promise.resolve(false);
  }

  googleMapsScriptPromise = new Promise((resolve) => {
    const existingScript = document.getElementById('google-maps-api-script');
    if (existingScript) {
      if ((window as any).google?.maps) {
        resolve(true);
      } else {
        existingScript.addEventListener('load', () => resolve(true));
        existingScript.addEventListener('error', () => resolve(false));
      }
      return;
    }

    const script = document.createElement('script');
    script.id = 'google-maps-api-script';
    script.type = 'text/javascript';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=geometry`;
    script.async = true;
    script.defer = true;

    script.onload = () => {
      resolve(true);
    };

    script.onerror = () => {
      console.warn('[TacticalMap] Failed to load Google Maps script. Falling back to Leaflet.');
      resolve(false);
    };

    document.head.appendChild(script);
  });

  return googleMapsScriptPromise;
}
