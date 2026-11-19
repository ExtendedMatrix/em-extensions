# EM extensions — the index

The **index** of the community packages and plugins of Extended Matrix that
can be downloaded and installed (decision D-12): one `index.json`, in the form
of Blender's
[Extension Listing API v1](https://developer.blender.org/docs/features/extensions/api_listing/v1/),
which the EM tools read as a **repository** — EMStudio's *Tools ▸ Extensions…*,
EM Tools for Blender, a script with `from s3dgraphy import em`.

> **Status.** The index exists and is generated. EMStudio reads a repository
> (row X2 of the extensions plan): *Tools ▸ Extensions… ▸ Repositories ▸
> + Add repository…*, the address of an `index.json` — this one, any other, a
> `file://` URL or a shared folder — with an optional access token and «Check
> for updates at start-up»; the archive is checked against `archive_hash`
> before it is opened, the `blocklist` is respected, `[requires]` are
> installed first. The same from a script (`em.extensions.add_repository`,
> `install_from`) and the command line (`python -m s3dgraphy.extensions repo
> add|sync|install`). An https repository is read only with «Allow online
> access» on (off by default). Side-by-side versions, «Update all» and the
> archives per platform (X3) are there too (`python -m s3dgraphy.extensions
> updates|update-all|versions|use|clean`, `build --split-platforms`; this
> index may list one archive per platform of the same id and version). EM
> Tools as a client (X6): not yet. The list of the reviewed (X4) is read:
> see below. The address below is not yet served.

**Address (once published):** `https://extendedmatrix.github.io/em-extensions/index.json`

## What is in the index

Every archive the index names is **built** from its sources by the CI and
served beside the index (`index.html` lists them to download or drag into
the Extensions window). The sources are two:

| from | what |
|---|---|
| [ExtendedMatrix/em-profiles](https://github.com/ExtendedMatrix/em-profiles) `profiles/<id>/`, at the commit in `sources.lock.json` | **community packages** — data only, or data with the code that serves them (mixed) |
| this repository, `plugins/<id>/` | **plugins** — code without data |

An entry carries Blender's fields (`id`, `version`, `name`, `tagline`,
`maintainer`, `type`, `license`, `archive_url`, `archive_hash`,
`archive_size`; `em_api_min` in place of `blender_version_min`) and ours:

- `sections` — for `data` and `code`, the version and the digest of each
  (a data-only update does not touch the code's), the vocabularies the data
  carry with their licence and tier, the code's hosts, platforms,
  permissions (each with its «why») and capabilities;
- `requires` — the archive's `[requires]`, as written;
- `content_hash` — the hash over the archive's files that an installation
  keeps in `installed.json`; `archive_hash` is the hash of the zip's bytes,
  checked after the download and before opening it;
- `reviewed` — who read the code, when and in which role (`by`, `on`,
  `as`, `digest`): from `reviewed.json`, when the digest reviewed is the
  entry's **code section** (its data, for an archive with no code). A
  data-only update keeps the code's digest, so it keeps its review; a code
  changed by one byte is a code nobody has read yet.

## The list of the reviewed (row X4)

The trust in the beta is a list, not a signature (decision D-6): a plugin
is reviewed **by the editor** or **by the curators of a community package
that requires it**. `reviewed.json`:

```json
{"reviewed": [{"id": "facemesh_fit", "digest": "sha256:…", "by": "@handle",
               "as": "editor | curator:<package>", "on": "2026-11-19", "note": "…"}]}
```

A line is added with

```
python -m s3dgraphy.extensions review add dist/<id>-<version>.zip --reviewed . --by @you --as curator:<package>
```

and the CI checks it: `by` is the GitHub handle CODEOWNERS knows; `editor`
is an owner of `/reviewed.json` here; `curator:<package>` an owner of
`/profiles/<package>/` in em-profiles, the package requiring the plugin (or
being it, for a mixed package's own code); an author of `plugins/<id>/` does
not review it alone.

What the tools do with it: a code whose digest this index lists as reviewed
installs **without the trust question** and is marked verified (with who
read it) in the Extensions window, in the menus and in the log of the acts
it writes. The reviews of this index count by default; those of any other
repository only once the person turns them on for it («Fidati delle
revisioni di questo repository»). A review taken out of this list makes the
installed code «not verified» again at the next refresh: it stays
installed.

`blocklist.json` lists the ids withdrawn, with the reason the window shows;
a withdrawn id is never listed.

## How it is made

```
python tools/generate.py [--em-profiles ../em-profiles] [--check] [--lock] [--lang it]
```

1. every source folder is built with `python -m s3dgraphy.extensions build`
   — deterministic: the same folder gives the same bytes;
2. `python -m s3dgraphy.extensions server-generate` lists the archives —
   the one validator of the EM tools refuses what it refuses, and the
   repository what only a repository sees: a version of a section reused
   with another content, a vocabulary version with two contents, a
   vocabulary copied from the package that owns it, `requires` in a cycle;
3. `index.json` at the root is **committed**: a pull request shows the change
   of the index, hash by hash, to whoever reviews it. The CI runs
   `--check` and fails when the committed index is not the one the sources
   give; on `main` it publishes `dist/` to GitHub Pages.

A new version of a package in em-profiles reaches the index with a pull
request here that runs `tools/generate.py --lock` (the em-profiles commit in
`sources.lock.json`) and commits `index.json`.

## Other repositories

Anybody can serve a repository of their own — a project, a laboratory, a
NAS: put the archives in a folder and run

```
python -m s3dgraphy.extensions server-generate --repo-dir FOLDER [--html]
```

`archive_url` is then relative to the index, so the folder works the same
over HTTPS and as `file:///…/index.json` (decision D-13).

## Licences

See [LICENSING.md](LICENSING.md). Contributing a plugin:
[CONTRIBUTING.md](CONTRIBUTING.md).
