# UI Transformation Blueprint: Silt Strider

**Owner & Lead:** Antigravity (UI Transformation Lead)  
**Implementer:** Codex (Site Implementation Agent)  
**Data Supplier:** Claude (Database / Pipeline Agent)

---

## 1. Design Philosophy & Thematic Benchmark

The visual and ergonomic benchmark for the Silt Strider UI transformation is Morrowind's canonical in-game interface (captured in `Char Creation.png`):
- **Tactile CRPG Ergonomics:** Immediate, side-by-side feedback between character selections and resulting statistics. No scrolling required to see the effect of choices on desktop.
- **Authentic Morrowind Aesthetic:**
  - **Typography:** *Pelagiad* for display headings, *Iowan Old Style / Palatino* for prose, *Segoe UI* for numeric tabular data.
  - **Borders & Frames:** Procedural 9-slice repeating borders (`--mw-border` 6px window frame, `--mw-bevel` 4px button bevel, `--mw-groove` 2px etched divider). Never stretch pixel grain.
  - **Vitals Status Bars:** Gradients for Health (red `#a03017`), Magicka (blue `#2a387f`), and Fatigue (green `#007a2f`) with 2px groove bevels and centered tabular fractions (`45/45`).
  - **Color Palette:** Warm parchment text (`#f3e6c8`), dark surface panels (`#181510`), and weathered brass/gold accents (`#d4b06a`).

---

### 1.1 Operational Guardrails & Quality Protocols

1. **Shell & Environment Invariants (CRITICAL):**
   - **PowerShell Only:** Never emit bash chained operators (`&&`). Always use PowerShell command separators (`;`) or execute statements sequentially.
   - **Temp Isolation:** All temp fixtures, staging databases, artifacts, and test caches must strictly reside in `A:\Cache`. Always prefix pipeline test invocations with:
     `$env:TEMP='A:\Cache'; $env:TMP='A:\Cache'; python -B -m unittest discover -s . -p "test_*.py"`
   - **Scratch & Secret Isolation:** Never stage scratch files (e.g., `<scratchDir>/capture-*.js`), `Char Creation.png`, or `Hey.html`. Always clean up temporary CDP runner scripts after visual evaluation.

2. **Cross-Repo Boundary Enforcement:**
   - **Strict Boundary:** The Pipeline agent (`OpenMW Decompiler`) must NEVER directly modify files inside `A:\Claude\morrowind-tools`.
   - **Contract Sync:** Changes to game parsing outputs or schemas pass exclusively via exported JSON bundles to `public/legacy/` and synchronized updates to `COORDINATION.md` and `UI_TRANSFORMATION.md`.
   - **Legacy HTML Sync Hook:** Whenever `index.html` in the site repo is modified, immediately run `npm run extract:legacy` to regenerate `public/legacy/body.html` before running tests or visual verification. Never leave Next.js running against stale extracted markup.

3. **Verification & Adversarial QA Protocols:**
   - **Pipeline Tests (233 suites):** Must pass cleanly with zero uncaught warnings. Output should be summarized; do not flood context with raw passing test logs.
   - **Site Tests (155 suites) & CDP Screenshots:** Run `npm test` in `A:\Claude\morrowind-tools`. For UI modifications, execute headless visual capture via Chrome CDP on port 8765 (`node <scratchDir>/capture-*.js`) to confirm layout integrity on desktop and mobile before ticket completion.
   - **Adversarial Edge Cases:** Do not approve schema/logic changes on baseline tests alone. Before marking a logic task complete, write at least 3 automated tests targeting edge conditions (malformed record tags, missing SQLite indices, null/undefined properties, or boundary values).

4. **Two-Failure Revert & Escalation Policy:**
   - If an automated test fails twice consecutively during a fix attempt:
     1. Immediately abort code edits.
     2. Revert the working directory to the last clean git commit (`git restore .` / `git checkout .`).
     3. Emit a concise root-cause analysis showing the failing stack trace and the exact breaking invariant.
     4. Stop and request a `/boost` escalation run. Do not accumulate speculative patches.

5. **Handoff & Synchronization:**
   - Keep `COORDINATION.md` and `UI_TRANSFORMATION.md` identical across both repositories.
   - When completing a batch or milestone, update `COORDINATION.md` with:
     - Exported dataset schema changes.
     - Invariants assumed by the downstream Next.js / legacy JS runtime.
     - Exactly which script/command the next agent must run first.

---

## 2. Phase 1 Blueprint: Two-Pane Character Builder

### Objective
Replace the legacy vertical conveyor belt in `#panel-build` (17 stacked dropdowns followed by a massive gear table, burying `#c-summary`) with a responsive two-pane CRPG dashboard.

### Wireframe Architecture (Desktop $\ge 1024\text{px}$)

```
+---------------------------------------------------------------------------------------------------------+
| Mode Switcher: [ Premade Builds ] [ Custom Class ]   |   Profile: [ Vanilla | TR | ARCE ]               |
+----------------------------------------------------+----------------------------------------------------+
| LEFT PANE: Character Configurator                  | RIGHT PANE: Live Character Sheet                   |
| (components/character-builder/configurator.jsx)    | (components/character-builder/character-sheet.jsx) |
|                                                    |                                                    |
| [ Race: Dark Elf v ]     [ Gender: Male v ]        | +-- VITALS (Health / Magicka / Fatigue) ---------+ |
| [ Class: Custom v ]      [ Sign: The Lady v ]      | | Health:  [======= 45/45 =======] (Red)         | |
| [ Spec: Stealth v ]                                | | Magicka: [======= 40/40 =======] (Blue)        | |
| [ Favored Attr 1: Agility v ]                      | | Fatigue: [====== 195/195 ======] (Green)       | |
| [ Favored Attr 2: Endurance v ]                    | +------------------------------------------------+ |
|                                                    |                                                    |
| +-- Major Skills (5) ----------------------------+ | +-- PRIMARY ATTRIBUTES (8 Stats) ----------------+ |
| | [ Short Blade v ]       [ Light Armor v ]      | | Strength: 40           Agility: 50              | |
| | [ Marksman v ]          [ Sneak v ]            | | Intelligence: 40       Speed: 50                | |
| | [ Security v ]                                 | | Willpower: 30          Endurance: 75 (+25 Lady) | |
| +------------------------------------------------+ | | Personality: 55 (+10)  Luck: 40                 | |
|                                                    | +------------------------------------------------+ |
| +-- Minor Skills (5) ----------------------------+ |                                                    |
| | [ Acrobatics v ]        [ Athletics v ]        | +-- MAJOR & MINOR SKILLS ------------------------+ |
| | [ Alchemy v ]           [ Mercantile v ]       | | Major: Marksman 40 · Short Blade 35 · Sneak 35 | |
| | [ Speechcraft v ]                              | | Minor: Light Armor 25 · Speechcraft 20 · ...   | |
| +------------------------------------------------+ | +------------------------------------------------+ |
|                                                    |                                                    |
| [ Local Saves (<details>) ]                        | +-- STARTING SPELLS & POWERS --------------------+ |
|                                                    | | Race: Ancestor Guardian                        | |
|                                                    | | Sign: Lady's Favor (+25), Lady's Grace (+25)   | |
|                                                    | +------------------------------------------------+ |
+----------------------------------------------------+----------------------------------------------------+
| GEAR ADVISOR (components/character-builder/gear-advisor.jsx)                                            |
| [x] Steal early gear   [ ] Endgame gear early   |   [ Optimize Gear for this Build ]                    |
| +-- Early Kit (Near starting towns, <= 500g) --+ +-- Late Kit (Endgame & Artifacts) ------------------+ |
| | Cuirass: Dark Brotherhood (Steal, Balmora)   | | Cuirass: Cuirass of the Savior's Hide (Tel Fyr)    | |
| | Weapon: Glass Dagger (Suran Pawn, 27g)       | | Weapon: Fang of Haynekhtnamet                      | |
+------------------------------------------------+--------------------------------------------------------+
```

---

## 3. Component Hierarchy & File Layout

Codex should scaffold the new React implementation under `components/character-builder/`:

```
components/character-builder/
├── character-builder-root.jsx      # Top-level coordinator & mode switch (Premade vs Custom)
├── configurator.jsx               # Left pane: Identity, Class, Sign, Attributes, Skill pickers
├── character-sheet.jsx            # Right pane: Vitals bars, 8 Attributes, Skills with bonuses, Spells
├── vitals-bar.jsx                 # Reusable red/blue/green bar with 2px groove bevel
├── attribute-grid.jsx             # 2-column tabular attribute list with bonus notes
├── skill-display-grid.jsx         # Major/Minor/Other skills display with source breakdown
├── gear-advisor.jsx               # Decoupled bottom panel: Early & Late gear recommendations
└── premade-browser.jsx            # Premade build catalog accordion by Playstyle and Race
```

---

## 4. State & Data Flow Specification

### Data Source
- Use `useGameData('character')` (from `components/use-game-data.jsx`):
  - Injects `Races`, `Classes`, `Birthsigns`, `Skills`, `Attributes`, and `Spells`.
  - Automatically updates when `profile` changes in `ShellProvider`.

### State Structure (`CharacterState`)
```typescript
interface CharacterState {
  version: 1;
  world: 'vanilla' | 'tr';
  arce: boolean;
  name?: string;
  race: string;           // e.g. "Dark Elf"
  gender: 'Male' | 'Female';
  className: string;      // "Custom" or preset name like "Acrobat"
  sign: string;           // e.g. "The Lady"
  spec: 'Combat' | 'Magic' | 'Stealth';
  fav1: string;           // e.g. "Agility"
  fav2: string;           // e.g. "Endurance"
  maj: [string, string, string, string, string];
  min: [string, string, string, string, string];
}
```

### Calculation Rules & Vitals Math (from `computeSheet()`)
- **Health:** $\lfloor(\text{Strength} + \text{Endurance}) / 2\rfloor$. *(Note: Birthsign Fortify Endurance does not increase starting Health)*.
- **Magicka:** $\text{Intelligence} \times (1 + \text{race multiplier} + \text{sign multiplier})$.
- **Fatigue:** $\text{Strength} + \text{Willpower} + \text{Agility} + \text{Endurance}$.
- **Duplicate Skill Swapping:** When changing a Major or Minor skill to a skill already assigned, swap the two slots directly (preserve `swapDuplicateSkill` logic).

---

## 5. Visual Styling Specifications (Tailwind & CSS Tokens)

1. **Dashboard Grid:**
   ```html
   <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full max-w-6xl mx-auto my-4">
     <!-- Left Pane: Configurator -->
     <!-- Right Pane: Live Character Sheet -->
   </div>
   ```

2. **Panels:**
   Use the authentic 6px window frame:
   ```css
   border: 6px solid transparent;
   border-image: var(--mw-border) 6 repeat;
   background: var(--surface, #181510);
   box-shadow: inset 0 0 10px 2px rgba(0, 0, 0, 0.9), 0 12px 32px rgba(0, 0, 0, 0.28);
   ```

