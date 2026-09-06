# Recorded launch settings

From 0.25.0, each new replay stores two configuration files. `ucp-config.yml`
preserves the input file for reference; `replay-config.yml` is a generated launch
profile containing the actual loaded extensions, exact versions and order, with
their resolved options. The manifest identifies this as `settingsCapture:
resolved-v1` and stores the launch profile's SHA256 in `restartSettingsHash`.

UCP accepts table entries with `extension` and `version` in `load-order` as exact
version requirements. A string requirement such as `ui >= 1.0.0` can otherwise
select a newer installed version on a later launch. The generated profile uses
exact entries for all active modules and plugins and does not rerun dependency
selection. It is JSON, which is accepted by UCP's native YAML reader; both full
and sparse configuration sections are present.

Every extension's normalized configuration is wrapped once in `contents.value`.
The framework replaces that wrapper with the recorded options on launch. This
preserves literal nested data named `contents` that would otherwise be processed
again by UCP's recursive normalization. Missing option tables normalize to empty
tables consistently when constructing the recorded environment.

The installed YAML-to-Lua bridge is used to check the generated profile before
recording. Some quoted scalar strings are converted to numbers or booleans by
the existing bridge; strings containing a zero byte can be truncated. If a
loaded extension has introduced an option that cannot survive that conversion,
capture fails explicitly instead of promising an identical restart.
Nonfinite numbers (`.nan` / infinity) are rejected with their option path before
the JSON encoder can omit them. Correct the source option to its intended finite
value; the recorder does not silently choose gameplay settings for the user.

## Library and restart behavior

Play starts immediately when the effective environment and required extension
state match. For new recordings, differences in raw configuration formatting or
comments do not require a restart. Extension versions/order, resolved options,
framework identity and the existing Automarket compatibility checks still apply.

When a restart is required, Play queues the existing hidden helper. Exit the game
normally. After the process exits, the helper rechecks the executable, original
settings, generated profile and environment checksums, then starts the same game
with `--ucp-config-file=".../replay-config.yml"`. The normal configuration file is
not overwritten. The library selects the requested recording on the next launch.

If the generated profile is already loaded but the environment still differs,
the library asks for the recorded extension/framework versions instead of queuing
another identical restart. Missing versions are not downloaded or installed by
the helper. Changing the framework still requires installing the recorded build.

Named copies include the source launch profile and checksum. Damaged or missing
profiles cannot be loaded or restarted. Older recordings without this profile
retain the original raw-settings compatibility and restart behavior; this does
not retrofit a promise of resolved settings into old captures.

## Validation

The Lua/file tests exercise typed options, exact version and load order capture,
effective compatibility after relaunch, named-copy integrity and malformed
metadata. Windows tests execute the real helper with process waiting/launching
replaced by fakes and verify its file/hash checks and selected launch path.

`tests/framework-settings` additionally builds the unchanged production UCP
`LuaYamlParser.cpp` against Lua 5.4.6 and yaml-cpp 0.7.0, then runs the generated
profile through the actual framework JSON encoder, version matcher and option
normalizer. It checks that newer installed versions are not selected, missing
exact versions are rejected, typed/nested values survive, and coercion is refused.
Its inputs are pinned to repository commits; no full framework or game is built.

```sh
cmake -S tests/framework-settings -B build-framework-settings
cmake --build build-framework-settings --config Release
ctest --test-dir build-framework-settings -C Release --output-on-failure
```

The Windows/Linux compatibility workflow runs this check separately from the
PR release tests. Full live game exit/restart, graphics initialization and Extreme
playback still require verification. Environment matching is not yet a complete
content fingerprint: edited extension binaries/assets under unchanged versions
remain a separate engineering gap. Multiplayer playback remains unavailable.
