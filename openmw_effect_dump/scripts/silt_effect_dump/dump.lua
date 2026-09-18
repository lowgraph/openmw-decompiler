-- Print the engine's magic effect table to openmw.log, one JSON object per line.
--
-- The plugin files carry only two of an effect's flags. The rest live in the engine,
-- and OpenMW exposes them through core.magic.effects.records. The Lua sandbox has no
-- io and openmw.vfs is read-only, so the log is the way out.

local core = require('openmw.core')

local MARKER = 'SILTDUMP'
local VERSION = 1
-- Every boolean the engine publishes about an effect, in the API's own names.
local FLAGS = {
    'harmful', 'continuousVfx', 'hasDuration', 'hasMagnitude', 'isAppliedOnce',
    'casterLinked', 'nonRecastable', 'hasAttribute', 'hasSkill',
    'onSelf', 'onTouch', 'onTarget', 'unreflectable',
    'allowsSpellmaking', 'allowsEnchanting', 'negativeLight',
}

local function escape(value)
    return (tostring(value)
        :gsub('\\', '\\\\'):gsub('"', '\\"')
        :gsub('\n', '\\n'):gsub('\r', '\\r'):gsub('\t', '\\t'))
end

local function number(value)
    if type(value) ~= 'number' then return 'null' end
    return string.format('%.10g', value)
end

local function boolean(value)
    if value == nil then return 'null' end
    return value and 'true' or 'false'
end

local function encode(index, effect)
    local parts = {
        '"index":' .. number(index),
        '"id":"' .. escape(effect.id) .. '"',
        '"name":"' .. escape(effect.name) .. '"',
        '"school":"' .. escape(effect.school) .. '"',
        '"baseCost":' .. number(effect.baseCost),
    }
    for _, flag in ipairs(FLAGS) do
        parts[#parts + 1] = '"' .. flag .. '":' .. boolean(effect[flag])
    end
    return '{' .. table.concat(parts, ',') .. '}'
end

local module = {}
module.done = false

-- Returns true once a complete block has been printed; safe to call repeatedly.
function module.run(context)
    if module.done then return true end
    local magic = core.magic
    local records = magic and magic.effects and magic.effects.records
    if not records then return false end
    local lines, count = {}, 0
    for index, effect in pairs(records) do
        count = count + 1
        lines[count] = encode(index, effect)
    end
    if count == 0 then return false end
    print(MARKER .. ' BEGIN ' .. VERSION .. ' ' .. context .. ' ' .. count)
    for i = 1, count do
        print(MARKER .. ' ' .. lines[i])
    end
    print(MARKER .. ' END ' .. count)
    module.done = true
    return true
end

-- Wrapped so a failure never disturbs the game; the other context still gets a turn.
function module.attempt(context)
    local ok, err = pcall(module.run, context)
    if not ok then
        print(MARKER .. ' ERROR ' .. context .. ' ' .. tostring(err))
    end
    return ok
end

return module
