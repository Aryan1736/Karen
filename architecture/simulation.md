# Karen's Ear — Synthetic Simulation Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Purpose & Hackathon Role

In a live hackathon demonstration or tactical training drill, real live disaster reports are rarely occurring at the moment of evaluation. Relying purely on typing single reports by hand fails to showcase the system's true capabilities:
1. High-throughput real-time queue sorting.
2. Automatic deduplication of bursty messages.
3. Multi-source corroboration elevating priority.
4. Visual clustering on the interactive tactical map.

The **Synthetic Simulation Engine** generates controlled, realistic bursts of crisis reports modeled on actual disaster datasets (`CrisiText`, FEMA alerts) to rigorously exercise the system.

---

## 3. Strict Safety & Labeling Invariant
> **Synthetic reports must NEVER be confused with real emergency dispatches. Every simulated dispatch is permanently tagged with `"is_synthetic": true`.**

* In PostgreSQL: `raw_reports.is_synthetic = TRUE`.
* In API Envelopes: `"is_synthetic": true` on all returned incident and report objects.
* In Command Center UI: Prominent visual badge (e.g. purple pill: `[SIMULATED]`) displayed on the card and map popup.

---

## 4. Simulation Engine Pipeline

```text
[ Simulator Configuration ]
  - Scenario Selection (e.g., "Bhubaneswar Urban Flash Flood")
  - Dispatch Velocity (e.g., 10 reports/min)
  - Duplicate Ratio (e.g., 40% duplicates)
  - Escalation Chance (e.g., 20% life-safety surge)
               │
               ▼
[ Scenario Template Engine ] (Draws from CrisiText FEMA scenarios + Local Gazetteer)
               │
               ▼
[ Dispatch Mutation Engine ]
  ├── Exact duplicates (re-tweets / echo dispatches)
  ├── Independent eyewitness variations (different wording, same coordinates)
  ├── Secondary related reports (traffic jams, power cuts)
  └── Outlier noise (minor unrelated incidents)
               │
               ▼
[ Timed Ingestion Loop ] ──► Calls standard `POST /reports` with `is_synthetic: true`
               │
               ▼
[ Live Dashboard Reaction ]
```

---

## 5. Scenario Presets & CrisiText Integration

The simulator leverages narrative event chains from `LanD-FBK/crisitext`:

### Scenario Preset 1: Urban Flash Flooding & Underpass Submersion
* **Scenario ID:** `sim_scenario_flood_01`
* **Geographic Focus:** Urban transit hubs & low-lying underpasses (e.g., Rasulgarh, Patia, Jaydev Vihar).
* **Progression:**
  * *T0 to T+2m:* Early warning dispatches, minor street waterlogging (Urgency: `LOW` $\to$ `MEDIUM`).
  * *T+2m to T+5m:* Multiple vehicles trapped under railway underpass, water reaching roof level (Urgency: `HIGH` $\to$ `CRITICAL`).
  * *T+5m to T+8m:* Surge of duplicate citizen calls corroborating trapped passengers, pushing incident to #1 in queue.

### Scenario Preset 2: Structural Collapse & Fire Outbreak
* **Scenario ID:** `sim_scenario_collapse_02`
* **Geographic Focus:** High-density commercial district.
* **Progression:**
  * Explosive bang reported, smoke observed, panic dispatches.
  * Structural partial collapse, citizens screaming under rubble.
  * Multi-agency response requirements triggered: `FIRE_HAZMAT` + `SEARCH_AND_RESCUE` + `MEDICAL_EMS`.

---

## 6. Simulator Control Interface & REST API

The simulator is controlled via backend endpoints and a dedicated UI panel in the Command Center:

```text
POST /simulation/start
{
  "scenario_id": "sim_scenario_flood_01",
  "rate_per_minute": 15,
  "total_reports": 30,
  "duplicate_probability": 0.35,
  "escalation_probability": 0.20
}

POST /simulation/stop
{
  "simulation_id": "sim-881"
}
```

The simulator runs as an asynchronous background task within FastAPI without blocking incoming manual dispatches.
