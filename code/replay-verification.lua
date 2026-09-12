-- Evidence only: these observations never supply simulation inputs. Release
-- checks trade first-divergence precision for less capture and loading work;
-- diagnostics and older recordings retain their detailed 64-tick observations.
local validation=require('code/validation')
local digest=require('code/native-hash')
local M={COMPACT='state-digest-v1'}

function M.recordingProfile()
  if not require('code/build-profile').diagnostics then return M.COMPACT end
end

function M.interval(profile)
  assert(profile==nil or profile==M.COMPACT,'Unsupported replay verification profile')
  return profile==M.COMPACT and 1024 or 64
end

function M.capture(engine,profile,time,rng,rngData,resourceData)
  local value={time=time,rng=rng or engine:rngState()}
  rngData=rngData or engine:rngData()
  if profile==M.COMPACT then
    -- Fixed native lengths (40,016 + 800 bytes) make this concatenation
    -- unambiguous. One digest covers both without serializing 200 integers.
    value.stateHash=digest.sha256(rngData..(resourceData or engine:resourceData()))
  else
    value.resources=engine:resourceState(resourceData)
    value.rngHash=digest.sha256(rngData)
  end
  return value
end

function M.validate(value,profile)
  assert(type(value)=='table','Invalid replay checkpoint')
  validation.rng(value.rng)
  if profile==M.COMPACT then validation.hash(value.stateHash,'checkpoint state hash')
  else
    validation.resources(value.resources)
    validation.hash(value.rngHash,'checkpoint RNG hash')
  end
end

return M