3. **Vitals Bars (`vitals-bar.jsx`):**
   - **Health Gradient:** `linear-gradient(180deg, #a03017 0%, #9e2f17 20%, #671f0f 50%, #45130a 75%, #2f0e07 100%)`
   - **Magicka Gradient:** `linear-gradient(180deg, #2a387f 0%, #29367d 20%, #1b2352 50%, #121636 75%, #0c1025 100%)`
   - **Fatigue Gradient:** `linear-gradient(180deg, #007a2f 0%, #00772f 20%, #004d1f 50%, #003014 75%, #00240e 100%)`
   - **Border:** `2px solid transparent; border-image: var(--mw-groove) 2 repeat;`
   - **Text:** White/parchment with `text-shadow: 1px 1px 0 #000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000;`

---

## 6. Execution Checklist for Codex (Phase 1)

- [x] **Step 1:** Create `components/character-builder/` and scaffold the 8 subcomponents listed above.
- [x] **Step 2:** Port `computeSheet()` and `startingSpells()` calculation logic into a standalone pure helper (`lib/character-math.mjs`).
- [x] **Step 3:** Implement the two-pane layout for desktop ($\ge 1024\text{px}$) and verify responsive single-column collapse for mobile.
- [x] **Step 4:** Decouple `#gear-box` into `gear-advisor.jsx` situated below the character sheet.
- [x] **Step 5:** Connect the new React builder to `ShellProvider` and bind permalink writing via `history.replaceState`.
- [x] **Step 6:** Run `npm test` in `A:\Claude\morrowind-tools` to ensure all 109 fixture, regression, and math tests continue to pass without errors.

---

## 7. Phase 2 Blueprint: Interactive Skill Matrix & Specialization Board

### 7.1 Objective & UX Architecture
Morrowind characters always start with exactly 5 Major and 5 Minor skills assigned. Static budget counters (e.g. 5/5 filled pips) and multi-column boards with modal conflicts disrupt natural character planning.

Phase 2 introduces the **Tactile Skill Slot Editor & Multiplier Tracker**:
- **Direct Tactical Slots:** 5 Major (+25) and 5 Minor (+10) interactive slots displayed in an authentic 2-column Morrowind bevel layout.
- **Immediate Contextual Intelligence:** Every slot displays the skill selector, governing attribute indicator (`[STR]`, `[AGI]`, etc.), and live computed skill rating badge (`[ 45 ]`, `[ 25 ]`) updating in real time.
- **Zero-Friction Duplicate Swapping:** Selecting an already-assigned skill automatically swaps it with the duplicate slot with no popups or modal interruptions.
- **Level-Up Multiplier Distribution Counter:** Pinned status strip displaying class skill coverage across all 7 primary attributes (`STR (3) · AGI (2) · END (2)...`) with an educational tooltip explaining Morrowind's 3-attribute level up mechanic and efficient leveling strategies.
- **1-Click Preset Customization:** Selecting a preset class locks the skills cleanly for canonical accuracy, while providing a 1-click `[ ✎ Customize Skills ]` action that transitions `className` to `"Custom"` for instant tweaking.
- **Holistic 27-Skill Roster:** The right-pane Live Character Sheet (`character-sheet.jsx`) remains the authoritative CRPG character sheet, displaying Major, Minor, and all 17 Miscellaneous skills with their computed values, matching `Char Creation.png`.

---

### 7.2 Desktop Wireframe ($\ge 1024\text{px}$)

```
+---------------------------------------------------------------------------------------------------------+
| CLASS SKILL DISTRIBUTION: STR(3)  AGI(2)  END(2)  INT(1)  WIL(2)  SPD(0)  PER(0)      [ (i) Info ]      |
+---------------------------------------------------------------------------------------------------------+
| [ Preset Class: Warrior (Locked) ]                                               [ ✎ Customize Skills ] |
+---------------------------------------------------------------------------------------------------------+
| MAJOR SKILLS (+25)                                                                              5 Slots |
| 1. [ Long Blade [STR]         v ] [ 45 ]         2. [ Heavy Armor [END]       v ] [ 35 ]                |
| 3. [ Block [AGI]              v ] [ 35 ]         4. [ Athletics [SPD]         v ] [ 35 ]                |
| 5. [ Armorer [STR]            v ] [ 20 ]                                                                |
+---------------------------------------------------------------------------------------------------------+
| MINOR SKILLS (+10)                                                                              5 Slots |
| 1. [ Spear [END]              v ] [ 20 ]         2. [ Marksman [AGI]          v ] [ 20 ]                |
| 3. [ Axe [STR]                v ] [ 20 ]         4. [ Blunt Weapon [STR]      v ] [ 20 ]                |
| 5. [ Medium Armor [END]       v ] [ 15 ]                                                                |
+---------------------------------------------------------------------------------------------------------+
```

---

### 7.3 Canonical Skill & Governing Attribute Matrix

Every skill belongs to exactly one Specialization and is governed by one Primary Attribute:

| Skill | Specialization | Governing Attribute | Calculation Rule |
| :--- | :---: | :---: | :--- |
| **Block** | Combat | Agility | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Armorer** | Combat | Strength | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Medium Armor** | Combat | Endurance | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Heavy Armor** | Combat | Endurance | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Blunt Weapon** | Combat | Strength | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Long Blade** | Combat | Strength | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Axe** | Combat | Strength | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Spear** | Combat | Endurance | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Athletics** | Combat | Speed | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Enchant** | Magic | Intelligence | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Destruction** | Magic | Willpower | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Alteration** | Magic | Willpower | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Illusion** | Magic | Personality | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Conjuration** | Magic | Intelligence | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Mysticism** | Magic | Willpower | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Restoration** | Magic | Willpower | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Alchemy** | Magic | Intelligence | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Unarmored** | Magic | Speed | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Security** | Stealth | Intelligence | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Sneak** | Stealth | Agility | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Acrobatics** | Stealth | Strength | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Light Armor** | Stealth | Agility | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Short Blade** | Stealth | Speed | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Marksman** | Stealth | Agility | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Mercantile** | Stealth | Personality | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Speechcraft** | Stealth | Personality | Base 5 + Spec(+5) + Tier(+25/+10) + Race |
| **Hand-to-hand** | Stealth | Speed | Base 5 + Spec(+5) + Tier(+25/+10) + Race |

*(Note: Luck governs no skills directly, but adds a global bonus to all action resolution formulas)*.

---

### 7.4 State Management & Micro-Interaction Rules

1. **Tier Assignment Lifecycle:**
   - Each skill exists in one of three states:
     - `Misc` (Base 5 + Spec? + Race?)
     - `Minor` (+10 bonus, fills 1 of 5 Minor slots)
     - `Major` (+25 bonus, fills 1 of 5 Major slots)
   - Tapping/clicking a skill cycles through `Misc` -> `Minor` -> `Major` -> `Misc`.
   - Alternatively, clicking the tier badge opens a 3-choice popover: `[ Major (+25) ]` `[ Minor (+10) ]` `[ Misc ]`.
2. **Budget Constraints & Auto-Promotion / Demotion:**
   - Maximum 5 Major skills, maximum 5 Minor skills.
   - If player clicks "Major" when 5 Majors are already filled:
     - Display a swap dialogue: *"Major slots full (5/5). Choose an existing Major skill to replace."*
     - If the replaced skill was a Minor skill, swap their positions cleanly.
3. **Preset Class Integration:**
   - Choosing a preset class (e.g. "Knight", "Mage", "Assassin") automatically marks its 5 Majors and 5 Minors across the board.
   - Modifying any skill assignment while a preset class is active automatically transitions `className` to `"Custom"`, with toast feedback.
4. **Multiplier Balance Counter:**
   - Above the matrix, a live badge bar displays how many Major + Minor skills fall under each attribute:
     `STR: 3 · AGI: 2 · END: 2 · INT: 1 · WIL: 2 · SPD: 0 · PER: 0`
   - Morrowind's leveling rules: Each level up allows picking **three attributes** to increase. Any attribute can gain up to a $\times 5$ bonus (+5) if the player gained 10 skill increases under that governing attribute (from Major, Minor, or Misc training) during that level.
   - This counter helps players balance class skills (which trigger level-ups) against Misc skills (which allow controlled training without advancing the level counter) to reliably hit $\times 5 / \times 5 / \times 5$ gains.

---

### 7.5 Mobile & Tablet Responsive Specifications (< 1024px)

- **Mobile Viewport Split:** On viewports under 1024px, display a horizontal segment tab bar:
  `[ Combat (9) ]  [ Magic (9) ]  [ Stealth (9) ]`
- **Sticky Budget HUD:** Pinned to top of the matrix:
  `Majors: 5/5 · Minors: 5/5 · Attr: STR(3) AGI(2)...`
- **Touch Ergonomics:** Each skill card has a minimum height of 44px with distinct tap targets for opening details vs toggling tier.

---

### 7.6 Component Hierarchy & File Layout (Phase 2)

```
components/character-builder/
├── configurator.jsx                       # Hosts SkillPicker coordinator
└── skill-picker/
    ├── index.jsx                          # Top coordinator (Matrix vs Slot toggle)
    ├── skill-matrix.jsx                   # 3-column specialization board
    ├── skill-card.jsx                     # Individual tactile card with attr badge & tier pill
    ├── skill-budget-bar.jsx               # Sticky 5/5 Major & 5/5 Minor budget tracker
    ├── skill-attribute-summary.jsx        # Multiplier distribution summary bar
    └── skill-swap-modal.jsx               # Conflict resolution modal when slots are full
```

---

### 7.7 Execution Checklist for Codex (Phase 2)

- [ ] **Step 1:** Scaffold `components/character-builder/skill-picker/` and create the 6 subcomponents listed above.
- [ ] **Step 2:** Build `skill-card.jsx` with authentic `--mw-bevel` borders, governing attribute badges, race bonus badges, and tier toggles.
- [ ] **Step 3:** Build `skill-matrix.jsx` supporting 3-column desktop layout and mobile tabbed specialization switcher.
- [ ] **Step 4:** Implement `skill-budget-bar.jsx` and the governing attribute multiplier summary.
- [ ] **Step 5:** Integrate `SkillPicker` into `configurator.jsx`, binding state to `build.maj` and `build.min` with bidirectional sync to legacy controls.
- [ ] **Step 6:** Run `npm test` and `npm run build` to guarantee zero regressions.

---

## 8. Phase 3 Blueprint: Cross-Tool Calculator State Integration

### 8.1 Objective & Architecture
Morrowind's specialized calculators (Enchanting, Spellmaking, Alchemy, Travel) currently function as isolated pages with manually re-entered values. 

Phase 3 introduces **Cross-Tool State Reactivity**:
- The active character's attributes, skills, and race powers automatically populate into the other calculators.
- Permalinks retain cross-tool state via unified URL hashes.
- Powered by `useActiveCharacter()` React Context that bridges the active character sheet across all tools.

---

### 8.2 Tool Integration Specifications

