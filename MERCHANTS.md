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
vanilla    660 providers    382 trade    328 priceable    25 KB gzipped
tr        2575 providers   1530 trade   1247 priceable    98 KB gzipped
tr_arce   identical to tr, so the bundle inherits it
```

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

## 20% of traders have no stats to read

An auto-calculated NPC stores no skills and no attributes: the engine derives them from
class and level at load. That is not a gap in the extraction, because there is nothing
in the record to extract. The split is perfectly clean — **not one auto-calculated actor
has a stored Mercantile.**

| Profile | Traders | Priceable | Auto-calculated |
| --- | --- | --- | --- |
| vanilla | 382 | 328 | 54 (14%) |
| tr | 1,530 | 1,247 | 283 (18%) |

Those publish `mercantile`, `personality` and `luck` as **null**, with `autocalc: true`
and `priceable: false`. Null means the engine decides, never zero: treating it as zero
makes `npcTerm` vanish and every such merchant look maximally generous. The reference
`barterOffer` returns null for them rather than a plausible-looking wrong number.

Deriving those stats is possible with what already ships — `Races` carries per-gender
attribute values and skill bonuses, `Classes` carries favoured attributes,
specialization and major/minor skills, and each merchant here publishes its `class`,
`race`, `female` and `level`. It is not done here because it is a reimplementation of
engine code with no way to check its answers short of reading them back out of a
running game. A caller who can verify is welcome to it.

## Options and verification

```powershell
python build_merchant_catalog.py --profile tr
python build_app_bundle.py --no-merchants
python -m unittest test_merchant_catalog -v
```

Tests cover stored stats publishing, auto-calculated nulls, null skill and attribute
blocks, gold and disposition, class and race coming from the record rather than the
provider table, a creature not haggling and being priceable anyway, an auto-calculated
NPC not being, trade versus service-only flags, the raw bitfield, the flag table being
carried once, the counts separating auto-calculated from creatures, and the formula's
own weights and exemptions.

Beyond the unit tests, the reference implementation was exercised against every
priceable vanilla merchant: **0 monotonicity violations in 579** — a better haggler
never pays more or receives less.

## What this layer does not do

It does not model disposition change, bargaining attempts, or the reputation and
faction modifiers that move disposition before the formula runs; `disposition` here is
the record's base value. It does not know merchant stock or restocking, only the gold
they carry and the services they offer. It evaluates no dialogue conditions, so a
merchant who would refuse to trade with you still appears.
