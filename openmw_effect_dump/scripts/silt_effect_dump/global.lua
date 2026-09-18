-- The reliable path: by the time a game is running, every record store is populated.
local dump = require('scripts.silt_effect_dump.dump')

local function attempt()
    dump.attempt('global')
end

attempt()

return {engineHandlers = {onInit = attempt, onLoad = attempt}}