#### 1. Enchanting Calculator (`#panel-enchant`)
- **Ingested Stats:** Character's live **Intelligence** and **Enchant** skill.
- **Formulas:**
  - **Cast Success Rate:** $\text{Chance} = (\text{Enchant} + \frac{\text{Intelligence}}{5} + \frac{\text{Luck}}{10}) \times (\frac{\text{Current Fatigue}}{\text{Max Fatigue}}) - \text{Item Cast Cost}$.
  - **Constant Effect Cap:** Checks if Enchant skill $\ge 100$ and soul capacity $\ge 400$ (Golden Saint / Ascended Sleeper).
- **UI Enhancement:** Display live success chance badge next to item configuration.

#### 2. Spellmaking Calculator (`#panel-spell`)
- **Ingested Stats:** Character's live **Willpower**, **Luck**, and Magic School skills (**Destruction**, **Alteration**, **Illusion**, **Conjuration**, **Mysticism**, **Restoration**).
- **Formulas:**
  - **Spell Casting Chance:**
    $$\text{Cast %} = \left(2 \times \text{School Skill} - \text{Spell Cost} + \frac{\text{Willpower}}{5} + \frac{\text{Luck}}{10}\right) \times \left(0.75 + \frac{0.5 \times \text{Current Fatigue}}{\text{Max Fatigue}}\right)$$
- **UI Enhancement:** Live reliability rating: `[ Highly Reliable (95%) ]`, `[ Risky (45%) ]`, or `[ Uncastable (0%) ]`.

#### 3. Alchemy Calculator (`#panel-alchemy`)
- **Ingested Stats:** Character's live **Intelligence**, **Luck**, and **Alchemy** skill.
- **Formulas:**
  - **Brewing Success Chance:**
    $$\text{Brew %} = \text{Alchemy} + \frac{\text{Intelligence}}{10} + \frac{\text{Luck}}{10}$$
  - **Potion Magnitude & Duration:** Factored by character's apparatus quality and Intelligence.
- **UI Enhancement:** Live brew success indicator on recipe cards.

#### 4. Travel Optimizer (`#panel-travel`)
- **Ingested Stats:** Character's starting race and faction alignment.
- **UI Enhancement:** Quick-select origin button: `[ From Starting Hub: Seyda Neen / Balmora ]`.

---

### 8.3 Execution Checklist for Codex (Phase 3)

- [x] **Step 1:** Create `components/character-context.jsx` exposing `useActiveCharacter()`.
- [x] **Step 2:** Rewire Enchanting Calculator to read `Intelligence` and `Enchant` from context.
- [x] **Step 3:** Rewire Spellmaking Calculator to calculate live cast chance for crafted spells.
- [x] **Step 4:** Rewire Alchemy Calculator to calculate potion brew success.
- [x] **Step 5:** Verify automated tests and production build.

---

## 9. Comprehensive UX/UI Audit & Art Direction Polish

### 9.1 The 3-Tier CRPG Frame Hierarchy
- **Tier 1 (Outer Window Frame):** `--mw-border` (6px ornate scrollwork). Used exclusively for root primary panels (`.configurator`, `.character-sheet`, `.gear-advisor`, `.panel`). Never nested inside another Tier 1 frame.
- **Tier 2 (Structural Inset Inset):** `--mw-groove` (2px recessed etched line). Used for internal cards, panels, and plaques (Vitals, Spells, Calculator HUDs, Warning scrolls).
- **Tier 3 (Interactive Controls):** `--mw-bevel` (4px raised button bevel). Used exclusively for clickable buttons (`.mw-btn`), dropdowns (`.mw-select`), and inputs. Never used as a structural container.

### 9.2 Execution Checklist
- [x] **Step 1:** Establish 3-Tier Frame Hierarchy across all layout containers and components.
- [x] **Step 2:** Eliminate all line tangencies (mode bar double-bevel, skill slot border collisions, calculator HUD clashing, mobile sticky vitals elevation).
- [x] **Step 3:** Streamline mobile responsive ergonomics (remove duplicate sheet button, enlarge `<InfoTip>` touch target $\ge 32\text{px}$).
- [x] **Step 4:** Enhance accessibility (add `:focus-visible` gold outline `#d4b06a`, brighten muted text from `#8a7a5e` to `#9e8b6b` for WCAG AA $\ge 4.5:1$ contrast).
- [x] **Step 5:** Clean up orphaned/dead code in `components/character-builder/skill-picker/`.

### 9.3 Character Builder Ergonomics & Gear Advisor Face Lift
- [x] **Desktop Panel Proximity:** Reduced dashboard grid gap from `2rem` (32px) to `1.25rem` (20px) in `.cb-dashboard`, bringing the Configurator and Character Sheet into a tighter, cohesive visual unit on desktop viewports.
- [x] **Side Padding & Border Breathing Room:** Expanded interior horizontal padding in `.configurator`, `.character-sheet`, and `.gear-advisor` to `px-8 sm:px-10` (32px - 40px), guaranteeing ample breathing room between dropdowns/buttons and outer ornate 9-slice borders.
- [x] **Master Window Enclosing Frame:** Re-enclosed `#panel-build` within the authentic `--mw-border` 6px master window frame with deep inset shadows (`box-shadow: 0 12px 32px rgba(0,0,0,0.5), inset 0 0 16px 2px rgba(0,0,0,0.85)`), matching `#panel-challenge` (Challenge Runs master window) and establishing an enclosing frame for the entire character creator.
- [x] **Gear Recommendations CRPG Face Lift:**
  - Upgraded Armor Rating (AR) from flat inline text into a distinct, tactile CRPG stat badge (`.gear-ar-tag`) with burnished bronze gradient, 1px gold border (`#9e7f45`), bold monospace typography, and inset lighting.
  - Enhanced category banners (`th[colspan]`) and table headers (`thead th`) with *Pelagiad* serif typography, uppercase tracking (`0.08em`), and etched groove dividers (`--mw-groove`).
  - Elevated item names (`.gear-name`) with bold Pelagiad typography and styled Tamriel Rebuilt/region badges.

### 9.4 Character Builder Workspace Polish (Round 2)
- [x] **Controls Deep Breathing Room:** Enforced `padding: 36px 48px !important;` on `.configurator` and `.character-sheet` via dedicated CSS rules, providing a wide 48px gutter between border edges and outer controls (`Race`, `Class`, `Specialization` on left; `Female`, `Birthsign`, `Endurance` on right).
- [x] **Early Game & Endgame Kit Visual Emphasis:** Transformed `#gear-box details` and `.gear-results-container details` from plain text disclosures into high-contrast beveled CRPG plaques with 1.3rem *Pelagiad* headings, dark gradient banners (`linear-gradient(180deg, rgba(68,48,26,0.88), rgba(22,16,11,0.95))`), gold chevrons, and active hover lighting.
- [x] **Complete Miscellaneous Skills:** Updated `SkillDisplayGrid` to list all 17 miscellaneous skills alphabetically under the authentic heading `"Miscellaneous Skills"`.
- [x] **Mode Bar Visual Prominence & Clearance:** Added generous top margin (`mt-2 sm:mt-4 mb-8`) and expanded `#panel-build` top padding to `32px` to prevent buttons from touching the upper master panel border. Scaled mode switcher typography to `1.05rem` (`text-base`, `px-6 py-3`) with warm gold gradient and glowing focus highlights when active.
- [x] **Decoupled Superior Box Clearance:** Enforced clear negative space margins (`mt-7` on `LocalCharactersPanel`, `mt-8` on `GearAdvisor`) preventing any overlap or contact with superior dashboard containers.

### 9.5 Column-Aligned Mode Architecture & Local Characters Plaque (Round 3)
- [x] **Column-Aligned Mode Selectors:** Replaced the floating horizontal mode bar with a 2-column grid (`.mode-bar-grid`), aligning `Custom Class Builder` directly above the left column (`Character Configuration`) and `Premade Builds Catalog` directly above the right column (`Character Sheet`), eliminating asymmetric left floating.
- [x] **Guaranteed Superior Clearance:** Added 24px bottom margin (`mb-6` / `1.5rem`) on `.mode-bar-grid` and 32px top padding on `#panel-build`, ensuring mode selector buttons never touch the upper borders of `Character Configuration` or `Character Sheet`.
- [x] **Removed Broken Skill Numbers:** Eliminated the redundant and broken visual index numbers (`{idx + 1}.`) from Major and Minor skill slots in `configurator.jsx`, giving dropdowns clean horizontal expansion.
- [x] **Relocated Copy Build Link:** Placed the `Copy Build Link` action button directly beneath `Local Characters` in the left pane as a full-width management button.
- [x] **Local Characters CRPG Plaque:** Styled `#local-characters` with the exact same collapsible plaque aesthetic as the gear kit tabs (1.3rem *Pelagiad* bold heading, dark burnished bronze gradient header, gold chevron `▾`/`▴`, groove border, and dark inset shadow).

### 9.6 Mobile Ergonomics & Clean Attribute Presentation (Round 4)
- [x] **Non-Persistent Mobile Vitals:** Removed the sticky `.character-vitals-hud` from mobile viewports. On small screens, vitals are kept cleanly inside the `Character Sheet` tab, freeing 110px+ of vertical viewport space for configuring choices without sticky element obstruction.
- [x] **Mobile-First Gear Advisor Layout:** Restructured the action bar in `GearAdvisor` with clean checkbox wrapping and a full-width (`w-full sm:w-auto`) primary call-to-action button (`py-2.5 px-6`), transforming the previously dangling/awkward button on mobile into a solid, intentional CRPG action.
- [x] **Clean Specialization & Favored Attribute Option Text:** Removed inline `(+5 skills)` and `(+10)` from dropdown option values in `configurator.jsx` and moved bonuses to field labels (`Specialization (+5)`, `Favored Attr 1 (+10)`, `Favored Attr 2 (+10)`), matching `Major Skills (+25)` and `Minor Skills (+10)`. Eliminates option text truncation and clipping behind custom dropdown arrows.

### 9.7 InfoTip Inline Alignment & Mechanics Simplification (Round 5)
- [x] **Inline InfoTip Alignment:** Converted `<label>` layouts for `Birthsign`, `Specialization`, `Favored Attr 1`, and `Favored Attr 2` to `flex items-center justify-between` with `shrink-0` on `InfoTip`. Restored clean, concise field titles (`Specialization`, `Favored Attr 1`, `Favored Attr 2`), permanently preventing the info `(i)` button from wrapping below the title.
- [x] **Removed "Show the Math" Disclosure:** Completely excised the redundant `Show the math & mechanics breakdown` details accordion from `CharacterSheet`, streamlining the live sheet and focusing purely on authentic in-game Morrowind stats and starting powers.

