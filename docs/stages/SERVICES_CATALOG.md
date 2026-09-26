# Services and travel catalogue

Run after the foundation and world builders:

```powershell
python build_services_catalog.py
python inspect_services_catalog.py
python inspect_services_catalog.py --service enchanting
python inspect_services_catalog.py --cell "interior:balmora, guild of mages"
python inspect_services_catalog.py --warnings --limit 50
```

Output: `A:\Cache\OpenMWFoundation\services\services.sqlite`.
Staging files and SQLite journals stay beside the output on A:. No dependencies
beyond Python 3.10+ are required. Inputs are opened read-only, snapshot IDs and
profile definitions are checked, and the finished output replaces the previous
version atomically. Failure leaves the published database unchanged.

Optional arguments: `--database` (foundation), `--world-database`, `--output`
(directory), and repeated `--profile vanilla`, `--profile tr`, `--profile tr_arce`.
A selected-profile build replaces the whole output, so use another directory
if you want to retain a separate build. Output must not contain either input.

## Contract

This is an indexed extraction layer for subsequent app exports and calculators.
It does not replace the world database or typed item/spell catalogs. All revision
IDs refer to the same foundation snapshot; always join using the selected profile.
The three profiles retain their separate world/version/ARCE metadata.

| Table/view | Contents |
| --- | --- |
| profiles, metadata | Profile definitions, schema and snapshot versions, coverage |
| service_flags | Named trade category and service bits |
| providers | Shared NPC/creature revisions with known service flags or destinations, provenance, raw bits and world actor stats |
| profile_providers | Profile-specific provider winners and original plugins |
| provider_services | Provider revision to known service bits |
| transport_destinations | Ordered DODT/DNAM destinations, position and rotation, once per provider revision |
| cells | Live profile cells for endpoint names, grids and regions |
| profile_destinations | Destination resolution for each profile |
| provider_locations | Direct provider placements with world reference IDs and coordinates |
| door_links | Teleport-door placement revisions, destination coordinates and original instance details |
| profile_door_links | Profile-specific destination resolution for doors |
| travel_edges | Directed transport and door links, assembled as a view |
| warnings | Source-data notices and unresolved/ambiguous destinations |

Service bits include weapon/armor/etc. trade, magic items, spell sales, training,
spellmaking, enchanting, and repair. A trade flag does not establish that a
particular inventory item is for sale. Provider records include creatures.
Actors with only unrecognized bits are not treated as service providers.

`services_raw=null` means AIDT was absent. Unknown bits are preserved in provider
rows (where applicable) and warning details. Actor `stats_json` comes from the
world catalogue; autocalculated stats remain unknown. NPC class/faction links,
base gold and stored skills are inputs to later pricing and training calculations.
Gold is not a service price. No exact prices or training limits are invented.

For stock candidates, link `providers.version_id` to world
`inventories.holder_version_id`. For declared spells, link to world
`actor_spells.actor_version_id`, then resolve the spell in the profile's typed
catalog. Neither link promises availability: equipped items, owned containers,
spell types, autocalculated spells, dialogue and scripts need further analysis.

Travel links are directed. Return routes are only present when supported by
their own source records. Provider definitions and destinations are stored once;
the view combines destinations with direct placements without expanding paths.
Door details retain locks, keys, traps and scripts remain linked through world
object definitions. These links do not imply access or safe passage.

Blank destination names use `floor(x / 8192), floor(y / 8192)` exterior grids,
including negative coordinates. Named cells resolve case-insensitively to an
interior first, or a uniquely named exterior. Ambiguous names remain unresolved.
Statuses are `resolved`, `implicit_exterior` (grid has no explicit live cell),
`missing_cell`, and `ambiguous_name`. The latter two have null destination keys.
Never assume a null target is a usable route.

## Coverage and warning review

`provider_without_direct_placement` is an informational gap: the actor may be
spawned by a list or script. It is retained without inventing a location.
`unknown_service_bits` preserves bits outside the documented service mask; these
do not enable additional services. Both notices can recur across profiles.
Destination warnings and orphan DNAM fields need individual review.

This stage covers static DODT transport and teleport doors. It does not yet cover
dialogue/script teleports, interventions, Mark/Recall, walking routes, travel
mode labels inferred from names, or character-dependent access and prices.
There is no claim that the travel graph is complete for shortest-path planning.

Format references: OpenMW's
[service enum](https://github.com/OpenMW/openmw/blob/master/components/esm3/loadnpc.hpp),
[transport decoder](https://github.com/OpenMW/openmw/blob/master/components/esm3/transport.cpp),
and [travel window](https://github.com/OpenMW/openmw/blob/master/apps/openmw/mwgui/travelwindow.cpp).

Tests: `python -B -m unittest test_services_catalog test_world_catalog test_foundation test_catalogs`.
Tests use synthetic plugins. Set `TEMP` and `TMP` to `A:\Cache` to keep their
temporary databases on A: as well.
