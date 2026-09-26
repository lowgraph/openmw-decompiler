# Agent Path Migration Guide — OpenMW Decompiler

Date: 2026-09-26  
Branch: `portfolio/restructure`

This document defines canonical repository locations, path migrations, and operational guidelines for AI agents working in `lowgraph/openmw-decompiler`.

---

## 1. Repository Map

| Area | Canonical Path | Description |
|---|---|---|
| **Pipeline Scripts** | Root (`./`) | Rebuild orchestrator (`rebuild.py`), extraction (`extract_foundation.py`), and 16 catalog/builder scripts (`build_*.py`) |
| **SQL Schemas** | `schemas/` | Normalized SQLite relational schema definitions (`foundation_schema.sql`, `world_schema.sql`, `journal_schema.sql`, `acquisition_schema.sql`, `services_schema.sql`, `script_evidence_schema.sql`) |
| **TypeScript Contracts**| `contracts/` | Typed contract interfaces consumed by downstream applications (`*-types.ts`) |
| **Stage Documentation** | `docs/stages/` | Engineering specifications for individual pipeline stages (`ACQUISITION_INDEX.md`, `BEST_IN_SLOT.md`, etc.) |
| **Authored Policy** | `policy/` | Authored analytical policy specifications (`early-game.json`, `late-game.json`, `travel.json`, `journal-titles.json`) |
| **OpenMW Engine Dump** | `openmw_effect_dump/` | Lua mod scripts for runtime engine effect metadata extraction |
| **Item Schemas & Samples**| `items/` | Category JSON schemas and sample fixtures |
| **Automated Tests** | Root (`test_*.py`)| 22 synthetic test suites verifying all extraction and derivation stages |

---

## 2. Path Migration Table

### A. TypeScript Contracts (12 files)
| Old Path | Canonical New Path | Purpose |
|---|---|---|
| `best-in-slot-types.ts` | `contracts/best-in-slot-types.ts` | Best-in-slot recommendation types |
| `bundle-types.ts` | `contracts/bundle-types.ts` | Release bundle and manifest types |
| `catalog-types.ts` | `contracts/catalog-types.ts` | Core game catalog types |
| `faction-types.ts` | `contracts/faction-types.ts` | Faction requirement & rank types |
| `gear-rows-types.ts` | `contracts/gear-rows-types.ts` | Derived gear row recommendation types |
| `journal-progress-types.ts` | `contracts/journal-progress-types.ts` | Journal and quest progress types |
| `merchant-types.ts` | `contracts/merchant-types.ts` | Barter and merchant types |
| `place-types.ts` | `contracts/place-types.ts` | Location and place types |
| `policy-types.ts` | `contracts/policy-types.ts` | Analytical policy configuration types |
| `quest-types.ts` | `contracts/quest-types.ts` | Quest catalog types |
| `rules-types.ts` | `contracts/rules-types.ts` | Derived effect rules types |
| `travel-types.ts` | `contracts/travel-types.ts` | Transit network and route types |

### B. SQL Schemas (6 files)
| Old Path | Canonical New Path | Loader Updated |
|---|---|---|
| `foundation_schema.sql` | `schemas/foundation_schema.sql` | `extract_foundation.py` |
| `acquisition_schema.sql` | `schemas/acquisition_schema.sql` | `build_acquisition_index.py` |
| `journal_schema.sql` | `schemas/journal_schema.sql` | `build_journal_catalog.py` |
| `services_schema.sql` | `schemas/services_schema.sql` | `build_services_catalog.py` |
| `world_schema.sql` | `schemas/world_schema.sql` | `build_world_catalog.py` |
| `script_evidence_schema.sql`| `schemas/script_evidence_schema.sql`| `build_script_evidence.py` |

### C. Stage Documentation (20 files)
Moved to `docs/stages/`:
`ACQUISITION_INDEX.md`, `BEST_IN_SLOT.md`, `BUNDLE.md`, `CATALOGS.md`, `FACTIONS.md`, `FOUNDATION.md`, `ITEM_SOURCES.md`, `JOURNAL_CATALOG.md`, `JOURNAL_PROGRESS.md`, `LOCATIONS.md`, `MERCHANTS.md`, `PLACES.md`, `POLICY.md`, `QUESTS.md`, `ROWS.md`, `RULES.md`, `SCRIPT_EVIDENCE.md`, `SERVICES_CATALOG.md`, `TRAVEL.md`, `WORLD_CATALOG.md`.

---

## 3. Invariants Kept at Root

The following files deliberately remain at the repository root:
- `rebuild.py` and all 26 `build_*.py` and `extract_foundation.py` scripts.
- `REBUILD.md`: Required at root because `test_rebuild.py` line 31 explicitly reads `(ROOT/'REBUILD.md')` to verify documented pipeline commands match execution steps.
- `README.md`: Primary portfolio project overview.
- `AGENTS.md`: Multi-agent operational rules.
- `COORDINATION.md`: Multi-agent contract synchronization document.
- `HANDOFF.md`: Cold-start onboarding guide.
- `UI_TRANSFORMATION.md`: Tracked synchronization document.
- `test_*.py` (all 22 test files): Retained at root to preserve exact test runner execution and environment invariants.

---

## 4. Supported Commands & Verification

- **Run pipeline tests**:
  ```powershell
  $env:TEMP='A:\Cache'; $env:TMP='A:\Cache'; python -B -m unittest discover -s . -p "test_*.py"
  ```
- **Inspect pipeline order**: `python rebuild.py --list`
- **Rebuild slice (dry-run/help)**: `python rebuild.py --help`

---

## 5. Agent Invariants

1. **No Real-Data Rebuilds Without Instruction**: The user executes full extractions locally. Verify code and schema changes exclusively with synthetic in-memory fixtures.
2. **Canonical Paths**: Resolve all schemas from `ROOT / 'schemas' / '<name>_schema.sql'`. Never add fallback to root paths. Do not recreate schema or contract files in root.
3. **PowerShell Only**: Never use bash `&&`. Always use `;` or execute statements sequentially.
4. **Temp Isolation**: Always isolate temporary files to `A:\Cache`.
