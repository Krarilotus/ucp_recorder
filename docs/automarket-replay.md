# Automarket replay adapter (0.7.0)

This adapter targets Automarket 1.1.0, protocol 1.0.0 and map-extensions 1.0.0. Recorder must load after protocol: its post-dispatch observer changes bytes used by protocol's original signature scan. Startup checks that protocol's dispatch hook is already present before installing recorder hooks. Other extension versions are not silently assumed compatible.

## Commands and ownership

Automarket's `init.lua` registers `automarket.commitSingle` as a LOCKSTEP protocol. Its 272-byte packet contains the four-byte discriminator, four-byte controlling player, 260-byte AutoMarketPlayerData and four-byte committed fee. The adapter resolves the registered discriminator through protocol's public API, stores it in the manifest, and checks it again for playback. Payload length, discriminator, owning player, fee 0..100 and all Boolean fields are validated before native scheduling. Arbitrary category 122 payloads and immediate category 121 are not enabled.

`protocols/lockstepProtocol.lua` uses `COMMAND_FIXED_RECEIVED_PARAMETER_LOCATION_ADDRESS` when inferring the received size. In both executables the address is GameSynchronyState + 0xcdc (LEA at Crusader 0x4908bb / Extreme 0x490a1b). Recorder's allocated payload buffer alone does not satisfy this callback. The adapter stages the padded packet into the native buffer for the call and restores all 1260 bytes afterwards, including on failure. The existing native inferred-size guard remains active.

The native pre/post-dispatch journal captures the settings commit and verifies its execution order and actor. Automarket's `ui/market/process.lua` performs weekly trades directly during simulation; those trades are not extra player commands and must not be injected a second time. The queue guard prevents a spectator from committing new market settings during playback while leaving this weekly simulation callback alone. Other automation extensions that generate commands need separate ownership policies.

## Starting state

Automarket registers `automarketplayerdata.bin` with Map Extensions. It includes settings, fee and fractional credit. `mapextensions/game.lua` wraps FilePackager's write entry and substitutes an extended section array; `callbacks.lua` serializes registered data into that section. Loading follows the corresponding read wrapper.

Recorder calls the public native write entry so this wrapper executes. Verification permits its five-byte jump only when Map Extensions 1.0.0 is active and the untouched sixth byte matches; other native sites retain exact checks. This is an explicit integration contract with an installed module, not proof that no other extension changed that jump. Recorder neither overwrites the wrapper nor calls its unwrapped trampoline.

## Validation and remaining limits

Automated tests cover malformed custom payloads, mismatched registrations/versions, failed callbacks, exact receive-buffer restoration, save-hook acceptance and load ordering. Both native profiles have original-binary checks. The following still require a live test in each game:

1. Record a match with enabled buy/sell settings and nonzero fees; change settings mid-match and leave through Quit Mission.
2. Confirm the starting save restores settings, fee and fractional credit, then replay to completion twice.
3. Confirm weekly purchases/sales and resource totals match, including rounding/refunds and full storage.
4. Try committing new settings during playback and confirm no extra trade/settings action occurs.

RNG and command checks do not prove complete world-state equality. Version checks do not fingerprint edited extension files. Protocol 1.0.0 logs some handler failures internally instead of propagating them; returning from dispatch proves the call happened, not that the extension accepted every action. These limits remain visible rather than being called multiplayer compatibility.
