-- Runs at the main menu, where the content files are already loaded. If the record
-- store is not ready this early, the global script picks it up when a game starts.
local dump = require('scripts.silt_effect_dump.dump')

dump.attempt('menu')

return {}
