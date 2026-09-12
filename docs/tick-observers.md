# Completed-tick observers

UCP exposes another extension through read-only proxies. An integration cannot
replace `modules.recorder.recorder.onTick`. Use the public API instead:

```lua
assert(modules.recorder.tickObserverApiVersion == 1)
local token = modules.recorder:registerTickObserver(function(context)
  if not context.active then return end
  -- Inspect the completed simulation state here.
end)
-- When disabling the integration:
modules.recorder:unregisterTickObserver(token)
```

The callback runs after the existing native tick-return hook. No additional
native hook is installed. Inactive notifications close diagnostic streams on
observed session transitions. `context` contains `active`, `status`,
`singlePlayer`, `tick`, a copied `resources` array, and selected `manifest`
fields: `id`, `variant`, `snapshotHash`, `settingsHash`, `environmentHash`.
`active` is true only during a single-player recording. Callbacks should use
the tick and session identity to ignore duplicate notifications.

Recorder's mutable session and engine are never passed to extensions. Each
callback receives its own copy, so changing it affects neither Recorder nor
another listener. A failing listener is removed and reported without failing
the recording. Registration changes during dispatch take effect safely; new
listeners start with the next dispatch. At most 16 listeners may be active.
With no listeners, dispatch does not read any game state.
