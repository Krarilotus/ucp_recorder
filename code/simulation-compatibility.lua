-- Verify that known extension-owned simulation state participates in native
-- world saves. Matching configuration and RNG do not replace this requirement.
local M={}

function M.verify()
  for _,extension in ipairs(allActiveExtensions or {}) do
    if extension.name=='ucp2-legacy' then
      local legacy=modules and modules['ucp2-legacy']
      assert(legacy and legacy.simulationStateFormat==1 and type(legacy.serializeSimulationState)=='function',
        'UCP2-Legacy 2.15.2 or newer with saved simulation state is required. '..
        'Update UCP2-Legacy and install its map-extensions dependency, then record a new replay. '..
        'Older recordings did not preserve the AI attack target cycle.')
    end
  end
end

return M
