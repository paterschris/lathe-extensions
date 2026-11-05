## Extension

- Id:
- Version:
- Source repository:

## Checklist

- [ ] The table name in `extensions.toml` matches `id` in the extension's `extension.toml`
- [ ] The version in `extensions.toml` matches `version` in `extension.toml`
- [ ] The submodule points at a commit on the extension's default branch or a release tag
- [ ] For an update: the version was bumped (a changed submodule with the same version fails CI)
- [ ] The extension has a license file
