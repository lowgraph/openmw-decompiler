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