### 9.8 Unified Site Typography & Pelagiad Integration (Round 6)
- [x] **Tailwind v4 Theme Font Binding:** Added `@theme` block into `app/globals.css` explicitly binding `--font-serif` to `"Pelagiad", "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;`, `--font-sans` to `"Segoe UI", system-ui, -apple-system, sans-serif;`, and `--font-mono` to `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;`. This activates authentic `Pelagiad` for all React components consuming Tailwind's `font-serif` utility class.
- [x] **Dropdown & Button Face Unification:** Configured `.mw-select` and `.mw-btn` to enforce `var(--font-serif) !important;` on their closed faces for authentic Elder Scrolls styling, while ensuring `.mw-select option, .mw-select optgroup` explicitly render in `var(--font-sans) !important;` (`Segoe UI` / `system-ui`) for crisp, legible rendering inside native OS menu popups.
- [x] **Global Heading & Button Parity:** Updated `index.html` heading and button selectors to prioritize `Pelagiad` across `h1, h2, h3, h4, .brand h1, .kicker, .btn`, `select`, and `.cat-btn`, creating 1:1 thematic parity between the Challenge Runs interface and the Character Builder.
- [x] **CRPG Table & Monospace Stat Tokens:** Consolidated all stat tags, Armor Rating badges (`.gear-ar-tag`), item metadata tags (`.gear-tag`, `.region-tag`), and saved character status messages to standard `var(--font-mono)`.

### 9.9 Responsive Navigation Bedrock & Hamburger Menu Polish (Round 7)
- [x] **Unified Responsive Breakpoint Architecture (<900px vs >=900px):** Unified the tablet and mobile navigation threshold to 899px across `index.html` and `app/globals.css`, eliminating the previous 768px-899px dead zone where the hamburger button was suppressed while header elements stacked awkwardly.
- [x] **Persistent Top Navigation:** Removed legacy view-based suppression (`body:not(.view-challenge):not(.view-builder) .nav-primary { display: none; }`), ensuring primary tool navigation links remain accessible across all views, including Home, About, and standalone calculators.
- [x] **Interactive Hamburger Toggle States:** Updated the trigger button in `components/site-header.jsx` to dynamically switch glyphs from `☰` (closed) to `✕` (open) with corresponding accessible `aria-label` updates (`Open menu` / `Close menu`) and tactile bevel styling.
- [x] **CRPG Mobile Navigation Drawer:** Styled `#react-menu-drawer.open` with an authentic 4px bevel frame, dark backdrop, gold focus outlines, full-width touch targets (>=44px), structured section dividers, and a dedicated `Game World Profile` section header.

### 9.10 Universal Navigation Polish & Account Harmonization (Round 8)
- [x] **Universal Page Access on Desktop:** Integrated sleek `Calculators ▾` and `More ▾` dropdown menus directly into the top bar across both React (`SiteHeader`) and standalone classic HTML (`index.html`). Desktop viewports have instant access to all 9 destinations (Challenge Runs, Build Optimizer, Enchanting, Spellmaking, Alchemy, Travel Optimizer, Choose a Tool, About, Changelog) while strictly preserving the desktop single-row header contract (`@media (min-width: 900px)`).
- [x] **Structured CRPG Mobile Drawer & Natural Scrolling:** Transformed `#react-menu-drawer.open` into an authentic Elder Scrolls navigation hub organized into clear thematic sections: Character Planners, Calculators (2-column touch grid), Reference & Site (3-column grid), and Game World Profile. Removed scroll trapping (`overscroll-behavior: contain`) so mobile users can smoothly scroll the page down to view all sections and account controls without gesture locking.
- [x] **Harmonized Account & Sign-In Controls:** Redesigned `.account-bar` to share identical `--mw-bevel` 4px borders, *Pelagiad* typography, and gold accent styling as the world selection controls. On desktop, button heights harmonize with header controls (32px min-height) with gold hover states and italic status badges. On mobile, the account bar automatically docks as the "Account & Cloud Saves" final section of the open drawer, remaining cleanly hidden when the menu is closed.
- [x] **Airtight Auth State & [hidden] Display:** Resolved specificity collision where mobile `display: flex !important` overrode the HTML `hidden` attribute. Explicitly scoped mobile rules to `.btn:not([hidden])` and `#account-user:not([hidden])` with high-specificity `.account-bar [hidden] { display: none !important; }`, guaranteeing that signed-out and signed-in states render accurately without empty avatar frames or lingering sign-in buttons.
- [x] **Outside-Click Boundary & Focus Restoration:** Expanded outside-click listeners in both React and classic HTML to recognize `.account-bar` as an interior component of the open drawer, preventing taps on auth buttons from dismissing the menu. Added WAI-ARIA keyboard navigation for desktop dropdowns (ArrowDown/ArrowUp cycling, Escape restoring focus to trigger buttons, Tab dismiss), topbar outside-click closing, and unmount cleanup for `.drawer-open`.

### 9.11 Desktop Navigation Refinements, ARCE Spacing & Account Bar Harmonization (Round 9)
- [x] **Desktop More Dropdown Refinement:** Excluded `home` from `MORE_VIEWS` and desktop `#react-more-dropdown-menu` / `#dropdown-more-menu`. The brand title (`Silt Strider`) already acts as the primary Home navigation link, removing redundant "Choose a Tool" dropdown entries. Fixed the active gold border (`.on`) on `More ▾` button when on the Home view, ensuring `More ▾` is only highlighted when viewing About or Changelog.
- [x] **TR & ARCE Desktop Header Spacing & Zero-Layout-Shift:** Eliminated header layout shift where switching to Tamriel Rebuilt increased topbar height from 84px to 100px. Unified desktop `.world-controls` (`min-width: 900px`) into an inline horizontal row with 6px gap (`flex-direction: row; align-items: center;`). Styled desktop ARCE button with compact padding and dynamic `+ ARCE` label, inline beside Tamriel Rebuilt. Tuned `#react-header-slot .nav-primary .btn` padding to `6px 12px` and `0.88rem`, preserving 411px width for the brand title in TR mode and locking header height at a stable 84px across all profiles.
- [x] **Harmonized Desktop Account & Cloud Saves Bar:** Transformed the floating `.account-bar` into a unified header section anchored below a subtle gold hairline divider (`border-top: 1px solid rgba(212, 176, 106, 0.2)`). Added an authentic `Account & Cloud Saves:` heading label (`::before`) matching the world selector aesthetic (`.cat-lbl`), visually grounding `[Sign in]` and `[Sign up]` buttons so they no longer appear disconnected from the layout.
- [x] **Preserved Mobile Drawer Parity:** Confirmed all desktop layout adjustments are strictly scoped under `@media (min-width: 900px)`, preserving 100% of the mobile drawer design, tactile buttons, and scrolling ergonomics.

