# Publishing an extension

Extensions get into the registry by pull request. CI builds and checks every
pull request, and the maintainer reviews and merges it once CI passes. Merging
publishes it. You don't need the registry to share an extension, though: anyone
can install yours from a `.tar.gz` or git URL pasted into the Extensions page's
search box.

## Before you open a pull request

1. Your extension lives in its own public git repository with an
   `extension.toml` that sets `id`, `name`, `version`, `schema_version`,
   `authors`, `description` and `repository`.
2. It packages cleanly with `extension_cli` (see "Testing locally").
3. It has a license file.

Starting from scratch? Use
[lathe-extension-template](https://github.com/paterschris/lathe-extension-template).

## Lathe-only extensions

If your extension only works in Lathe, add this to its `extension.toml`,
next to `id` and `version` (above the first `[table]`, or TOML puts it inside
that table):

```toml
requires = ["lathe"]
```

Lathe shows a "Lathe" badge on it.

Extensions that use the Lathe API (`lathe_extension_api`) must also list the
permissions they need. Lathe asks users to allow them at install time, shows
them on the extension's card, and lets users revoke them:

```toml
requires = ["lathe"]
lathe_capabilities = ["buffer:read", "buffer:write"]
```

| Capability | Allows |
|---|---|
| `buffer:read` | Reading the text, path, language and selections of the file a command was run from |
| `buffer:write` | Editing that file and changing its selections |
| `events:open` | Running when a file is opened |
| `events:save` | Running when a file is saved |
| `events:change` | Running when a file's text changes (after typing pauses) |
| `ui:status` | Showing text in the status bar and showing notifications |
| `ui:prompt` | Asking for text or a choice while a command runs |
| `tasks:spawn` | Running commands as tasks in a terminal |
| `ui:views` | Showing views, panels and file previews drawn by Lathe (API 0.2, not released yet) |
| `ui:decorations` | Highlighting and annotating text in the editor (API 0.2, not released yet) |

Lathe skips any extension that lists a
requirement it does not recognize, so unknown values are rejected by CI.

## Adding a new extension

```sh
git submodule add https://github.com/you/your-extension extensions/your-extension
```

Then add a table to `extensions.toml`:

```toml
[your-extension]
submodule = "extensions/your-extension"
version = "0.1.0"
```

If the extension is not at the root of its repository, add
`path = "relative/dir"`.

## Publishing an update

1. Bump `version` in your extension's `extension.toml` and tag the release in
   your repository.
2. Update the submodule to that commit:
   `git -C extensions/your-extension checkout <tag>`
3. Bump `version` in `extensions.toml` to match.

CI rejects a changed submodule whose version did not change, because a
published version is never rebuilt.

## Testing locally

```sh
cargo install --git https://github.com/paterschris/lathe --locked extension_cli
python3 script/registry.py validate --extension-cli ~/.cargo/bin/zed-extension
```

To try the archive in Lathe before publishing, run `extension_cli` yourself,
host `archive.tar.gz` anywhere, and paste its URL into the search box on the
Extensions page. Lathe offers to install it from the URL.

## What gets accepted

- The extension does what its description says.
- No obfuscated code and no downloads of unrelated binaries.
- Ids are lowercase kebab-case and do not impersonate another extension.
- Extensions that are already in the Zed registry are only accepted here when
  they carry a Lathe-specific change, and the description says what it is.

Listed extensions can be removed if they break these rules. Report problems
with the "Report an extension" issue template.
