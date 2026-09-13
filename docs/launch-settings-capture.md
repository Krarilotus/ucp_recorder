# Preserve author settings for replay restart

Related: [Recorder #51](https://github.com/Corax34/ucp_recorder/issues/51).

AI Swapper 1.1.0 transforms the shared `configFinal` entries in `enable`.
Recorder previously captured those runtime tables afterward, so its generated
restart profile contained AI Swapper runtime arrays instead of `aic`/`aiv`
author options. Restarting applied no custom AI configuration; AIC's saved-state
admission correctly rejected the resulting mismatch.

Recorder 0.50.33 copies normalized options when its module is loaded. Stock
UCP 3.0.7 completes the module load loop before starting the enable loop.
The same independent snapshot supplies both the replay environment identity
and the generated restart profile. Native hooks and simulation ticks are unchanged.

Reuse review: stock framework `content/ucp/code/main.lua` normalizes `configFinal`
before loading modules, then enables them in a separate loop. The existing global
JSON codec makes the independent copy; Recorder's existing settings validation
rejects nonfinite or lossy values. The framework's `.ucp-final-config-cache` is a
YAML dump for inspection, not a lossless source for this copy. AI Swapper's
`init.lua:transformConfigData` and `enable` were inspected in the installed
1.1.0 archive. No framework, AI Swapper, Legacy, scanner or owner API changes
are required. No parallel configuration loader is introduced.

Validation: portable tests execute Recorder's actual load and enable paths with
a dependency mutation between them, check nested-copy independence, generated
author options, stable environment identity, changed-option rejection and
startup failure reporting. The full local suite passed 525 tests and 6,413
subtests, with one skip. Native restart acceptance is pending for this version.
The earlier 0.50.32 native cold-load and uninterrupted combat replay results
do not certify this change. Combat backward-seek divergence remains separately
tracked in [#50](https://github.com/Corax34/ucp_recorder/issues/50).

Existing recordings retain their recorded identities. This fix does not rewrite
old manifests or automatically repair a previously transformed restart profile.
Keep their original module ZIPs and configuration; use a new recording to test
0.50.33 restart behavior.
