# Live input ownership

Recorder exposes `inputStateVersion == 1`, `getInputState()` and
`observeInputTransitions(callback)` to other modules. This interface does not
change the replay format or submit any commands.

`getInputState()` is synchronous and read-only. It returns nil until startup is
ready, otherwise `{version=1, generation=integer, blocked=boolean, mode, status}`.
Consumers must recheck immediately before native dispatch, reject unavailable or
unrecognized data, and cancel pending gestures when generation changes.

Ordinary idle/recording sessions permit input. Playback remains blocked through
loading, pause, completion and failure, even when the native mode looks like
single-player. Offline multiplayer playback also remains blocked. The native
screen, text, modal, focus, player authority and synchronization checks remain
the consumer's responsibility; `blocked=false` alone never authorizes an action.

Observers run synchronously before and after world transitions, with generation
already advanced. Before callbacks run, live input is blocked. Callbacks may only
cancel their own local input: do not advance, pause, load or change Recorder's
world. A returned function unsubscribes. Observer failure aborts the transition
and leaves input blocked; all other observers still receive cancellation.

The existing session start/reset, ordinary-load and snapshot-seek owners invoke
these boundaries. Nested reset/load stays blocked throughout; no tick polling or
additional native hooks are installed. A failed transition stays blocked for the
rest of the launch because its world is uncertain.

Custom Hotkeys consumes this interface using its existing UCP Lua bridge. Native
integration and two-PC acceptance must be reported separately from component tests.
