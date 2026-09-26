# TINGLE — Visual DNA & Design System Specification
**Project Authority:** Google Stitch Project `14393008759381373726`  
**Product Name:** TINGLE (Frontend Presentation)  
**System Identity:** Tactical Emergency Intelligence & Incident Correlation System  
**Design Philosophy:** Kinetic Neo-Brutalism & Multiverse Tactical Dispatch  

---

## 1. Visual Theme & Atmosphere

TINGLE is an emergency intelligence operating console engineered for high-stakes dispatchers and situational commanders operating under intense cognitive pressure. The visual identity rejects generic SaaS clichés—no soft ambient gradient blobs, no frosted-glass translucencies, and no floating pills.

Instead, the system enforces **Kinetic Neo-Brutalism**:
- **Absolute Structural Integrity:** Unapologetic `2px` to `4px` solid ink-black borders (`#08080C`) framing all tactical modules.
- **Physicality & Mechanical Feedback:** Hard, un-blurred offset drop shadows (`2px 2px 0 #08080C` up to `8px 8px 0 #08080C`) that mechanically depress on interaction (`transform: translate(2px, 2px)` / `translate(4px, 4px)` collapsing shadow).
- **Sharp Geometry:** Raw `0px` border radii (`roundedness: 0`) across cards, badges, buttons, and panels. Softness dilutes urgency; hard 90-degree corners establish precision and authority.
- **Multiverse Tactical Artifacts:** Half-tone microdot screen overlays, deliberate CMYK misregistration fringes (cyan/magenta chromatic offsets on critical thresholds), tactical hazard striping, and asymmetric comic panels.
- **Operational Pipeline:** Visualizes the emergency transition: **CHAOS → SIGNAL → INCIDENT → PRIORITY → ACTION**.

---

## 2. Color Palette & Roles

The palette operates on high-voltage ink-on-newsprint contrast against a deep multiverse void. Backgrounds sit in deep optical carbons (`#08080C` and `#111116`), providing maximum contrast for chromatic registration punches and luminous hazard indicators.

### 2.1 Void & Surface Base
- **Void Dark Canvas** (`#08080C` / `--color-void-dark` / `--color-bg-canvas`): Deepest background canvas and structural ink-border color.
- **Surface Dark** (`#111116` / `--color-surface-dark` / `--color-bg-surface`): Primary container and card surface fill.
- **Surface Dark Elevated** (`#1A1A24` / `--color-surface-dark-elevated`): Elevated tactical docks, active headers, and inspector panels.
- **Surface Container Scale:**
  - `surface-container-lowest`: `#0e0e12` (telemetry strips, sub-drawers)
  - `surface-container-low`: `#1b1b20` (dock rails, panel sidebars)
  - `surface-container`: `#1f1f24` (item rows, feed items)
  - `surface-container-high`: `#2a292e` (control groups, filter trays)
  - `surface-container-highest`: `#353439` (hover surfaces, active indicators)

### 2.2 Text & High-Contrast Typography
- **Newsprint White** (`#F4F4F0` / `--color-newsprint-white` / `--color-text-primary`): Primary display headlines, button text, and high-urgency callouts.
- **On-Surface Steel** (`#e4e1e8` / `--color-on-surface` / `--color-text-secondary`): Standard body copy and operational descriptions.
- **Muted Steel** (`#94A3B8` / `--color-text-muted`): Secondary telemetry notes, inactive labels.
- **Outline & Grid Muted** (`#5d3f3e`, `#ad8886` / `--color-outline`, `--color-outline-variant`): Cartographic grid lines and subtle dividers.

### 2.3 Tactical Priority Spectrum
- **P0 / CRITICAL** (`#E61937` / `#FF2B4A` / `--color-critical` / `--color-p0-critical`): Life-safety threat, active rescue needed. High-frequency pulsing beacon, solid black borders, white text.
- **P1 / HIGH** (`#FF5C00` / `--color-high` / `--color-p1-high`): Severe damage / high hazard. Hazard Orange fill, black text (`#08080C`), angular bracket containment (`[ HIGH ]`).
- **P2 / MEDIUM** (`#FFE600` / `--color-medium` / `--color-p2-medium`): Localized secondary hazard. Dispatch Yellow fill, black text (`#08080C`), hard offset shadow.
- **P3 / LOW** (`#00F0FF` / `--color-low` / `--color-p3-cyan`): Advisory updates. Electric Cyan outline / fill, structural bracket framing.
- **NEEDS REVIEW / GLITCH** (`#FF007A` / `#B026FF` / `--color-glitch-magenta`): Unverified data, low model confidence (< 0.60), or missing GPS. Vivid magenta with chromatic misregistration.
- **VERIFIED & TELEMETRY** (`#00F0FF` / `--color-cyan-corroboration`): Verified signal threads, corroborated witness count, active WebSocket link.
- **SYSTEM HEALTH** (`#00FF66` / `--color-success` / `--color-system-green`): Active feeds, healthy background workers, encrypted transport.

---

## 3. Typographic Architecture

The typographic hierarchy balances dramatic comic book momentum with cold mathematical HUD readouts:

1. **Display & Primary Headlines (`Anton`, sans-serif):**
   - Condensed, punchy, and aggressive.
   - Applied in uppercase for maximum visual punch (`letter-spacing: 0.03em - 0.05em`).
   - Evokes the physical force of screen-printed comic title blocks and tactical bulletins.
   - Scale:
     - `display-hero`: 64px / line-height 68px
     - `headline-lg`: 36px / line-height 40px
     - `headline-md`: 24px / line-height 28px
