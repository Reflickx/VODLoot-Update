# VODLoot Update Distribution

This public repository is the client-facing distribution endpoint for VODLoot.

It intentionally contains **no VODLoot application source and no production release-building logic**.

Production releases are built and signed by the GitHub Actions workflow in the private `Reflickx/VODLoot` repository. That workflow publishes:

- `VODLoot-update-<version>.zip` to this repository's GitHub Releases; and
- the signed `stable.json` manifest to this repository's `main` branch **after** the release asset is available.

Clients poll:

`https://raw.githubusercontent.com/Reflickx/VODLoot-Update/main/stable.json`

Do not hand-edit `stable.json` or replace an already-published release package.
