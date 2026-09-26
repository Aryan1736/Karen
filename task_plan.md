# Karen's Ear — Task Plan

## Current Phase
Phase 1 — B: Blueprint (Vision & Logic)

## Project Status
BLUEPRINT_REVISIONS_INCORPORATED (AWAITING_APPROVAL)

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

### Phase 1 — B: Blueprint (REVISED & COMPLETED)
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
- [ ] Obtain Blueprint approval

### Phase 2 — L: Link
- [ ] Verify environment variables & Render / Vercel configurations
- [ ] Verify Hugging Face dataset download & local inference environment
- [ ] Benchmark ML model memory footprint and inference latency (RAM & CPU targets)
- [ ] Verify PostgreSQL connection & table initialization
- [ ] Build minimal connectivity test scripts in `tools/`
- [ ] Validate end-to-end data handshake across services

### Phase 3 — A: Architect
- [ ] Build Layer 1 SOPs in `architecture/`
- [ ] Build ML pipeline with feature-derived urgency (`feature/ml-pipeline` - Aryan)
- [ ] Build backend & PostgreSQL models (`feature/backend` - Daksh)
- [ ] Build incident engine & tunable fusion/deduplication (`feature/backend` - Daksh)
- [ ] Build deterministic priority scorer with explainable factors (`feature/backend` - Daksh)
- [ ] Build frontend command center & Leaflet map (`feature/frontend` - Srinivash)
- [ ] Build simulator & integration tests (`feature/evaluation-integration` - Pankaj)
- [ ] Integrate components via established API contracts

### Phase 4 — S: Stylize
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