2. **Body & Operational Narrative (`Space Grotesk`, sans-serif):**
   - Modern, sharp, and highly legible with geometric quirks.
   - Handles operational narratives, citizen dispatches, and explanation factor bars without visual fatigue.
   - Scale:
     - `headline-sm`: 18px / line-height 24px (font-weight: 700)
     - `body-lg`: 16px / line-height 24px (font-weight: 500)
     - `body-md`: 14px / line-height 20px (font-weight: 400)
     - `body-sm`: 12px / line-height 18px (font-weight: 400)
3. **Telemetry & Tactical Metadata (`JetBrains Mono`, monospace):**
   - Monospaced, razor-sharp technical figures.
   - Governs telemetry readouts, geo-coordinates, confidence percentages, RF frequencies, and UTC timestamps.
   - Scale:
     - `label-lg`: 14px / line-height 18px (font-weight: 700, letter-spacing: 0.05em)
     - `label-md`: 12px / line-height 16px (font-weight: 600, letter-spacing: 0.06em)
     - `label-sm`: 10px / line-height 14px (font-weight: 500, letter-spacing: 0.08em)

---

## 4. Elevation, Depth & Geometry

Depth in TINGLE is purely tactile, directional, and physical—no blurred glow artifacts.

### 4.1 Hard-Offset Shadow Scale
- **Level 0 (Flat / Pressed):** `0px 0px 0 #08080C`, solid 2px-3px ink border.
- **Level 1 (Pills & Status Chips):** `2px 2px 0 #08080C`.
- **Level 2 (Standard Panels & Incident Cards):** `4px 4px 0 #08080C`.
- **Level 3 (Tactical Modals & Focus States):** `6px 6px 0 #08080C` or `8px 8px 0 #08080C`.

### 4.2 Chromatic Shadow Overdrive
- **AI Focus / High Alert:** `box-shadow: 4px 4px 0 #00F0FF, 8px 8px 0 #08080C;`
- **Glitch / Needs Review Misregistration:** `box-shadow: -2px 0 #00F0FF, 2px 0 #FF007A;`

### 4.3 Tactile Patterns & Textures
- **Halftone Dot Matrix:** `radial-gradient(var(--color-surface-container-high) 1px, transparent 1px)` with 6px spacing.
- **Hazard Tape Striping:** `repeating-linear-gradient(45deg, #08080C, #08080C 10px, #FFE600 10px, #FFE600 20px)` or orange/black variant.

---

## 5. Reusable Component Rules

### 5.1 Tactical Buttons (`Button`)
- **Visual:** Solid structural fills (`#E61937`, `#FF5C00`, `#FFE600`, `#1f1f24`), solid 2px–3px `#08080C` ink border, all-caps Anton or Space Grotesk typography.
- **Interaction Physics:**
  - Base: `box-shadow: 3px 3px 0 #08080C;` (or `4px 4px 0 #08080C`)
  - Hover: `transform: translate(-1px, -1px); box-shadow: 5px 5px 0 #08080C;`
  - Active: `transform: translate(2px, 2px); box-shadow: 0px 0px 0 #08080C;`

### 5.2 Badges & Priority Chips (`Badge`)
- **P0 CRITICAL:** Red fill, white text, 2px black border, accompanied by a pulsing cyan/white dot beacon.
- **P1 HIGH:** Hazard Orange fill, black text, bracketed `[ HIGH ]`.
- **P2 MED:** Dispatch Yellow fill, black text, 2px offset shadow.
- **P3 LOW:** Void black fill, Electric Cyan text, 2px Cyan outline.
- **NEEDS REVIEW:** Glitch Magenta fill or border, cyan chromatic misregistration.
- **SIM-LIVE:** Hazard orange striping with blinking ping beacon.

### 5.3 Tactical Cards & Containers (`Card`)
- 2px to 4px continuous solid ink-black border (`#08080C`).
- Top-edge tactical tape badge displaying incident coordinates and millisecond timestamps in `JetBrains Mono`.
- Zero border radius (`roundedness: 0`).

### 5.4 Confidence & Telemetry Gauges (`ConfidenceGauge`)
- Segmented brutalist bar meter or stepped progress blocks: `[████████░░] 94.2%`.
- High-voltage cyan or toxic green fill against void-dark track.

---

## 6. Anti-Patterns (Banned in TINGLE)

1. **NO Emojis in production UI:** Use SVG/Lucide icons or technical glyphs.
2. **NO `Inter` or generic system fonts:** Exclusively use `Anton`, `Space Grotesk`, and `JetBrains Mono`.
3. **NO Rounded Corners:** No `rounded-md`, `rounded-xl`, or `rounded-2xl` on cards, panels, or buttons. All corners are crisp 90° (`0px`).
4. **NO Blur / Translucent Glass Shadows:** Never use blurry `box-shadow: 0 10px 30px rgba(0,0,0,0.2)`. Shadows must be hard, crisp, and directional (`Xpx Ypx 0 #08080C`).
5. **NO Neon Gradient Bubbles:** No purple/blue gradient backgrounds or glowing aura spheres.
6. **NO Fabricated Data / Fake Predictions:** All metrics, scores, and timestamps must represent genuine state or deterministic computations.
