# Merchants and barter pricing

Run in this project's VS Code terminal, after the services catalog exists:

```powershell
python build_merchant_catalog.py
python build_app_bundle.py
```

Output goes to `A:\Cache\OpenMWFoundation\merchants\<profile>-<hash>.json`, and
`build_app_bundle.py` publishes it as the `Merchants` catalog. See `merchant-types.ts`
for the app contract and a reference `barterOffer`.

## The price is not in the files

No record anywhere says what a merchant charges. The engine works it out when you open
the barter window, from both sides' Mercantile, Luck and Personality, both fatigues,
and the merchant's disposition toward you. This catalog publishes the merchant's half;
the player's half comes from the character being planned.

```
vanilla    660 providers    382 trade    382 priceable    25 KB gzipped
tr        2575 providers   1530 trade   1530 priceable    98 KB gzipped
tr_arce   identical to tr, so the bundle inherits it
```

Every trader can be priced: the one in five whose stats the engine invents at load are
derived here the same way it does. See below.

Service names are carried once in `serviceFlags` and referenced by `servicesRaw` per
record. Eleven strings on 2,575 merchants cost more than every other field together.

## The formula, read rather than remembered

`barterFormula` carries the literals of OpenMW's `getBarterOffer`, transcribed from
`apps/openmw/mwmechanics/mechanicsmanagerimp.cpp`. That matters: writing it from
memory produced clamps that are not in the engine. What it actually does is

```
a = min(Mercantile, 100)      d = min(merchant Mercantile, 100)
b = min(0.1 x Luck, 10)       e = min(0.1 x merchant Luck, 10)
c = min(0.2 x Personality,10) f = min(0.2 x merchant Personality, 10)

pcTerm  = (disposition - 50 + a + b + c) * playerFatigueTerm
npcTerm = (d + e + f) * merchantFatigueTerm
buy     = 0.01 * (100 - 0.5 * (pcTerm - npcTerm))
sell    = 0.01 * (50  - 0.5 * (npcTerm - pcTerm))
price   = max(1, trunc(basePrice * (buying ? buy : sell)))
```

Luck is weighted half as heavily as Personality and both cap at 10, so a merchant's
Mercantile dominates. These are engine constants rather than game settings, so they are
authored and marked `source: "authored"`; the settings the formula *does* need —
`fFatigueBase`, `fFatigueMult` and the bargaining ones — are named rather than copied,
and their values are in the `GameSettings` catalog.

**Two cases never reach the arithmetic.** A zero base price stays zero. And a creature
merchant returns the base price unchanged, before the engine reads a single stat.

That second one is load-bearing and easy to miss. It is why Creeper pays face value,
which the reference implementation reproduces:

```
Creeper (CREA, haggles false)      novice and expert both trade at 1000 for a 1000g item
Ababael Timsar-Dadisun (Merc 100)  novice pays 1618 and is paid 1; expert pays 962, is paid 537
```

A creature is therefore `priceable: true` with no stats at all — its price is exactly
the base value.

**The sell price can exceed the buy price**, and that is the engine, not a mistake here.
There is no `min` between the two terms: `sell > buy` whenever the player's term beats
the merchant's by more than 50. Agrippina Herennia sells a 1,000 gold item to a maxed
haggler for 693 and buys it back for 806. That is Morrowind's long-known Mercantile
exploit, reproduced faithfully because it is what the game does.

## One trader in five stores no stats, and is derived

An auto-calculated NPC stores no skills and no attributes: the engine derives them from
class and level at load. There is nothing in the record to extract, and the split is
perfectly clean — **not one auto-calculated actor has a stored Mercantile.**

`autocalc.py` reruns the engine's own `autoCalculateAttributes` and
`autoCalculateSkills`, transcribed from `apps/openmw/mwclass/npc.cpp`, so every trader
is now priceable:

| Profile | Traders | From the record | Derived | Still unknown |
| --- | --- | --- | --- | --- |
| vanilla | 382 | 305 | 54 | **0** |
| tr | 1,530 | 1,219 | 283 | **0** |

`statsSource` says which happened. A stored value is never overwritten. `autocalc` still
reports what the record said, independently of whether a derivation succeeded, and null
on all three still means neither route worked — never that the value is zero.

### How the derivation was checked

This is engine code reimplemented outside the engine, so it needed evidence rather than
confidence. The way in: **at level 1 the `(level - 1)` terms vanish**, and autocalc
reduces to exactly what character creation produces. 94 of the user's 96 real saves are
level 1.

Across 49 distinct race/class/birthsign level-1 characters:

```
attributes exact                       32
attributes explained by birthsign only 15
attributes unexplained                  2
skill values BELOW prediction           0
skill values above prediction          55
```

The fifteen are fortify effects the save reports inside `base` — Ro'Grogu the Khajiit
Barbarian was out by Endurance +25 and Personality +25, which is precisely what his
birthsign, Lady's Favor, grants. The two residuals are partial: a Charioteer's +25 Speed
matched with a stray +2 Strength left over, and a TR birthsign the lookup did not
resolve.

The load-bearing number is the zero. Every skill disagreement is the character's value
being *higher* than predicted, and they land on `unarmored` (36), `athletics` (11) and
`acrobatics` (3) — the skills that rise from walking, running and jumping. A wrong
formula would produce values below the prediction too. It produces none.

The derived population also behaves as it should: derived Mercantile has a median of 44
against 10 for hand-authored merchants, because Bethesda wrote most shopkeepers as weak
hagglers while autocalc scales with level. That is the game's behaviour, not an artifact.

Use `--no-autocalc` to publish the nulls instead.

## Options and verification

```powershell
python build_merchant_catalog.py --profile tr
python build_app_bundle.py --no-merchants
python -m unittest test_merchant_catalog -v
```

```powershell
python -m unittest test_autocalc -v
```

Tests cover stored stats publishing, auto-calculated nulls without a reference, null
skill and attribute blocks, gold and disposition, class and race coming from the record
rather than the provider table, a creature not haggling and being priceable anyway,
trade versus service-only flags, the raw bitfield, the flag table being carried once,
the counts separating read from derived, a stored value never being overwritten, a class
the catalogs do not carry staying unknown, and the formula's own weights and exemptions.

`test_autocalc.py` pins the derivation itself: major, minor, specialised and
miscellaneous skills at level 1, how fast each rises, the 100 ceiling, level 0, the
favoured-attribute bonus, gender selection, attribute growth weighted by the skills an
attribute governs, and the level-1 equivalence the whole verification rests on.

Beyond the unit tests, the reference implementation was exercised against every
priceable vanilla merchant, derived ones included: **0 monotonicity violations in 637**
— a better haggler never pays more or receives less — and all 54 derived traders price
without error.

## What this layer does not do

It does not model disposition change, bargaining attempts, or the reputation and
faction modifiers that move disposition before the formula runs; `disposition` here is
the record's base value. It does not know merchant stock or restocking, only the gold
they carry and the services they offer. It evaluates no dialogue conditions, so a
merchant who would refuse to trade with you still appears.
