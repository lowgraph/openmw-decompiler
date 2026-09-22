Silt Strider Data Pipeline

A reproducible data pipeline that extracts, normalizes, validates, and derives structured datasets from OpenMW/Morrowind game data for "Silt Strider Tools" (https://siltstrider.tools/).

Application: "lowgraph/siltstrider.tools" (https://github.com/lowgraph/siltstrider.tools)
Live product: "siltstrider.tools" (https://siltstrider.tools/)

---

Overview

This repository is the data-engineering side of Silt Strider.

It reads approved Morrowind, OpenMW, Tamriel Rebuilt, Project Tamriel, and related plugin data and transforms those heterogeneous source files into normalized, profile-specific datasets used by the web application.

The pipeline does more than extraction.

It also models relationships between game entities, derives analytical datasets, evaluates configurable policies, records provenance, validates cross-stage consistency, and packages immutable browser-facing releases.

At a high level:

Game / plugin files
        │
        ▼
validated extraction
        │
        ▼
normalized SQLite foundation
        │
        ├──────────────┐
        ▼              ▼
typed catalogs     world models
                       │
        ┌──────────────┼────────────────┐
        ▼              ▼                ▼
 acquisition       services         journals
 evidence          & travel         & quests
        │
        └──────────────┼────────────────┘
                       ▼
              analytical policies
                       │
                       ▼
              derived datasets
                       │
                       ▼
              validated app bundle
                       │
                       ▼
                Silt Strider

The repository name reflects its origins, but the current project is better understood as an ETL and analytical data pipeline than as a simple decompiler.

---

Design goals

The pipeline is built around several principles.

Preserve provenance

Derived data should remain traceable to the extraction snapshot, game-data profile, source plugin, policy version, and—where relevant—the OpenMW engine version that produced it.

Separate evidence from judgment

Raw facts and relationships are modeled separately from authored analytical policy.

For example:

Evidence
────────
item value
location
owner
acquisition path
hostiles
lock level
merchant availability

Policy
──────
maximum purchase price
whether theft is allowed
acceptable danger
near-start locations
whether endgame gear is allowed early

Derived result
──────────────
early-game eligibility

Changing a policy therefore does not require pretending that the underlying game data changed.

Preserve uncertainty

Failure to find evidence is not automatically converted into evidence of absence.

Bounded or truncated searches can return an explicit unknown state rather than an unjustified negative conclusion.

Refuse stale or inconsistent builds

Known failure conditions should stop publication rather than remain warnings someone must remember to check manually.

Reproduce releases

Generated catalogs and application bundles are tied to the extraction snapshot from which they were derived.

Artifacts from incompatible snapshots cannot silently be combined.

---

Pipeline stages

The full rebuild currently covers the major stages below.

1. Foundation extraction

"extract_foundation.py"

Reads approved plugins and stores the source records and their provenance in a normalized SQLite foundation.

The extraction preserves original record bytes and resolves game profiles using the same ordered override model expected by the project.

Current profiles include:

- "vanilla"
- "tr"
- "tr_arce"

The foundation is described in "FOUNDATION.md" (FOUNDATION.md).

---

2. Typed catalogs

"build_catalogs.py"

Transforms resolved foundation data into application-oriented typed catalogs.

These cover core entities such as:

- races
- classes
- skills
- attributes
- spells
- magic effects
- weapons
- armor
- clothing
- ingredients
- apparatus
- books
- enchantments
- game settings

See "CATALOGS.md" (CATALOGS.md) and "catalog-types.ts".

---

3. World model

"build_world_catalog.py"

Builds normalized world relationships including:

- cells
- actors
- inventories
- placements
- leveled lists
- linked references

The world representation preserves relationships rather than eagerly expanding every possible acquisition path.

See "WORLD_CATALOG.md" (WORLD_CATALOG.md).

---

4. Journals, quests, and script evidence

The pipeline separately models journal and script information through stages such as:

- "build_journal_catalog.py"
- "build_quest_catalog.py"
- "build_script_evidence.py"

These datasets preserve quest stages, completion markers, dialogue/script evidence, and uncertainty around scripted acquisition.

See:

- "JOURNAL_CATALOG.md" (JOURNAL_CATALOG.md)
- "QUESTS.md" (QUESTS.md)
- "SCRIPT_EVIDENCE.md" (SCRIPT_EVIDENCE.md)

---

5. Acquisition evidence

"build_acquisition_index.py"

Builds bounded reverse-query structures for determining how an item can be acquired through:

- direct placements
- inventories
- leveled lists
- merchants
- scripted grants
- ownership relationships

"query_item_sources.py" combines static and scripted evidence into a unified view.

The distinction between evidence and policy is intentional: the evidence layer reports what is known before deciding whether a route is acceptable.

See:

- "ACQUISITION_INDEX.md" (ACQUISITION_INDEX.md)
- "ITEM_SOURCES.md" (ITEM_SOURCES.md)

---

6. Services, merchants, places, factions, and travel

Dedicated builders derive higher-level domain datasets:

- "build_services_catalog.py"
- "build_merchant_catalog.py"
- "build_places_catalog.py"
- "build_faction_catalog.py"
- "build_travel_catalog.py"

These convert lower-level world relationships into application-ready models for service providers, barter calculations, named places, faction progression, and transport networks.

See:

- "SERVICES_CATALOG.md" (SERVICES_CATALOG.md)
- "MERCHANTS.md" (MERCHANTS.md)
- "PLACES.md" (PLACES.md)
- "FACTIONS.md" (FACTIONS.md)
- "TRAVEL.md" (TRAVEL.md)

---

Engine-derived rules

Some behavior cannot be recovered reliably from plugin files alone.

The project therefore distinguishes between:

- information present in source data;
- behavior inferred from how content uses that data;
- behavior observed directly from OpenMW.

For magic effects, for example, content usage can provide evidence about magnitude, duration, and targeting.

Where the content is insufficient, the pipeline can retain "null" rather than invent a value.

"dump_profiles.py" launches OpenMW with the included Lua effect dumper and records runtime effect metadata that plugin files do not expose.

The rules layer then compares inference with engine-observed behavior.

This allows results to be classified as confirmed, corrected, or otherwise resolved instead of silently replacing one source with another.

See:

- "RULES.md" (RULES.md)
- "build_rules_library.py"
- "openmw_effect_dump/"

---

Analytical policy

Policy files live separately from extracted facts.

Examples include:

policy/
├── early-game.json
├── late-game.json
├── travel.json
└── journal-titles.json

This distinction matters because statements such as:

«“This item exists at location X.”»

and:

«“This item is reasonable to recommend to a new character.”»

are different kinds of information.

The first is extracted evidence.

The second is an analytical judgment derived from evidence under an explicit policy.

Policy is independently versioned, so changing a recommendation rule does not require re-extracting unchanged game data.

See "POLICY.md" (POLICY.md).

---

Derived gear recommendations

"build_gear_rows.py" produces recommendation rows for combinations of:

- equipment slot
- armor class or weapon skill
- policy toggles
- optimization objective

Candidate acquisition routes are discovered and evaluated once, then reused across policy combinations where possible.

Recommendations can distinguish between objectives such as:

- raw equipment power
- enchantment potential

The system can also expose a nearby primary option and a stronger alternative available farther away when appropriate.

See "ROWS.md" (ROWS.md).

For late-game constant-effect equipment, "build_best_in_slot_catalog.py" ranks available candidates against the priorities of each premade build.

See "BEST_IN_SLOT.md" (BEST_IN_SLOT.md).

---

Data-quality philosophy

One of the core goals of the project is to move known operational mistakes from documentation into executable guards.

The pipeline refuses conditions such as:

- stale version labels
- unlisted plugin files in approved directories
- stale engine dumps
- artifacts produced from another extraction snapshot
- partial gear runs targeting normal production output
- authored policy references that match no real entity
- unsupported engine versions for transcribed formulas
- inconsistent profile/catalog coverage
- incompatible application-bundle inputs

This turns:

"Remember to check this"

into:

"The pipeline cannot publish unless this is valid"

That behavior is documented in "REBUILD.md" (REBUILD.md).

---

Example: catching semantic data corruption

The project has uncovered several cases where syntactically valid data produced semantically incorrect downstream results.

One example involved the "INTV" field on placed references.

A loose equipment reference can use the value as the item's condition.

A container reference, however, carries the container's value—not the condition of every item stored inside it.

Treating both cases identically caused expensive equipment inside some containers to appear broken:

container INTV = 0
        │
        ▼
incorrectly applied to contained equipment
        │
        ▼
equipment appears broken
        │
        ▼
effective value becomes 0
        │
        ▼
incorrect early-game recommendation

The fix corrected the interpretation and added regression tests for both loose-item and container cases.

This kind of end-to-end data lineage is a major focus of the repository: a bad source interpretation should be traceable through every downstream transformation it affects.

---

Application bundle

"build_app_bundle.py"

Packages the pipeline's output into the versioned contract consumed by Silt Strider.

The browser-facing bundle:

- contains application-relevant catalogs only
- excludes unnecessary large payloads such as book prose
- records snapshot and profile provenance
- stores file byte counts and SHA-256 hashes
- supports inheritance between profiles
- supports record-level deltas
- has a content-derived bundle identity

For example, the "tr_arce" profile can inherit unchanged Tamriel Rebuilt catalogs while shipping only the records ARCE actually changes.

The frontend reconstructs the profile and independently validates the manifest and payloads.

See "BUNDLE.md" (BUNDLE.md).

---

Rebuilding

When upstream inputs change, the full pipeline can be run with:

python rebuild.py

The rebuild runner:

1. executes the pipeline's test suite first;
2. runs the extraction and transformation stages in dependency order;
3. stops immediately when a stage refuses its inputs;
4. records build output in rebuild logs;
5. packages the application bundle;
6. stages the bundle into the application repository;
7. performs downstream verification.

List the stages with:

python rebuild.py --list

Resume from a specific stage after fixing a refusal:

python rebuild.py --from rules

See "REBUILD.md" (REBUILD.md) before running a full rebuild against real game data.

---

Testing

Install Python dependencies with:

python -m pip install -r requirements.txt

Run the complete Python suite:

python -m unittest discover -s . -p "test_*.py"

The tests rely heavily on synthetic fixtures so core extraction and transformation behavior can be validated without repeatedly rebuilding the full installed game dataset.

Coverage includes areas such as:

- binary/plugin extraction
- override behavior
- catalog generation
- app-bundle reconstruction
- hashes and manifests
- policy validation
- acquisition paths
- condition/value calculations
- danger modeling
- travel
- factions
- merchants
- journal data
- rules derivation
- gear recommendations
- snapshot consistency
- rebuild orchestration

The application repository has its own downstream contract and regression tests as an additional consumer-side validation layer.

---

Local requirements

Running the unit tests does not require rebuilding the complete local game dataset.

A full production data rebuild requires a configured local environment containing the relevant Morrowind/OpenMW and approved mod data.

Machine-specific source locations and version labels are defined in the repository's configuration files.

The pipeline reads source game data and writes generated outputs to separate locations rather than modifying installed game files.

---

Human-directed, AI-assisted development

This repository is part of a multi-agent development workflow.

Current responsibilities are separated between:

- Claude — extraction, transformation, analytical pipeline, and data contracts
- Codex — consuming web application
- Antigravity — UI/UX transformation architecture

The agents do not share unrestricted ownership of the codebase.

The integration boundary between the data pipeline and application is the versioned bundle contract, which is independently validated on both sides.

The human-directed layer is responsible for product requirements, analytical criteria, system boundaries, research decisions, validation, and whether generated implementations are accepted and released.

See:

- "COORDINATION.md" (COORDINATION.md)
- "AGENTS.md" (AGENTS.md)
- "HANDOFF.md" (HANDOFF.md)

---

Why this repository exists separately

The application should not need to understand TES3 binary formats, plugin precedence, SQLite extraction internals, or the reasoning used to derive analytical datasets.

Likewise, the data pipeline should not need to manipulate React components or browser UI state.

The repositories therefore communicate through one explicit interface:

openmw-decompiler
        │
        │ validated application bundle
        ▼
siltstrider.tools

That separation allows extraction and application development to proceed independently while contract tests catch integration drift.

---

Related project

The application consuming this data is:

"lowgraph/siltstrider.tools" (https://github.com/lowgraph/siltstrider.tools)

Live at:

"siltstrider.tools" (https://siltstrider.tools/)
