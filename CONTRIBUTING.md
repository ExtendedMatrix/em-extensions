# Contributing

## A community package

It goes to [ExtendedMatrix/em-profiles](https://github.com/ExtendedMatrix/em-profiles)
(`profiles/<id>/`), with its curators; a package with code too (mixed) as
well, because its code is reviewed with its data. Once merged there, a pull
request here moves `sources.lock.json` to that commit and commits the new
`index.json` (`python tools/generate.py --lock`).

## A plugin (code without data)

A pull request that adds `plugins/<id>/`:

- the folder named as the plugin's `id`;
- `em-extension.toml` with a `[code]` section and no `[data]` (an archive
  with data is a community package, and goes to em-profiles), every
  permission with its short «why», the hosts it runs in, its wheels for
  every platform it declares;
- a line in `.github/CODEOWNERS`: `/plugins/<id>/ @you`;
- `index.json` regenerated (`python tools/generate.py`).

The CI validates it with the one validator of the EM tools and checks the
index. A plugin listed here is **not** reviewed by being listed: until its
code digest is in `reviewed.json` (row X4), the tools install it as
«not verified», with the question of trust.

## Reviewing a plugin

The editor, or a curator of a community package that requires the plugin,
reads its code and adds a line to `reviewed.json` in a pull request:

    python -m s3dgraphy.extensions review add dist/<id>-<version>.zip --reviewed . --by @you --as curator:<package>

The review is of the digest of the **code section**: a new version whose
code did not change keeps it; a new code needs a new review. An author does
not review their own plugin alone. See the README, «The list of the
reviewed».

## Withdrawing

An id goes into `blocklist.json` with its `reason` (English) and
`reason_it`; the index stops listing it and the tools will say why.

## Versions

A version is never reused: a change is a new version, of the archive and
of the section that changed. The index refuses the same version of a
section with another content.
