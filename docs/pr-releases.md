# Downloadable builds for each PR

`Publish PR releases` creates a separate GitHub prerelease for every published PR head from this project's maintained repositories. Each title names the PR, module version and commit; each release contains the installable `recorder-VERSION.zip` and its SHA-256 checksum. Updating a PR creates another immutable release, preserving older test results and downloads.

PR opened, updated, reopened and ready-for-review events trigger the workflow once it is installed on the target repository's default branch. Until upstream accepts the automation, the author's fork polls the upstream PR list every five minutes; GitHub may delay scheduled runs. Manual dispatch accepts a PR number for backfilling, or an empty value for all open PRs. Existing releases are skipped.

The workflow tests each selected commit on Windows and Linux with read-only permissions. A separate job packages clean source using the publisher script from the default branch. The write-enabled publishing job verifies the artifact identity and checksum and never executes PR code or its build scripts. No shared cache or secret is passed to PR tests. The current repository allowlist covers upstream and Krarilotus's fork; expanding publication to other contributors is an explicit maintenance decision.

The fork publishes its own releases; it cannot install workflows or publish releases in Corax's repository. Links from the upstream PRs point to these fork test builds. Publishing does not merge a PR or certify live replay/multiplayer behaviour. Read the README and changelog inside each version, since earlier stages have fewer features and safeguards.

For a backfill batch, all selected Windows/Linux test jobs must pass before packaging begins. A failed test keeps that batch unpublished and is visible in Actions; dispatching one PR permits an independent retry.
