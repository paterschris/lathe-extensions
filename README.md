# Lathe Extensions

The extension registry for [Lathe](https://github.com/paterschris/lathe).

Lathe lists extensions from this registry next to the Zed extension registry.
Every Zed extension still works in Lathe; this registry is for extensions that
are not in Zed's registry, or that need a Lathe-specific build.

## How it works

- `extensions.toml` lists each extension: its id, the git submodule that holds
  its source, and the version to publish.
- On every merge to `main`, CI packages each version that is not already
  published with `extension_cli`, uploads the archive to the `extensions`
  GitHub release, and deploys `index.json` to GitHub Pages:
  `https://paterschris.github.io/lathe-extensions/index.json`
- Lathe reads that file, verifies each archive's sha256 before installing,
  and checks it again for updates.

There is no server. Published archives are never rebuilt: a version is
immutable once it is in the index.

## Using the registry in Lathe

Add it to your settings:

```json
{
  "extension_registries": [
    "https://paterschris.github.io/lathe-extensions/index.json"
  ]
}
```

## Publishing an extension

See [CONTRIBUTING.md](CONTRIBUTING.md).
