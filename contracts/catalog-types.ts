/** Contract for typed catalog schema 1.1.0. IDs and keys are not display names. */
export type GameDataVersion = { world: "vanilla" | "tamriel_rebuilt"; version: string };
export type Profile = GameDataVersion & { id: "vanilla" | "tr" | "tr_arce"; arce: boolean };
export type Catalog<T> = {
  schemaVersion: "1.1.0"; snapshotId: string; profile: Profile;
  recordType: string; records: T[];
};
export type BaseRecord = {
  id: string; key: string; recordType: string; name: string;
  gameDataVersion: GameDataVersion;
  provenance: { originPlugin: string; winningPlugin: string; recordVersionId: number };
};
export type Range = { min: number; max: number };
export type EffectIdentity = {
  effectId: number; effectKey: string; name: string;
  skill: string | null; attribute: string | null;
};
export type Effect = EffectIdentity & {
  range: "self" | "touch" | "target";
  magnitude: Range; durationSeconds: number; areaFeet: number;
};
export type CastType = "cast_once" | "when_strikes" | "when_used" | "constant_effect";
export type Enchantment = BaseRecord & {
  castType: CastType; cost: number; charges: number;
  flagsRaw: number; autoCalculate: boolean; effects: Effect[];
};
export type Item = BaseRecord & {
  sourcePlugin: string; weight: number; value: number;
  model: string | null; icon: string | null; script: string | null;
};
export type Enchantable = { enchantp: number; enchantmentId: string | null };
export type Weapon = Item & Enchantable & {
  recordType: "WEAP";
  type: "SB1H" | "LB1H" | "LB2H" | "BL1H" | "BL2C" | "BL2W" | "SP2H" |
        "AX1H" | "AX2H" | "BOW" | "CROSSBOW" | "THROWN" | "ARROW" | "BOLT";
  health: number; speed: number; reach: number;
  chop: Range; slash: Range; thrust: Range; magical: boolean; silver: boolean;
};
export type BodyPart = { slot: number; male: string | null; female: string | null };
export type Armor = Item & Enchantable & {
  recordType: "ARMO"; type: string; health: number; armorRating: number; bodyParts: BodyPart[];
};
export type Clothing = Item & Enchantable & { recordType: "CLOT"; type: string; bodyParts: BodyPart[] };
/** Prose lives in the separate BookText catalog; join on `key`. */
export type Book = Item & Enchantable & { recordType: "BOOK"; isScroll: boolean; skill: string | null };
export type BookText = { key: string; text: string };
export type Potion = Item & { recordType: "ALCH"; autoCalculate: boolean; effects: Effect[] };
export type Ingredient = Item & { recordType: "INGR"; effects: (EffectIdentity & { slot: number })[] };
export type Apparatus = Item & {
  recordType: "APPA"; type: "mortar_and_pestle" | "alembic" | "calcinator" | "retort"; quality: number;
};
export type Tool = Item & { recordType: "LOCK" | "PROB" | "REPA"; quality: number; uses: number };
export type Light = Item & {
  recordType: "LIGH"; durationSeconds: number; radius: number;
  color: { r: number; g: number; b: number }; sound: string | null; flags: string[];
};
export type Miscellaneous = Item & { recordType: "MISC"; isKey: boolean };
export type Spell = BaseRecord & {
  type: "spell" | "ability" | "blight_disease" | "common_disease" | "curse" | "power";
  cost: number; flagsRaw: number; autoCalculate: boolean;
  playerStart: boolean; alwaysSucceeds: boolean; effects: Effect[];
};
export type GenderValues = { male: number; female: number };
export type Race = BaseRecord & {
  description: string; skillBonuses: { skill: string; bonus: number }[];
  attributes: Record<string, GenderValues>; height: GenderValues; weight: GenderValues;
  flagsRaw: number; playable: boolean; beast: boolean; spellIds: string[];
};
export type Specialization = "combat" | "magic" | "stealth";
export type CharacterClass = BaseRecord & {
  description: string; favoredAttributes: string[]; specialization: Specialization;
  minorSkills: string[]; majorSkills: string[]; playable: boolean; servicesRaw: number;
};
export type Birthsign = BaseRecord & { description: string; texture: string | null; spellIds: string[] };
export type Skill = BaseRecord & {
  skill: string; governingAttribute: string; specialization: Specialization;
  useValues: number[]; description: string;
};
export type Attribute = { id: string; index: number; name: string };
export type GameSetting = BaseRecord & (
  { valueType: "string"; value: string } |
  { valueType: "integer" | "float"; value: number } |
  { valueType: "unset"; value: null }
);
export type MagicEffect = BaseRecord & {
  effectId: number; school: string; baseCost: number; flagsRaw: number;
  allowSpellmaking: boolean; allowEnchanting: boolean; description: string;
  color: { r: number; g: number; b: number }; size: number; speed: number; sizeCap: number;
  assets: Record<string, string | null>;
};
