# Karen's Ear — Task Plan

## Current Phase
Phase 3 — A: Architect (Technical Specifications & 3-Layer Blueprints)

## Project Status
ARCHITECT_COMPLETED_AWAITING_APPROVAL

## Phases

### Protocol 0 — Initialization (COMPLETED)
- [x] Create project memory (`task_plan.md`, `findings.md`, `progress.md`, `gemini.md`)
- [x] Answer discovery questions (Q1–Q6 confirmed)
- [x] Define data schemas (Raw Report, ML Output, Incident, Audit Log)
- [x] Define architectural invariants (AI probabilistic / App deterministic, No hallucination)
- [x] Define behavioral rules (Explainability, Graceful degradation, Needs review)
- [x] Define team ownership (Aryan: ML, Daksh: Backend, Pankaj: Integration/Eval, Srinivash: Frontend)
- [x] Define integration contracts (ML → Backend, Backend → Frontend, Sim → Backend)
- [x] Obtain Protocol 0 sign-off and approval to proceed

### Phase 1 — B: Blueprint (COMPLETED & APPROVED)
- [x] Inspect existing repository state (`https://github.com/Aryan1736/Karen.git`)
- [x] Inspect CrisiText schema (`LanD-FBK/crisitext` on Hugging Face)
- [x] Determine usable ML tasks & align with dataset constraints (CrisiText is NLG warning data, not labeled urgency)
- [x] Define explicit Urgency Methodology (Feature-derived from life-safety, hazard velocity, and separate evaluation)
- [x] Research crisis-classification resources (`HumAID`, `CrisisBench`, `CrisisTransformers`)
- [x] Research semantic incident correlation & dynamic thresholding (0.85 baseline to be empirically calibrated)
- [x] Research duplicate detection vs. independent corroboration mechanics
- [x] Research emergency dashboard patterns (Aegis, CrisisKit Lite, Leaflet/OSM)
- [x] Finalize ML pipeline boundaries (Aryan: classification, NER, embeddings)
- [x] Finalize JSON contracts in `gemini.md` (Raw Report, ML Output, Incident, Priority, Override, API Envelope)
- [x] Define runtime resource benchmarking targets (profile RAM and CPU latency on Render/local)
- [x] Obtain Blueprint approval

### Phase 2 — L: Link (COMPLETED & APPROVED)
- [x] Verify GitHub remote (`https://github.com/Aryan1736/Karen.git` on branch `main`)
- [x] Verify Python runtime (Python 3.13.5, pip, venv) & Node.js (v22.19.0, npm 10.9.3)
- [x] Verify CrisiText access (`LanD-FBK/crisitext` streaming sample, 8 columns, no API key needed)
- [x] Verify ML runtime (`sentence-transformers/all-MiniLM-L6-v2`, 384 dims, measured 9.68 ms CPU latency)
- [x] Verify PostgreSQL (`postgresql://localhost:5432`, `SELECT 1` successful, v18.3)
- [x] Verify OpenStreetMap (OSM main & tile servers reachable, HTTP 200)
- [x] Verify Vercel compatibility (Node.js/npm tooling ready for static/Vite client build)
- [x] Verify Render compatibility (Python 3.13 web service & environment variable model verified)
- [x] Create deterministic link checks (`tools/` modular scripts + `tools/check_links.py` entrypoint)
- [x] Obtain Link verification approval

### Phase 3 — A: Architect (COMPLETED — AWAITING PHASE 4 APPROVAL)
- [x] Build Layer 1 SOPs in `architecture/` (17 comprehensive specifications authored)
- [x] Author system overview & trust boundaries (`architecture/system-overview.md`)
- [x] Author ML/NLP pipeline & feature-derived urgency (`architecture/ml-pipeline.md`)
- [x] Author incident correlation, dynamic thresholding & corroboration (`architecture/incident-correlation.md`)
- [x] Author deterministic priority engine & factor breakdown (`architecture/priority-engine.md`)
- [x] Author human review, override schema & audit logging (`architecture/human-review.md`)
- [x] Author failure handling & graceful degradation matrix (`architecture/failure-handling.md`)
- [x] Author REST API contracts & standard envelopes (`architecture/api-contracts.md`)
- [x] Author PostgreSQL schema design & relational indexes (`architecture/database.md`)
- [x] Author real-time event streaming & WebSocket lifecycle (`architecture/realtime.md`)
- [x] Author synthetic disaster simulation architecture (`architecture/simulation.md`)
- [x] Author command center frontend layout & design tokens (`architecture/frontend.md`)
- [x] Author deployment & dual-platform topology (`architecture/deployment.md`)
- [x] Author security, secrets management & safety rules (`architecture/security.md`)
- [x] Author testing levels & quantitative ML benchmarks (`architecture/testing.md`)
- [x] Author observability, JSON logging & health telemetry (`architecture/observability.md`)
- [x] Author Layer 2 Navigation state machine & orchestration flow (`architecture/navigation.md`)
- [x] Author binding Architectural Decision Records ADR-001 through ADR-010 (`architecture/decisions.md`)
- [x] Establish Layer 3 Tools boundary and ephemeral `.tmp/` scratch space
- [x] Create repository `README.md` referencing architecture documentation
- [ ] Architect approval gate (Halted for user sign-off before Phase 4)

### Phase 4 — S: Stylize
- [ ] Scaffold frontend UI components & styling design system tokens
- [ ] Build tactical dark-mode Command Center layout
- [ ] Build interactive Leaflet tactical map with custom severity markers
- [ ] Build prioritized incident queue with smooth re-ordering micro-animations
- [ ] Build incident detail drawer with explainable factor breakdown bars
- [ ] Build human override modal with mandatory audit justification
- [ ] Build manual report injection & simulator control modals
- [ ] Verify mock-to-real UI rendering without visual placeholders

### Phase 5 — T: Trigger
- [ ] Polish command center UI/UX (dark-mode aesthetic, micro-animations, clean layout)
- [ ] Polish interactive Leaflet map (incident markers, clustering, severity heat indicators)
- [ ] Polish incident detail drawer & corroboration audit timeline
- [ ] Refine human override modal & feedback loops
- [ ] Validate demo flow (manual injection + simulated crisis surge)

### Phase 5 — T: Trigger
- [ ] Deploy backend & database to Render
- [ ] Deploy frontend command center to Vercel
- [ ] End-to-end verification of production cloud deployment
- [ ] Finalize documentation, video walkthrough, and submission repository
- [ ] Final maintenance documentation in `gemini.md`
