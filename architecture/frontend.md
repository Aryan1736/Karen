# Karen's Ear — Command Center Frontend Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Command Center Information Architecture

The frontend is a single-page emergency command center designed for rapid situational awareness under extreme cognitive load. It adopts an ultra-crisp, dark-mode tactical aesthetic inspired by modern defense and emergency operations consoles.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔴 KAREN'S EAR | TACTICAL COMMAND CENTER       [● LIVE WS] [SIMULATOR] [OP] │
├───────────────────────────────┬─────────────────────────────────────────────┤
│ PRIORITIZED INCIDENT QUEUE    │ TACTICAL GEOGRAPHIC MAP                     │
│ [All] [Critical] [Review]     │ (Leaflet.js + OpenStreetMap)                │
│                               │                                             │
│ ┌───────────────────────────┐ │      ┌────────┐                             │
│ │ #1 CRITICAL (Score: 88.5) │ │      │ 📍 88.5│ (Pulsing Red Marker)        │
│ │ Flash Flood - Underpass   │ │      └────────┘                             │
│ │ 📍 Rasulgarh (4 Trapped)  │ │                       ┌────────┐            │
│ │ 3 Reports (2 Corroborated)│ │                       │ 📍 65.0│ (Orange)   │
│ └───────────────────────────┘ │                       └────────┘            │
│ ┌───────────────────────────┐ │                                             │
│ │ #2 HIGH (Score: 65.0)     │ │                                             │
│ │ Wall Collapse             │ │                                             │
│ └───────────────────────────┘ │                                             │
├───────────────────────────────┴─────────────────────────────────────────────┤
│ INCIDENT INSPECTION DRAWER (Selected: inc-9831a2)                           │
│ ├── Why This Priority? (Factor contribution bars & plain-language summary)  │
│ ├── Fused Source Dispatches (Timeline of citizen calls & raw text)          │
│ ├── Tactical Action / Response Needed: [SEARCH & RESCUE] [MEDICAL]          │
│ └── Operator Override Controls [Change Urgency] [Edit Risk] [Confirm / Close│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Component Hierarchy

```text
src/
├── components/
│   ├── layout/
│   │   ├── HeaderBar.jsx          (System status, counters, simulation launcher)
│   │   └── SplitWorkspace.jsx     (Resizable left queue / right map split)
│   ├── queue/
│   │   ├── IncidentQueue.jsx      (Virtualized sorted list of incident cards)
│   │   ├── IncidentCard.jsx       (Severity badge, factor badges, corroboration pill)
│   │   └── QueueFilterTabs.jsx    (Filter by CRITICAL, ACTIVE, NEEDS_REVIEW, RESOLVED)
│   ├── map/
│   │   ├── TacticalMap.jsx        (Leaflet container, tile layer setup, map bounds)
│   │   ├── IncidentMarker.jsx     (Custom SVG div-icons with pulsing severity rings)
│   │   └── MapLegend.jsx          (Tactical severity and category key)
│   ├── detail/
│   │   ├── IncidentDetailDrawer.jsx (Slide-over drawer for deep triage)
│   │   ├── PriorityExplainer.jsx    (Factor weights, contribution breakdown bars)
│   │   ├── SourceReportsTimeline.jsx(Raw dispatches with DUPLICATE vs CORROBORATING tags)
│   │   └── OperatorOverrideModal.jsx(Form for operator field override with audit reason)
│   ├── simulator/
│   │   └── SimulatorControlModal.jsx(Scenario picker, rate slider, start/stop trigger)
│   └── injection/
│       └── ManualReportModal.jsx    (Direct dispatcher report entry form)
├── hooks/
│   ├── useIncidents.js            (REST fetcher + live WebSocket state reconciler)
│   ├── useIncidentWebSocket.js    (WebSocket lifecycle, heartbeat, reconnect loop)
│   └── useSimulator.js            (Simulator control mutations)
└── styles/
    └── design-tokens.css          (Color tokens, typography, elevation, animations)
```

---

## 4. Design System Tokens & Tactical Aesthetics

Karen's Ear uses a high-contrast dark theme engineered for legibility and minimal eye strain:

### 4.1 Color Palette
* **Background Canvas:** Deep Tactical Void (`#0B0F17`)
* **Card & Surface Background:** Dark Slate Surface (`#131B2E`)
* **Borders & Dividers:** Subtle Slate Border (`#1E293B`)
* **Severity Colors:**
  * `CRITICAL`: Neon Crimson (`#EF4444`, glow `rgba(239, 68, 68, 0.3)`)
  * `HIGH`: High-Vis Amber (`#F97316`)
  * `MEDIUM`: Warning Gold (`#F59E0B`)
  * `LOW`: Cool Slate (`#64748B`)
* **Verification & Corroboration:** Electric Cyan (`#06B6D4`)
* **Simulated Indicator:** Royal Purple (`#A855F7`)

### 4.2 Interactive Micro-Animations
* **Queue Re-ordering:** Cards animate position smoothly using CSS transitions (`transform 300ms ease`).
* **Live Ingestion Pulse:** Newly arrived or updated incidents exhibit a brief perimeter glow pulse to alert dispatchers without auditory distraction.
* **Map Pin Interaction:** Clicking a card pans and zooms the Leaflet map to the incident marker; clicking a map marker highlights and scrolls to the card.

---

## 5. State Management & Real-Time Reconciliation

1. **State Ownership:**
   * Global state holds:
     * `incidents`: Dictionary indexed by `incident_id` for $O(1)$ updates.
     * `sortedIncidentIds`: Memoized array sorted by `priority_score DESC`.
     * `selectedIncidentId`: Incident currently open in inspection drawer.
     * `wsStatus`: `'CONNECTING'`, `'CONNECTED'`, `'DISCONNECTED'`.
     * `activeFilter`: Current queue view tab.
2. **Event Handling:**
   * When `INCIDENT_UPDATED` arrives over WebSocket:
     1. Mutates `incidents[id]` in place.
     2. Re-computes priority order.
     3. Triggers card position transition.
     4. Updates map marker coordinates/color.
3. **No-Hallucination Location Handling on Map:**
   * If `incident.location.latitude == null`, the incident is tagged with a `"NO GPS / APPROX"` pill in the queue card and is **omitted from the geographic map** (or placed in an "Unmapped / Approximate" side dock).
   * Exact coordinates are NEVER invented just to draw a pin on the map.
