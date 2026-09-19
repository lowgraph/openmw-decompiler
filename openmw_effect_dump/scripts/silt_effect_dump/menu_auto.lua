-- Dump and leave. Used only by dump_profiles.py, which launches OpenMW once per
-- profile with its own content list; the game must exit for the next run to start.
-- The plain silt_effect_dump.omwscripts never quits, so normal play is unaffected.
local core = require('openmw.core')
local dump = require('scripts.silt_effect_dump.dump')

dump.attempt('menu-auto')
if dump.done then
    core.quit()
end

return {}
