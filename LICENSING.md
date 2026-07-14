# Licensing — dual track / 双轨

ACGM for Codex combines mechanical plugin code with coding-governance
methodology prose. The `license` field in `.codex-plugin/plugin.json` is
`SEE LICENSING.md` and points to this mapping.

ACGM for Codex 同时包含插件机械代码与编码治理方法论文本，因此使用双轨许可证。
`.codex-plugin/plugin.json` 的 `license` 字段为 `SEE LICENSING.md`，并指向本映射。

## Path mapping / 路径归属

| Path / 路径 | License |
|---|---|
| `.codex-plugin/**` | MIT (`LICENSE-CODE`) |
| `hooks/**` | MIT (`LICENSE-CODE`) |
| `scripts/**` | MIT (`LICENSE-CODE`) |
| `bin/**` | MIT (`LICENSE-CODE`) |
| `tests/**` except `tests/manual/**` | MIT (`LICENSE-CODE`) |
| `tests/manual/**` | CC-BY-4.0 (`LICENSE-DOCS`) |
| `pyproject.toml`, `VERSION` | MIT (`LICENSE-CODE`) |
| `skills/**/SKILL.md` YAML frontmatter | MIT (`LICENSE-CODE`) |
| `skills/**/SKILL.md` prose body | CC-BY-4.0 (`LICENSE-DOCS`) |
| `skills/**/references/**` | CC-BY-4.0 (`LICENSE-DOCS`) |
| `README.md`, `README.en.md` | CC-BY-4.0 (`LICENSE-DOCS`) |
| `docs/**` | CC-BY-4.0 (`LICENSE-DOCS`) |
| `ARCHITECTURE.md`, `EVIDENCE.md`, `SECURITY.md` | CC-BY-4.0 (`LICENSE-DOCS`) |
| `CHANGELOG.md`, `CONTRIBUTING.md`, `RELEASING.md` | CC-BY-4.0 (`LICENSE-DOCS`) |
| `LICENSING.md` | CC-BY-4.0 (`LICENSE-DOCS`) |

## Notes / 说明

- The two licenses both permit modification and commercial use. CC-BY-4.0
  additionally requires attribution for the methodology and documentation.
- In practice, attributing ACGM for Codex as a whole satisfies both tracks.
- 两种许可证都允许修改与商用；方法论及文档采用的 CC-BY-4.0 另要求署名。
