# Required state and admission API compatibility

The signed 0.50.29 bundle disabled Recorder on stock UCP 3.0.7 with AIC Tactics
0.0.7 and Map Extensions 1.1.1. `required-state.owner()` required the exact package
version 1.1.0, so it ignored the installed version 1 capture API. The related
Protocol admission adapter had the same exact-version test, and Automarket's
dependency list omitted the unchanged Protocol API in 1.1.5/1.1.6.

Recorder 0.50.30 checks the existing Map `requiredStateVersion()` and Protocol
`multiplayerAdmissionVersion()` contracts. Absent optional capabilities remain
absent; incompatible API versions or incomplete owners are rejected. AIC still
requires a valid state provider. Captured bytes, fingerprints, state digests and
admission packet validation are unchanged.

Automarket retains its explicit 1.1.0 payload adapter. Its transport/save checks
reuse `native-command.bind` and `native-save.interface`, which validate the owners'
versioned metadata and layouts; no duplicate resolver or package-version whitelist
is added. This does not relax recorded content/configuration matching.

The actual Map owner is exercised through required capture, boundary integrity
and simulation preflight with newer package versions. Protocol tests cover the
installed 1.1.6 registration and incompatible API rejection. Native stock-runtime
acceptance must be repeated with the corrected signed package; the earlier failed
startup does not establish working replay.
