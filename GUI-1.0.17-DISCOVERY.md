# Easier discovery in GUI 1.0.17

Proposed patch versions: recorder 0.50.2.

- Find these extensions using translated topics in the search box and tag filter.
- Existing saved setups and activation rules keep their package identities and settings.

## Maintainer notes

Stable tag IDs use the GUI’s shared translations in all nine supported languages. Capability facts describe this package’s files, parsed configuration demands and options, not its family’s combined behavior. Existing dependencies, required/suggested settings and load-order conflict controls still apply. Family membership does not make members exclusive or install them automatically.

This patch is stacked on https://github.com/Corax34/ucp_recorder/pull/46 at `ad33698d22f851a3a140778a3d27972254ae6895`. Its upstream review, runtime acceptance and publication requirements remain in force.

Validation: definitions parse; unrelated manifest fields and configuration are preserved, apart from the explicit identity/path corrections above. Shared family roots and tag translations are checked against GUI 1.0.17. No game testing or release publication is claimed.