### 9.12 Challenge Runs Pool & Logic Refinements (Round 10)
- [x] **Hill Giant Excluded from Randomizer:** Filtered "Hill Giant" out of the Randomizer race roll (`rollOne("race")`) and the Challenge Runs race select element (`#r-race`), ensuring the randomizer never rolls this extreme 5-speed monster race.
- [x] **Hard — No Magicka Refinement:** Simplified "No Magicka — fatigue and potions only" to "No Magicka" in `POOL` and `HARD`, removing fatigue and potion restrictions so players can still manage stamina and use potions while banned from using Magicka.
- [x] **Classified Merchant Training as Hard:** Added "No merchants except to pay for training" into the `HARD` difficulty band (`band() === "Hard"`).
- [x] **Factions and Settlements Restriction Conversion:** Moved "Join no factions until you have visited five settlements" from `OBJECTIVES` (where it didn't belong as a goal) into `POOL` as an active restriction.
- [x] **Clarified Fast Travel Ban Wording:** Updated "No Intervention spells, Mark, Recall, or Guild Guides" to "No guild guides, recall or intervention" in `POOL`.
- [x] **Enforced Level Cap vs Reach Level 50 Conflict Logic:** Tagged "Reach level 50" with `["level"]` in `tagsOf` and configured `restrictionBans` for "Level 20 cap", "Level 10 cap", and "Never sleep to level up — stay level 1" to return `["level"]`. This permanently prevents "Reach level 50" from generating alongside impossible level cap restrictions.

---

## 10. Phase 4 Blueprint: Challenge Runs Overhaul (Two-Pane Layout & Parchment Sheet)

### 10.1 Objective & Design Strategy
The existing Challenge Run tool in `#panel-challenge` presents a functional randomizer but suffers from a single-column stacked layout where the generated run summary, controls, hidden character inputs, and expandable restriction pools are buried vertically.

Phase 4 transforms Challenge Runs into a responsive **two-pane CRPG dashboard**, directly mirroring the ergonomics and high-contrast styling of the Character Builder:
- **Pragmatic, SEO-Friendly Labeling:** Clear, unambiguous naming across all controls ("Run Configuration", "Run Summary", "Generate Run", "Active Restrictions", "Major Objective") while retaining authentic Elder Scrolls aesthetic touches (Pelagiad display fonts, 3-tier frame hierarchy, parchment sheet backgrounds).
- **Tactile Run Generation & Pinning:** A prominent `[ Generate Run ]` primary action, customizable modifier count selectors, difficulty preset buttons (`Standard`, `Hardcore`, `Cursed`, `Custom`), and slot-pinning toggles (lock icons) allowing players to freeze specific rolls (e.g. keep rolled race/class while re-rolling restrictions).
- **Parchment Run Summary Sheet:** The right pane serves as the complete, legible character run dossier:
  - **Character Overview:** Race, Class, Gender, Birthsign, starting Vitals, and Favored Attributes.
  - **Major Objective Plaque:** High-contrast beveled banner detailing the primary victory condition.
  - **Active Restrictions List:** Distinct list items with clear difficulty badges (`[Easy]`, `[Medium]`, `[Hard]`, `[Grind]`), plain-English mechanics explanations, and conflict-free guarantees.
  - **Minor Objectives Checklist:** Optional checklist of secondary world milestones.
  - **Export & Action Bar:** `[ Send to Build Optimizer ]` (populates the Character Builder with the rolled build), `[ Copy Summary (Markdown) ]`, `[ Copy Permalink ]`, and `[ Print / Save Sheet ]`.

---

### 10.2 Desktop Wireframe ($\ge 1024\text{px}$)

```
+---------------------------------------------------------------------------------------------------------+
| Mode: [ Standard ] [ Hardcore ] [ Cursed ] [ Custom ]    |    Seed: [ SEED-7482-TR ]  [ Copy Link ]     |
+----------------------------------------------------+----------------------------------------------------+
| LEFT PANE: Run Configuration                       | RIGHT PANE: Run Summary Sheet                      |
| (components/challenge-runs/run-configurator.jsx)   | (components/challenge-runs/run-summary-sheet.jsx)  |
|                                                    |                                                    |
| [ === Generate Run === ] (Primary Action)          | +-- CHARACTER OVERVIEW --------------------------+ |
|                                                    | | Dark Elf Male · Assassin · The Lady            | |
| +-- Modifier Settings ---------------------------+ | | Health: 45 · Magicka: 40 · Fatigue: 195        | |
| | Restrictions Count: [ 3 v ]                    | | Favored: Agility (+10), Endurance (+10)         | |
| | Objectives Count:   [ 2 v ]                    | +------------------------------------------------+ |
| |                                                |                                                    |
| | Difficulty Filters:                            | +-- MAJOR OBJECTIVE -----------------------------+ |
| | [x] Easy (18)   [x] Medium (24)                | | Defeat Dagoth Ur without donning Wraithguard   | |
| | [x] Hard (14)   [ ] Grind (6)                  | | Complete the main quest without the artifact.  | |
| +------------------------------------------------+ | +------------------------------------------------+ |
|                                                    |                                                    |
| +-- Pinned Slots (Lock to Keep on Roll) ---------+ | +-- ACTIVE RESTRICTIONS (3) ---------------------+ |
| | [🔓] Race: [ Dark Elf        v ]               | | 1. [HARD] No Magicka                           | |
| | [🔓] Class: [ Assassin       v ]               | |    No spells or cast-on-strike items.          | |
| | [🔓] Sign: [ The Lady        v ]               | | 2. [MED]  No Fast Travel                       | |
| | [🔒] Major Objective (Locked)                  | |    No silt striders, boats, or guild guides.   | |
| +------------------------------------------------+ | | 3. [EASY] Faction Devotion                     | |
|                                                    | |    Join no guilds until level 5.               | |
| [ Advanced Pool Search (<details>) ]              | +------------------------------------------------+ |
|                                                    |                                                    |
|                                                    | +-- MINOR OBJECTIVES (2) ------------------------+ |
|                                                    | | [ ] Slay the Umbra Orc in single combat        | |
|                                                    | | [ ] Clear the smuggler cave of Addamasartus    | |
|                                                    | +------------------------------------------------+ |
|                                                    |                                                    |
|                                                    | [ Send to Build Optimizer ]  [ Copy Summary ]    |
+----------------------------------------------------+----------------------------------------------------+
```

---

### 10.3 Mobile Layout (< 1024px)
- **Single-Column Flow:** Run Configuration sits on top with a full-width `[ Generate Run ]` button and collapsible filter accordion, followed immediately by the complete Run Summary Sheet below.
- **Sticky Roll Trigger:** When scrolling down the long Run Summary Sheet, a compact bottom bar offers quick `[ 🎲 Re-roll ]` and `[ Share ]` actions without forcing the user to scroll back to the top.

---

### 10.4 Component Hierarchy & File Layout (Phase 4)

Codex should implement the new Challenge Runs components under `components/challenge-runs/`:

```
components/challenge-runs/
├── challenge-runs-root.jsx          # Top coordinator: layout grid, seed state, and optimizer bridge
├── run-configurator.jsx             # Left pane: generation controls, difficulty presets, count selectors, lock pins
├── run-summary-sheet.jsx            # Right pane: parchment card container for full run sheet
├── character-overview-card.jsx      # Race, class, sign, vitals, and favored attributes summary
├── major-objective-plaque.jsx       # Beveled plaque for primary victory condition
├── restrictions-tablet.jsx          # List of active restrictions with difficulty badges and rules notes
├── minor-objectives-checklist.jsx   # Interactive secondary world goals checklist
├── seed-bar.jsx                     # Deterministic seed display, input, and 1-click URL sharing
└── pool-browser-modal.jsx           # Full searchable reference of all objectives and restrictions
```

---

### 10.5 State & Data Flow Specification (Challenge Runs)
- **Deterministic Seed Engine (`lib/challenge-seed.mjs`):**
  - Seed encodes game profile (`vanilla`, `tr`, `arce`), locked slots, active difficulty filters, rolled character attributes, major objective, and restriction IDs.
  - Permalinks format: `#challenge:seed=V1-TR-49182A`.
  - Re-rolling with pinned slots preserves locked values while pseudo-randomly deriving replacements for unlocked slots.
- **Build Optimizer Bridge:**
  - Clicking `[ Send to Build Optimizer ]` serializes the rolled character state (Race, Gender, Class, Sign, Spec, Favored Attributes, Major/Minor Skills) directly into `siltShell.navigate('builder')` and writes the hash, seamlessly switching tabs with zero data re-entry.

---

### 10.6 Execution Checklist for Codex (Phase 4)
- [x] **Step 1:** Create `components/challenge-runs/` and scaffold the 10 components.
- [x] **Step 2:** Extract challenge randomization and constraint validation into `lib/challenge-math.mjs` (conflict detection, tag exclusion, level cap rules).
- [x] **Step 3:** Implement slot-pinning logic allowing users to lock specific rolled attributes across re-rolls.
- [x] **Step 4:** Implement two-pane desktop layout with authentic 3-tier frame styling and high-contrast parchment text.
- [x] **Step 5:** Connect `[ Send to Build Optimizer ]` bridge to pass character state into `CharacterBuilderRoot`.
- [x] **Step 6:** Run `npm test` and `npm run build` to verify 100% test passing and zero regressions.

---

## 11. Phase 5 Blueprint: The 4 Specialized Calculators (Interactive Workstations)

### 11.1 Architectural Overview
The four specialized calculators (Enchanting, Spellmaking, Alchemy, Travel) provide critical CRPG math for Morrowind theorycrafting. Currently, they exist as plain HTML input lists. 

Phase 5 transforms them into **tactile, responsive workstations** with:
1. **Direct Game File Math:** Real formulas derived from OpenMW and original Morrowind mechanics.
2. **Character Context Reactivity:** Live reading of character attributes, skills, and race powers via `useActiveCharacter()`.
3. **Barter & Economics Modules:** Accurate gold pricing and vendor ranking factoring player Personality, Mercantile, and Disposition.
4. **Authentic 3-Tier Frame Styling:** Clear visual panels with Pelagiad headings, groove dividers, and beveled controls.

---

### 11.2 Enchanting Calculator (`components/calculators/enchanting/`)

#### 1. UX & Functional Architecture
- **Item & Soul Gem Selection:**
  - Base Item Selector (Weapons, Shields, Armor, Clothing, Rings, Amulets) displaying live **Enchantment Capacity** gauge (`0 / 120` points).
  - Soul Gem Selector (Petty to Grand, Azura's Star) with creature soul sizes (`Golden Saint: 400`, `Winged Twilight: 300`, `Grand: 180`, etc.).
  - Cast Type Selector:
    - `Cast When Used`
    - `Cast When Strikes` (weapons only)
    - `Constant Effect` (automatically locked with tooltip explanation unless Soul Size $\ge 400$).
- **Effect Stack Weaver:**
  - Multi-effect rows with dynamic add/remove actions.
  - Sliders for **Magnitude (Min/Max: 1–100)**, **Duration (1–120s)**, **Area (0–50ft)**, and **Range** (`Self`, `Touch`, `Target`).
  - Total Enchantment Point calculation with multi-effect penalty:
    $$\text{Total Points} = \text{Primary Effect Points} + \sum_{i=2}^{N} (i \times \text{Effect}_i \text{ Points})$$
  - Real-time Capacity Meter with warning states: Green (within capacity), Red (exceeds capacity).
- **Crafting Success vs Enchanter Barter HUD:**
  - **Self-Enchant Chance %:**
    $$\text{Chance} = (\text{Enchant} \times 0.75 + \text{INT} \times 0.25 + \text{LUK} \times 0.1) - \text{Points} \times (7.5 - \text{Fatigue Ratio} \times 2.5)$$
  - **Enchanter NPC Barter Table:**
    - Live ranking of game enchanters across Vvardenfell and Tamriel Rebuilt.
    - Displays NPC name, settlement location, and exact bartered gold cost adjusted for player Mercantile, Personality, and Disposition.

---

### 11.3 Spellmaking Calculator (`components/calculators/spellmaking/`)

#### 1. UX & Functional Architecture
- **Grimoire & Effect Browser:**
  - Filter tabs by Magic School: `Alteration`, `Conjuration`, `Destruction`, `Illusion`, `Mysticism`, `Restoration`.
  - Search filter supporting both base game and Tamriel Rebuilt spell effects.
- **Spell Inscription Slate:**
  - Multi-effect configuration with sliders:
    - Magnitude Min and Max ($1\text{--}100$)
    - Duration ($1\text{--}120\text{ seconds}$)
    - Area of Effect ($0\text{--}50\text{ feet}$)
    - Range (`On Self`, `On Touch`, `On Target`)
  - **Magicka Cost Formula (OpenMW / Morrowind canonical):**
    $$\text{Base Cost} = \frac{(\text{Min Mag} + \text{Max Mag}) \times (\text{Duration} + 1) + \text{Area} \times 0.1}{20} \times \text{Base Effect Cost} \times \text{Range Mult}$$
- **Live Reliability & Integration HUD:**
  - **Casting Chance %:**
    $$\text{Cast %} = \left(2 \times \text{School Skill} - \text{Spell Cost} + \frac{\text{Willpower}}{5} + \frac{\text{Luck}}{10}\right) \times \left(0.75 + \frac{0.5 \times \text{Current Fatigue}}{\text{Max Fatigue}}\right)$$
  - Reliability status badge: `Guaranteed (100%)`, `Reliable (75–99%)`, `Risky (40–74%)`, `Unusable (<40%)`.
  - Action: `[ Add to Active Character Spells ]` (saves custom spell into character session).
  - Spellmaker NPC Barter Table: lists Guild spellmakers sorted by bartered gold fee.

---

### 11.4 Alchemy Calculator (`components/calculators/alchemy/`)

#### 1. UX & Functional Architecture
- **Apparatus Rack:**
  - 4 apparatus slots:
    - **Mortar and Pestle** (Required — determines base brew success and potency)
    - **Alembic** (Reduces magnitude and duration of negative/harmful effects)
    - **Retort** (Magnifies magnitude and duration of positive/beneficial effects)
    - **Calcinator** (Magnifies magnitude and duration of all effects)
  - Quality selector per slot: `Apprentice`, `Journeyman`, `Master`, `Grandmaster`, `Secret Master`.
- **4-Slot Ingredient Mixer:**
  - Ingests ingredient catalog from data bridge (`useGameData('alchemy')`).
  - Active slot cards showing ingredient name, weight, and 4 magical effects.
  - Automatic shared effect matching: matching effects between selected ingredients highlight in bright gold.
  - "Smart Filter": checkbox to show only ingredients sharing at least one effect with currently slotted items.
- **Potion Outcome Summary:**
  - Live preview of crafted potion name (customizable), icon/vial, weight, and gold value.
  - Calculated list of active effects with exact magnitude and duration based on apparatus quality and Alchemy skill.
  - **Brew Success %:**
    $$\text{Brew %} = \text{Alchemy} + \frac{\text{Intelligence}}{10} + \frac{\text{Luck}}{10}$$
- **Reverse Effect Recipe Search:**
  - Dropdown to select a desired outcome (e.g. `Restore Magicka`, `Levitate`, `Cure Blight Disease`).
  - Instantly filters ingredient combinations into optimal 2-ingredient, 3-ingredient, and 4-ingredient recipes sorted by weight and availability.

---

### 11.5 Travel Optimizer (`components/calculators/travel/`)

#### 1. UX & Functional Architecture
- **Transit Network Graph:**
  - Encapsulates all fast travel routes: Silt Striders, Ferries & Boats, Mages Guild Guides, Dunmer Propylon Chambers, and Almsivi / Divine Intervention temple teleports.
  - World profile toggle: Vvardenfell-only network vs Tamriel Rebuilt Mainland expanded network.
- **Route Query Interface:**
  - Starting Location and Destination selectors (with autocomplete search and quick-select buttons for common hubs: Seyda Neen, Balmora, Vivec, Ald'ruhn, Sadrith Mora, Old Ebonheart).
  - Optimization Criteria:
    - `Fewest Hops` (fastest transit with least transfers)
    - `Lowest Cost` (minimum Septims spent)
    - `Overland Only` (excludes magical Guild Guides and Interventions)
    - `Include Propylons` (factors Propylon Index teleport ring)
- **Turn-by-Turn Travel Itinerary:**
  - Step-by-step connection card displaying transport type icons (Silt Strider, Ship, Guild Guide, Propylon, Walking connection), operator NPC name, fare in Septims, and total trip cost/time.

---

### 11.6 Component Hierarchy & File Layout (Phase 5)

```
components/calculators/
├── enchanting/
│   ├── enchanting-calculator-root.jsx
│   ├── item-capacity-meter.jsx
│   ├── soul-gem-picker.jsx
│   ├── effect-weaver-slate.jsx
│   └── enchanter-barter-table.jsx
├── spellmaking/
│   ├── spellmaking-calculator-root.jsx
│   ├── grimoire-school-tabs.jsx
│   ├── spell-composer-slate.jsx
│   ├── cast-reliability-hud.jsx
│   └── spellmaker-barter-table.jsx
├── alchemy/
│   ├── alchemy-calculator-root.jsx
│   ├── apparatus-rack.jsx
│   ├── ingredient-crucible.jsx
│   ├── potion-outcome-card.jsx
│   └── reverse-recipe-search.jsx
└── travel/
    ├── travel-optimizer-root.jsx
    ├── transit-route-finder.jsx
    ├── transit-mode-toggles.jsx
    └── travel-itinerary-card.jsx
```

---

### 11.7 Execution Checklist for Codex (Phase 5)
- [x] **Step 1:** Scaffold `components/calculators/` and subdirectories for the 4 tools.
- [x] **Step 2:** Port formulas for Enchanting capacity, Spellmaking Magicka/cast chance, and Alchemy potency into pure utility libraries (`lib/enchant-math.mjs`, `lib/spell-math.mjs`, `lib/alchemy-math.mjs`, `lib/travel-graph.mjs`).
- [x] **Step 3:** Connect calculators to `useActiveCharacter()` so player stats automatically populate without manual re-entry.
- [x] **Step 4:** Build interactive UI controls (tactile sliders, apparatus quality pickers, route cards) using authentic 3-tier frame styling.
- [x] **Step 5:** Run automated tests (`npm test`) and verify calculations match OpenMW game outputs.

---

## 12. Phase 6 Blueprint: Character Level Simulator & Build Progression Optimizer

### 12.1 Objective & True "Build Optimizer" Strategy
In Morrowind, a character build cannot be truly evaluated or optimized solely at Level 1. Character vitality, survivability, and power evolve dynamically based on player leveling decisions:
- **The Non-Retroactive Health Dilemma:** Health gains on level up equal $\lfloor \text{Endurance} / 10 \rfloor$. Unlike modern RPGs, this gain is **not retroactive** in Morrowind; raising Endurance early yields hundreds of additional endgame Hit Points compared to raising it late.
- **Attribute Multipliers & The Misc Skill Role:** Advancing 1 level requires 10 Major or Minor skill increases. The player selects 3 attributes to raise, each gaining a $+1$ to $+5$ multiplier based on skill points gained in skills governed by that attribute during that level. However, relying solely on Major/Minor skills severely restricts multiplier potential and prematurely caps the character. **Training Miscellaneous skills (non-major/minor)** is the canonical method to secure $+5$ multipliers without burning Major/Minor level headroom.
- **The Solution:** A comprehensive **Character Level Simulator & Build Progression Optimizer** (`#panel-leveler`) that ingests the active character's starting build, simulates manual or automated leveling to any target level (up to theoretical level cap), and prescribes the exact level-by-level training regimen—including which Miscellaneous skills must be trained to hit $+5$ multipliers.
- **Pragmatic, SEO-Friendly Labeling:** High-intent terminology ("Character Level Simulator", "Build Progression Optimizer", "Attribute Multipliers", "Health Projection", "Skill Training Requirements") avoiding fantasy fluff.
- **Enabling Deep Character Vault Saves:** Establishes the canonical progression data model used in Phase 7 (Cloud Character Vault), ensuring saved builds retain full progression history, level choices, and leveled stats rather than only Level 1 presets.

---

### 12.2 Canonical Leveling Math & Progression Engine

$$\text{Level-Up Threshold} = 10 \text{ Major or Minor skill increases}$$

$$\text{Theoretical Max Level} = 1 + \left\lfloor \frac{\sum_{s \in \text{Major/Minor}} (100 - \text{BaseSkill}_s)}{10} \right\rfloor$$

$$\text{Attribute Multiplier } M = \begin{cases} 
+1 & \text{if increases} = 0 \\
+2 & \text{if } 1 \le \text{increases} \le 4 \\
+3 & \text{if } 5 \le \text{increases} \le 7 \\
+4 & \text{if } 8 \le \text{increases} \le 9 \\
+5 & \text{if increases} \ge 10
\end{cases}$$
*(Note: Luck has no governing skills and is fixed at $+1$ per level. Attributes cap strictly at 100).*

$$\text{Health Gain per Level} = \lfloor \frac{\text{New Endurance}}{10} \rfloor$$

$$\text{Total Health at Level } N = \text{Base Health} + \sum_{i=1}^{N-1} \lfloor \frac{\text{Endurance}_i}{10} \rfloor$$

$$\text{Total Magicka at Level } N = \text{Intelligence}_N \times (1 + \text{Race Mult} + \text{Sign Mult})$$

$$\text{Total Fatigue at Level } N = \text{Strength}_N + \text{Willpower}_N + \text{Agility}_N + \text{Endurance}_N$$

```typescript
interface LevelUpChoice {
  level: number;
  attributes: [
    { name: AttributeName; multiplier: 1 | 2 | 3 | 4 | 5 },
    { name: AttributeName; multiplier: 1 | 2 | 3 | 4 | 5 },
    { name: AttributeName; multiplier: 1 | 2 | 3 | 4 | 5 }
  ];
  majorMinorIncreases: Record<string, number>; // Exactly 10 points triggering the level up
  miscSkillsToTrain: Record<string, number>;   // Off-class skills trained to complete 10/10 points for +5 multipliers
  enduranceAfterLevel: number;
  healthGained: number;
}

interface LeveledCharacterData {
  version: 1;
  baseCharacter: CharacterState; // Starting Level 1 build from Character Builder
  currentLevel: number;          // e.g. 15
  targetLevel: number;           // e.g. 50 (or max theoretical)
  maxTheoreticalLevel: number;   // Calculated from starting Major/Minor skills
  history: LevelUpChoice[];      // Record of all level-ups
  attributes: Record<AttributeName, number>;
  skills: Record<string, number>; // Full 27 skills tracked up to 100
  vitals: { health: number; magicka: number; fatigue: number };
}
```

---

### 12.3 Core Functional Modules

#### 1. Dual-Mode Progression Toggle ("Stats Only" vs. "Stats & Skills")
- **"Stats Only" Mode:** Focuses on the primary character profile:
  - 8 Primary Attributes (Strength, Intelligence, Willpower, Agility, Speed, Endurance, Personality, Luck) with base, bonus, and final values.
  - Vitals gauges: Health, Magicka, Fatigue.
  - Health Growth Comparison Chart: visual curve comparing the optimized leveling path against a delayed Endurance path.
- **"Stats & Skills" Mode:** Expands into a full 27-skill progression matrix:
  - Categorized by Specialization (Combat, Magic, Stealth) and Tier (Major, Minor, Misc).
  - Displays starting skill rating, accumulated points gained across level-ups, and final rating (strictly capped at 100).
  - Highlights governing attribute linkage tags (`[END] Heavy Armor`, `[STR] Long Blade`, `[AGI] Sneak`).

#### 2. Manual Leveling Stepper
- Step-by-step level browser: navigate between Level 1 and Target Level (`[ < Prev Level ]`, `[ Level 14 -> 15 ]`, `[ Next Level > ]`).
- For each level:
  - 3 Attribute Bonus pickers with multiplier selectors (`+1` to `+5`).
  - Major/Minor skill point allocator (must total exactly 10 points to advance level).
  - Miscellaneous skill allocator.
  - Interactive validation alerts: warns if an attribute would exceed 100, if Major/Minor points do not equal 10, or if skill increases are insufficient for the chosen multiplier.

#### 3. 1-Click "Optimize Character" Buttons
- **`[ Auto-Calculate Optimal Build ]`:** Greedy solver that rushes Endurance to 100 first for maximum HP, then selects attributes according to user priority, automatically distributing skill increases.
- **`[ Rush Endurance (+5) ]`:** Dedicated +5 Endurance rush every level until 100, then balances secondary attributes.
- **`[ Triple +5 (+5/+5/+5) ]`:** Optimizes for raw attribute efficiency with three +5 bonuses per level.
- **`[ Efficient (+5/+5/+1 Luck) ]`:** Maximizes two core attributes with +5 while raising Luck by +1 every level (since Luck cannot gain multipliers).
- **`[ Reset / Clear Plan ]`:** Reverts to base Level 1 state.

#### 4. Attribute Priority Options & Archetype Detection
- Drag-and-drop or rank-ordered selector allowing the player to set custom priority order (1st to 8th) for attribute leveling.
- **"Auto-Calculate Best Build" Archetype Detection:** Inspects specialization and class skill matrix to assign optimal priority queues:
  - **Melee Tank / Warrior:** Endurance (Rush 100) $\rightarrow$ Strength $\rightarrow$ Agility $\rightarrow$ Speed $\rightarrow$ Willpower $\rightarrow$ Personality $\rightarrow$ Intelligence $\rightarrow$ Luck.
  - **Stealth / Assassin / Marksman:** Endurance $\rightarrow$ Agility $\rightarrow$ **Strength** (Critical sneak multiplier: $4\times$ melee, $2\times$ bow damage scales with $\text{STR}/50$) $\rightarrow$ **Speed** $\rightarrow$ Intelligence $\rightarrow$ Personality $\rightarrow$ Willpower $\rightarrow$ Luck.
  - **Pure Mage / Caster:** Endurance $\rightarrow$ Intelligence $\rightarrow$ Willpower $\rightarrow$ Agility $\rightarrow$ Speed $\rightarrow$ Strength $\rightarrow$ Personality $\rightarrow$ Luck.
  - **Battlemage / Spellsword:** Endurance $\rightarrow$ Strength $\rightarrow$ Intelligence $\rightarrow$ Willpower $\rightarrow$ Agility $\rightarrow$ Speed $\rightarrow$ Personality $\rightarrow$ Luck.
  - **Nightblade / Shadowcaster:** Endurance $\rightarrow$ Agility $\rightarrow$ Intelligence $\rightarrow$ **Strength** $\rightarrow$ Willpower $\rightarrow$ **Speed** $\rightarrow$ Personality $\rightarrow$ Luck.
  - **Diplomat / Merchant:** Endurance $\rightarrow$ Personality $\rightarrow$ Speed $\rightarrow$ Agility $\rightarrow$ Strength $\rightarrow$ Willpower $\rightarrow$ Intelligence $\rightarrow$ Luck.

#### 5. Level-by-Level Miscellaneous Skill Training Itinerary
- For every level in the optimized progression, the engine generates an explicit training card:
  - **Level-Up Trigger:** Major/Minor skill points allocated (totaling 10).
  - **Miscellaneous Skills to Train:** Identifies the exact off-class skills that must be trained to hit the 10-point threshold for each chosen attribute's +5 multiplier.
  - **Specific Skill Suggestions:** Recommends candidate Misc skills available to the player (e.g., *"Train Misc: Spear +6 (for +5 Endurance), Armorer +4 (for +5 Strength), Sneak or Block +10 (for +5 Agility)"*).
  - Estimated gold training cost based on trainer formulas.

#### 6. Bidirectional Character Builder Integration
- **Direct Load:** Automatically ingests active character state from `CharacterContext` (`useActiveCharacter()`).
- **Bridge Actions:**
  - `[ Load from Character Builder ]`: Syncs the active Level 1 build into the level simulator.
  - `[ Apply Leveled Build to Character Sheet ]`: Updates the active Character Builder session with the leveled attribute and skill values.
  - `[ Export Leveled Build JSON ]`: Generates portable JSON build dossier.

---

### 12.4 Desktop Wireframe ($\ge 1024\text{px}$)

```
+---------------------------------------------------------------------------------------------------------+
| Silt Strider: Character Level Simulator & Build Progression Optimizer                                   |
| Active Character: Jiub · Dark Elf Assassin · Level [ 15 v ] of 62 (Theoretical Cap)                     |
| [ View Mode: (o) Stats Only  ( ) Stats & Skills ]        [ Load Active Build ] [ Apply to Builder ]     |
+----------------------------------------------------+----------------------------------------------------+
| LEFT PANE: Leveling Optimizer & Step Itinerary     | RIGHT PANE: Leveled Character Sheet                |
| (components/level-simulator/level-step-editor.jsx) | (components/level-simulator/progression-sheet.jsx) |
|                                                    |                                                    |
| OPTIMIZATION CONTROLS:                             | +-- LEVELED VITALS (Level 15) -------------------+ |
| [ Auto-Calculate Best Build ] [ Rush Endurance +5] | | Health:  [======= 182/182 =======] (+10 HP)    | |
| [ Triple +5 (+5/+5/+5) ]      [ Reset Plan ]       | | Magicka: [======= 80/80 =========]             | |
|                                                    | | Fatigue: [======= 290/290 =======]             | |
| Attribute Priority Order:                          | +------------------------------------------------+ |
| 1. [Endurance v] 2. [Strength v] 3. [Agility v]... |                                                    |
| Target Level Slider: [=========== 15/62 =========] | +-- PRIMARY ATTRIBUTES --------------------------+ |
|                                                    | | Strength: 65 (+25)     Agility: 85 (+35)         | |
| LEVEL 15 ITINERARY CARD:                           | | Intelligence: 40       Speed: 70 (+20)           | |
| +-- Attribute Level-Up Bonuses (3/3) ------------+ | | Willpower: 30          Endurance: 100 (MAX)     | |
| | 1. Endurance: +5 (Current: 95 -> 100 MAX)      | | Personality: 55        Luck: 55 (+15)           | |
| | 2. Strength:  +5 (Current: 60 -> 65)           | +------------------------------------------------+ |
| | 3. Agility:   +5 (Current: 80 -> 85)           |                                                    |
| +------------------------------------------------+ | +-- [STATS & SKILLS MODE] 27-SKILL PROGRESSION --+ |
|                                                    | | Heavy Armor (Maj): 45 -> 55 (Endurance)        | |
| +-- Skills to Raise This Level ------------------+ | | Long Blade  (Maj): 40 -> 46 (Strength)         | |
| | Major/Minor (10 pts -> Level Up):              | | Sneak       (Min): 35 -> 40 (Agility)          | |
| |   • Heavy Armor +4 | Long Blade +6             | | Spear       (Misc): 15 -> 21 (+6 trained)      | |
| |                                                | | Armorer     (Misc): 10 -> 14 (+4 trained)      | |
| | MISCELLANEOUS SKILLS TO TRAIN (FOR 5x BONUS):  | | Block       (Misc): 15 -> 25 (+10 trained)     | |
| |   • Spear (Misc): Train +6 pts (Endurance 5x)  | +------------------------------------------------+ |
| |   • Armorer (Misc): Train +4 pts (Strength 5x) |                                                    |
| |   • Block/Sneak (Misc): Train +10 (Agility 5x) | +-- HEALTH PROJECTION CHART ---------------------+ |
| +------------------------------------------------+ | | Max Health: 485 HP (Optimal) vs 290 HP (Delayed)| |
| [ < Previous Level ]          [ Next Level > ]     | +------------------------------------------------+ |
+----------------------------------------------------+----------------------------------------------------+
```

---

### 12.5 Component Hierarchy & File Layout (Phase 6)

```
components/level-simulator/
├── level-simulator-root.jsx         # Coordinator, target level slider, mode switch, and preset actions
├── level-mode-toggle.jsx            # "Stats Only" vs. "Stats & Skills" toggle bar
├── attribute-priority-ranker.jsx    # Attribute priority order selector
├── level-step-editor.jsx            # Left pane: manual stepper and optimizer controls
├── level-itinerary-card.jsx         # Explicit training card with Major/Minor points & Misc training needed
├── progression-sheet.jsx            # Right pane: live leveled character sheet, vitals, attributes
├── health-growth-chart.jsx          # Visual comparison chart of efficient vs delayed Endurance
└── skill-progression-matrix.jsx     # Full 27-skill progression table (Stats & Skills mode)

lib/
└── level-math.mjs                   # Canonical formulas: level cap, HP growth, multiplier rules, solver
```

---

### 12.6 Execution Checklist for Codex (Phase 6)
- [x] **Step 1:** Implement `lib/level-math.mjs` with level cap calculation, Health formulas, multiplier thresholds, and the optimization solver prescribing level-by-level Major/Minor and Misc skill training.
- [x] **Step 2:** Scaffold `components/level-simulator/` with all 8 subcomponents.
- [x] **Step 3:** Implement the Dual-Mode toggle ("Stats Only" vs "Stats & Skills") and manual level stepper.
- [x] **Step 4:** Integrate 1-click optimization buttons and attribute priority ranker.
- [x] **Step 5:** Connect `level-simulator-root.jsx` to `CharacterContext` (`useActiveCharacter()`) and add `[ Level Progression Optimizer → ]` quick launch in `CharacterSheet`.
- [x] **Step 6:** Mount `#panel-leveler` into `index.html` and register `leveler` view in `migration/shell-bridge.js`.
- [x] **Step 7:** Run `npm test` and verify that all calculations match canonical OpenMW level-up logic.

---

## 13. Phase 7 Blueprint: Cloud Character Vault (Clerk + Cloudflare D1)

### 13.1 Objective & Architecture
Currently, character builds are stored solely in the user's browser `localStorage`. While fast, this limits users to a single device and risks data loss upon clearing browser cache.

Phase 7 introduces the **Cloud Character Vault**:
- **Seamless Authentication:** Clerk user authentication for secure sign-in via Google, Discord, or Email.
- **Serverless Cloud Persistence:** Cloudflare D1 (serverless SQLite at the edge) for storing character dossiers.
- **Leveled Character Persistence:** Natively stores the character's simulated level and progression history from Phase 6.
- **Offline-First Hybrid Sync:** Immediate local writes for zero UI latency, followed by asynchronous cloud sync.
- **Public Build Permalinks:** 1-click generation of public showcase URLs (`siltstrider.tools/c/<slug>`).

---

### 13.2 Cloudflare D1 Database Schema & Quota Enforcement

The edge database uses Cloudflare D1 (SQLite) with an optimized dual-format architecture (SLT1 binary BLOBs and fallback structured JSON) and a tiered quota enforcement trigger:

```sql
-- Users table: maps Clerk authentication identity
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,               -- Clerk User ID (e.g. 'user_2b...')
    email TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- User tiers & quota limits: free 5 saves, supporter/paid 25 saves
CREATE TABLE IF NOT EXISTS user_tiers (
    user_id TEXT PRIMARY KEY,
    tier TEXT NOT NULL DEFAULT 'free',  -- 'free' | 'supporter' | 'patron'
    max_saves INTEGER NOT NULL DEFAULT 5,
    max_revisions_per_save INTEGER NOT NULL DEFAULT 3,
    max_blob_bytes INTEGER NOT NULL DEFAULT 131072,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Saves table: stores builds, progression dossiers, and ingested OpenMW saves
CREATE TABLE IF NOT EXISTS saves (
    id TEXT PRIMARY KEY,               -- UUID v4
    user_id TEXT NOT NULL,             -- Foreign key to users(id)
    save_type TEXT NOT NULL,           -- 'build' | 'progression' | 'challenge' | 'omwsave'
    name TEXT NOT NULL,                -- Character name (1-100 chars)
    race TEXT NOT NULL,
    class_name TEXT NOT NULL,
    gender TEXT NOT NULL,
    birthsign TEXT NOT NULL,
    world TEXT NOT NULL,               -- 'vanilla' | 'tr'
    arce INTEGER NOT NULL DEFAULT 0,   -- 0 | 1
    level INTEGER NOT NULL DEFAULT 1,  -- Leveled character level (1–100)
    current_cell TEXT,
    gold INTEGER DEFAULT 0,
    play_time_seconds INTEGER DEFAULT 0,
    format TEXT NOT NULL DEFAULT 'binary', -- 'binary' (SLT1) | 'json'
    payload_blob BLOB,                 -- Compressed SLT1 binary payload (~1.4 KB)
    payload_json TEXT,                 -- Fallback JSON payload
    checksum TEXT,                     -- SHA-256 integrity digest
    size_bytes INTEGER NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 1,
    is_public INTEGER NOT NULL DEFAULT 0,
    share_slug TEXT UNIQUE,            -- Short URL slug for public sharing
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_saves_user_updated ON saves(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_saves_slug ON saves(share_slug);

-- Quota Enforcement Trigger: prevents inserting beyond allowed slots (5 free / 25 paid)
CREATE TRIGGER IF NOT EXISTS trg_enforce_save_quota
BEFORE INSERT ON saves
BEGIN
    SELECT RAISE(FAIL, 'Quota exceeded: user has reached maximum allowed cloud saves for their tier')
    WHERE (
        SELECT COUNT(*) FROM saves WHERE user_id = NEW.user_id
    ) >= (
        SELECT COALESCE(max_saves, 5) FROM user_tiers WHERE user_id = NEW.user_id
        UNION ALL
        SELECT 5
        LIMIT 1
    );
END;
```

---

### 13.3 API Gateway & Security Specifications (Cloudflare Worker)
- **Endpoint Routing:**
  - `GET /api/saves`: List all character saves for the authenticated user, ordered by `updated_at DESC`.
  - `POST /api/saves`: Create a new character save (enforcing the 5/25 save quota).
  - `GET /api/saves/:id`: Retrieve a specific save (returns decrypted/decompressed payload).
  - `PUT /api/saves/:id`: Update an existing save (optimistic concurrency with revision bumping).
  - `DELETE /api/saves/:id`: Delete a character save and associated revisions.
  - `POST /api/saves/:id/duplicate`: Duplicate an existing save appending `(Copy)` to the title.
  - `POST /api/saves/:id/share`: Toggle public visibility and generate `#builder&build=<token>` permalink.
  - `GET /api/entitlements`: Returns quota limits and current save usage (`count`, `limit`, `tier`).
- **Security & Authentication:**
  - Authenticated via Clerk JWT session tokens passed in `Authorization: Bearer <token>`.
  - Same-origin Worker routing (`cloudflare/worker.mjs`) compatible with Next.js static exports (`output: 'export'`).
  - Users are strictly isolated via `WHERE user_id = ?` query bindings.

---

### 13.4 UI / UX: Cloud Character Vault Workstation & Modal Portal
- **Vault Triggers:**
  - Desktop Header: `[ Cloud Vault ]` button inside `.nav-primary` and `.account-bar`.
  - Mobile Drawer: `[ Cloud Character Vault ]` quick launch link.
  - Character Builder: Direct launch button inside the Character Sheet header and Local Characters panel.
  - Global Event Bus: `window.dispatchEvent(new CustomEvent('silt-open-vault'))`.
- **Character Dossier Cards (`components/character-vault/cloud-vault-card.jsx`):**
  - Displays Character Name, Level, Race, Class, Birthsign, Cell Location, Gold, and Quest count.
  - World profile tags (`Vanilla` / `TR` / `ARCE`) and Revision counter (`Rev 1`).
  - Visual Cloud Sync indicator: `[ Cloud Synced ]` (muted brass on dark parchment).
  - Action buttons:
    - `[ Load Build → ]`: Ingests character directly into Character Builder and Level Simulator.
    - `[ Duplicate ]`: Clones build for branching progression experiments.
    - `[ Share Link ]`: Generates compact URL hash permalink.
    - `[ Export JSON ]`: Zero lock-in JSON export.
    - `[ Rename ]` and `[ Delete ]` with inline confirmation.
- **Vault Dialog & Controls (`components/character-vault/cloud-vault-modal.jsx`):**
  - **Account & Quota Status Bar:** Displays user email/tier with real-time usage gauge (`X / 5` or `X / 25` used). Capacity warning banner triggers when quota is full.
  - **Save Active Build Banner:** 1-click button saving the currently active browser build directly to the cloud.
  - **Drag-and-Drop Ingestion Dropzone:** Supports dropping native `.omwsave` binary files or exported `.json` builds directly into the vault.
  - **5 Filter Tabs:** `All`, `OpenMW Saves`, `Builds`, `Challenges`, and `Local Browser Saves`.
  - **Local-to-Cloud Migration:** `Migrate to Cloud` button converts offline `localStorage` characters into cloud saves seamlessly.
  - **CRPG Aesthetic Standards:** Canonical `--mw-border` 6px parchment window frame, `--mw-bevel` 4px buttons, `--mw-groove` dividers, Pelagiad display font, `#d4b06a` gold highlights, and `#f3e6c8` warm text. Completely free of emojis and neon colors.

---

### 13.5 Execution Checklist for Codex (Phase 7)
- [x] **Step 1:** Create Cloudflare D1 database migrations under `cloudflare/schema.sql` and `cloudflare/migrations/0002_cloud_save_vault.sql` with quota enforcement triggers.
- [x] **Step 2:** Implement Worker API route handlers in `cloudflare/routes/saves.mjs` and `cloudflare/routes/entitlements.mjs` with Clerk JWT validation.
- [x] **Step 3:** Implement SLT1 binary codec (`lib/cloud-save-codec.mjs`) and client-side OpenMW binary save parser (`lib/omwsave-parser.mjs`).
- [x] **Step 4:** Implement hybrid sync engine in `lib/character-vault.mjs` bridging localStorage and D1 API with optimistic locking.
- [x] **Step 5:** Build `use-cloud-vault.js`, `cloud-vault-card.jsx`, and `cloud-vault-modal.jsx` components.
- [x] **Step 6:** Mount `<VaultPortal />` in `components/legacy-workbench.jsx` and add cross-tool navigation hooks in header, mobile drawer, character sheet, and local saves panel.
- [x] **Step 7:** Verify with 215 passing site tests (including 10 adversarial/edge test suites in `test/cloud-vault-ui.test.js`) and headless Chrome CDP visual captures.

---

## 14. Phase 8 Blueprint: Home Hub & Tool Launcher Cards

### 14.1 Objective & SEO Strategy
The current Home view (`#panel-home`) consists of a basic list of six buttons with brief text snippets. 

Phase 8 modernizes Home into an **informative, SEO-rich tool directory and hub**:
- **Clear Information Architecture:** High-contrast headings, semantic metadata, and structured feature descriptions optimized for search discovery (targeting keywords like *"Morrowind build optimizer"*, *"Morrowind character level simulator"*, *"Morrowind challenge run generator"*, *"Morrowind alchemy calculator"*).
- **Active Character Quick-Resume:** Prominently displays the player's active or most recently edited build, enabling 1-click continuation without navigating dropdowns.
- **Responsive Card Grid (7 Tools):** Tactile CRPG cards with procedural 9-slice borders, gold accents, feature tags, and direct launch buttons.
- **Game World Profiles Guide:** Explanatory callout detailing Vanilla Vvardenfell, Tamriel Rebuilt Mainland, and ARCE balance rules.

---

### 14.2 Desktop Wireframe ($\ge 1024\text{px}$)

```
+---------------------------------------------------------------------------------------------------------+
| Silt Strider: Morrowind Character Planner & Game Calculators                                            |
| An open-source suite of planning tools for The Elder Scrolls III: Morrowind and Tamriel Rebuilt.       |
+---------------------------------------------------------------------------------------------------------+
| [ 📜 ACTIVE SESSION: Jiub · Dark Elf Assassin (Level 15, TR) ]              [ Resume Build Optimizer → ]|
+----------------------------------------------------+----------------------------------------------------+
| [ TOOL CARD: Build Optimizer ]                     | [ TOOL CARD: Character Level Simulator ]           |
| Complete 27-skill character studio. Configure      | Plan level progression, track +5 multipliers, and  |
| race, class, birthsign, and starting powers.       | maximize Health with early Endurance scaling.      |
| Tags: [ 27 Skills ] [ Gear Advisor ] [ TR Support ]| Tags: [ Level 1-78 ] [ Health Math ] [ Multipliers]|
| [ Launch Build Optimizer → ]                       | [ Launch Level Simulator → ]                       |
+----------------------------------------------------+----------------------------------------------------+
| [ TOOL CARD: Challenge Runs ]                      | [ TOOL CARD: Enchanting Calculator ]               |
| Randomized playthrough generator. Roll customized  | Item capacity math, soul gem sizing, constant      |
| restrictions and major objectives with seed links. | effect threshold, and ranked vendor barter fees.   |
| Tags: [ Custom Difficulty ] [ Permalinks ] [ Vows ]| Tags: [ Capacity Math ] [ Constant Effect ]        |
| [ Launch Challenge Runs → ]                        | [ Launch Enchanting Calculator → ]                 |
+----------------------------------------------------+----------------------------------------------------+
| [ TOOL CARD: Spellmaking Calculator ]              | [ TOOL CARD: Alchemy Calculator ]                  |
| Magicka cost formulas, casting reliability odds,   | 4-ingredient brewing simulator with automatic      |
| and spellmaker NPC barter pricing across guilds.   | shared-effect matching, apparatus quality scaling. |
| Tags: [ Magicka Cost ] [ Cast % ] [ Vendor Barter ]| Tags: [ 4 Ingredients ] [ Reverse Search ]         |
| [ Launch Spellmaking Calculator → ]                | [ Launch Alchemy Calculator → ]                    |
+----------------------------------------------------+----------------------------------------------------+
| [ TOOL CARD: Travel Optimizer ]                                                                         |
| Multi-modal route finder across silt striders, boats, guild guides, and propylon chambers.              |
| Tags: [ Fewest Hops ] [ Lowest Cost ] [ Transit ]                                                       |
| [ Launch Travel Optimizer → ]                                                                           |
+---------------------------------------------------------------------------------------------------------+
| GAME WORLD PROFILES EXPLAINED                                                                           |
| Vanilla Vvardenfell (2002) · Tamriel Rebuilt Mainland (24.11) · ARCE Balance Adjustments               |
| Switch profiles at any time in the header bar to recalculate all tool data and catalogs.                |
+---------------------------------------------------------------------------------------------------------+
```

---

### 14.3 Component Hierarchy & File Layout (Phase 8)

```
components/home-hub/
├── home-hub-root.jsx                # Main container for the home directory
├── active-session-banner.jsx        # Quick-resume banner for in-progress character
├── tool-directory-grid.jsx          # Responsive grid of 7 tool launcher cards
├── tool-launcher-card.jsx           # Individual card with title, description, tags, and action
├── world-profiles-guide.jsx         # Explanatory card on Vanilla vs TR vs ARCE
└── colophon-bulletin.jsx            # Credits, changelog snippet, and community links
```

---

### 14.4 Execution Checklist for Codex (Phase 8)
- [ ] **Step 1:** Create `components/home-hub/` and scaffold the 6 components.
- [ ] **Step 2:** Build `active-session-banner.jsx` connecting to `CharacterContext` to display the active character name, race/class, level, and direct launch button.
- [ ] **Step 3:** Implement `tool-launcher-card.jsx` with authentic 3-tier frame styling (`--mw-border` container, `--mw-groove` dividers, `--mw-bevel` action button).
- [ ] **Step 4:** Integrate structured semantic HTML (`<main>`, `<article>`, `<header>`, `<nav>`) and SEO meta tags for search visibility.
- [ ] **Step 5:** Verify responsive collapse on mobile devices (< 900px) ensuring touch targets $\ge 44\text{px}$.


