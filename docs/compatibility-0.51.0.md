# Recorder 0.51.0 compatibility update

This update starts Recorder through UCP's existing `afterInit` event. Every
module has completed `enable()` before Recorder checks optional registrations
and installs its hooks. A module proxy can exist before its owner is ready;
checking the proxy during Recorder's earlier enable call caused Automarket's
protocol number to be `nil`. The new error includes the received value.

Checks still precede all Recorder hook installation. An unsupported adapter
disables recording with a support report; a partial installation is reported
as failed and requires a restart. Initialization cannot run twice. Disabling
Recorder before afterInit cancels its pending initialization.

## What is actually required?

Recorder needs a way to show its menus. It already uses the UI module, so UI
remains required and UCP resolves UI's own dependencies. Automarket, Legacy,
Custom Hotkeys, AI Toolkit, Ascension and Steam multiplayer are optional.
They are not added to `definition.yml` merely because Recorder recognizes them.

The required set is unchanged: **framework >=3.0.7; UI ^1.0.1**.

A separate refactor stack replaces Recorder's existing file, input, command and
save implementations with newer Files, WinProc Handler, Protocol and Map
Extensions interfaces. Those are real direct uses in that stack, not optional
module detection. Adopting it changes installation requirements and needs its
own coordinated dependency review. It is preserved separately and is not
silently included in this compatibility release.

## Included integrations

- Hotkeys can subscribe to Recorder's input transitions before startup completes.
  The copied input state stays blocked until ready and through playback, loading
  and seeking. Subscriptions remain attached to the same session input owner.
- AI Toolkit can subscribe to copied completed-tick context. It uses the existing
  tick-return hook; absent subscribers cause no extra game-state reads. A failing
  diagnostic subscriber is removed without stopping recording.
- Author configuration is copied while modules load, before AI Swapper or other
  owners transform their option tables. Validation and asset capture happen at
  the later startup boundary. The frozen configuration describes how to launch
  the same setup again, not an intermediate mutated runtime representation.
- Ascension Multiplayer 1.0.12 fixes its own `.nan` Knight count to 0. Recorder
  continues to reject non-finite settings; it never silently repairs gameplay
  options in a recording.

The optional API merges are based on Hotkeys input-state source `8dfb61e` and
Toolkit observer source `82a9cdd`. The configuration-copy fix follows `4938f68`.
Existing published preview artifacts remain intact; the earlier observer-only
0.51.0 preview is not the same package as this combined candidate. Keep the exact
artifact/fingerprint used to record a replay, not just its version number.

## Validation scope

Portable tests cover deferred initialization, Automarket registered before or
after Recorder and absent, startup rejection before patches, failure without
retry, early input subscriptions, canceled initialization, copied author options,
invalid values, tick-subscriber isolation, restore transitions and package contents.
They do not certify every third-party module, native load order or multiplayer
combination. Existing byte, configuration and replay-state guards remain active.

Before store promotion, verify native startup with Recorder alone and with the
corrected Ascension preset in both display orders. Record a short match, change
an Automarket threshold, save/end it, then replay the same package to completion.
With Hotkeys present, hold/release a local camera key around pause/seek and verify
no stale input survives restoration. Reordering a preset requires applying it;
changing files on disk requires restarting/reloading the GUI's metadata first.

Reported player-name/selection display issues and requests for more frequent
seek points remain follow-up work. This release does not increase snapshot
frequency or claim that yearly cache points are one-second snapshots.
