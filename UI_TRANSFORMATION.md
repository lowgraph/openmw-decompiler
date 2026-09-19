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
