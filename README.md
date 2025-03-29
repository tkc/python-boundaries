# Python Architecture Boundaries Checker 🛡️

[![CI Checks](https://github.com/tkc/python-boundaries/actions/workflows/lint_type_checks.yml/badge.svg)](https://github.com/tkc/python-boundaries/actions/workflows/lint_type_checks.yml)
[![Boundary Checks](https://github.com/tkc/python-boundaries/actions/workflows/boundary_checks.yml/badge.svg)](https://github.com/tkc/python-boundaries/actions/workflows/boundary_checks.yml)

Keep your Python project's architecture clean and maintainable! ✨ This GitHub Action helps enforce architectural boundaries, ensuring your layers (like in Clean Architecture or DDD) stay decoupled and dependencies flow in the right direction.

## Features 🚀

- **Define Your Architecture:** Clearly define architectural elements (layers) using simple regex patterns.
- **Enforce Dependency Rules:** Set clear rules (allow/disallow) for how elements can interact.
- **Flexible Configuration:** Use YAML or TOML for configuration (`.boundaries.yml`, `.boundaries.toml`, `ruff.toml`, or `pyproject.toml`).
- **Clear Feedback:** Get easy-to-understand violation reports directly in your PRs via GitHub Actions annotations. 📝
- **Easy Integration:** Use it as a GitHub Action in any Python repository. Plug and play! 🔌

## Usage Guide 📖

### Basic Setup

Get started quickly by adding this step to your workflow:

```yaml
name: Python Checks

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  architecture-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Check Architecture Boundaries 🏰
        uses: tkc/python-boundaries@v1 # Make sure to use the correct action path
```

### Custom Configuration ⚙️

Tailor the rules to your project's specific needs. Create a configuration file (e.g., `.boundaries.yml`) in your project root:

```yaml
# .boundaries.yml
elements:
  - type: "domain"
    pattern: 'src/domain/.*\.py$' # Regex to identify domain files
  - type: "application"
    pattern: 'src/application/.*\.py$'
  - type: "infrastructure"
    pattern: 'src/infrastructure/.*\.py$'
  - type: "presentation"
    pattern: 'src/presentation/.*\.py$'

rules:
  default: "disallow" # Disallow dependencies by default (safer!)
  specific:
    # Define allowed dependencies
    - from: "presentation"
      allow: ["application", "domain"] # Presentation can use Application & Domain
    - from: "application"
      allow: ["domain"] # Application can use Domain
    - from: "infrastructure"
      allow: ["domain", "application"] # Infrastructure can use Domain & Application
```

The action automatically finds and uses your config file!

### Non-Blocking Checks (Report Only) 🚦

Want to see violations without failing the build? Use `fail-on-error: false`:

```yaml
- name: Check Architecture (Report Only)
  uses: tkc/python-boundaries@v1
  with:
    fail-on-error: false
```

### Using Outputs for Conditional Logic 💡

Leverage the action's outputs for more advanced workflows:

```yaml
- name: Check Architecture Boundaries
  id: boundaries # Give the step an ID
  uses: tkc/python-boundaries@v1
  with:
    fail-on-error: false # Don't fail the job

- name: Summarize Violations (if any)
  if: steps.boundaries.outputs.has-violations == 'true'
  run: |
    echo "🚨 Architecture boundary violations found: ${{ steps.boundaries.outputs.violation-count }}"
    # Maybe post a comment, trigger another action, etc.
```

## Configuration Options 🛠️

Configure the checker via a file (see below).

### `elements`

Define your architectural layers:

- `type` (string, required): A unique name (e.g., "domain", "ui").
- `pattern` (string, required): Regex pattern matching file paths for this element (relative to project root).

### `rules`

Set the dependency rules:

- `default` (string, optional, "allow" or "disallow"): Default policy. `"disallow"` (recommended) means imports are forbidden unless explicitly allowed. Defaults to `"disallow"`.
- `specific` (list, optional): Rules for specific `from` elements:
  - `from` (string, required): The source element type.
  - `allow` (list of strings, optional): Element types `from` can import.
  - `disallow` (list of strings, optional): Element types `from` _cannot_ import (overrides `allow` and `default`).

**Note:** Elements can always import from themselves.

## Configuration File 📄

The action looks for config files in this order:

1.  `.boundaries.yml` or `.boundaries.yaml`
2.  `.boundaries.toml`
3.  `ruff.toml` (under `[tool.ruff.boundaries]` or `[boundaries]`)
4.  `pyproject.toml` (under `[tool.ruff.boundaries]` or `[tool.boundaries]`)

Uses a default config if none are found. Specify a custom path with the `config` input.

## Action Inputs 📥

| Input           | Description                                        | Required | Default |
| --------------- | -------------------------------------------------- | -------- | ------- |
| `path`          | Path to check (file or directory)                  | No       | `.`     |
| `config`        | Path to a custom configuration file                | No       | `""`    |
| `fail-on-error` | Whether the action should fail if violations found | No       | `true`  |

## Action Outputs 📤

| Output            | Description                                        |
| ----------------- | -------------------------------------------------- |
| `has-violations`  | Whether any violations were found (`true`/`false`) |
| `violation-count` | The total number of violations found               |

## Example: Clean Architecture 🧼

```yaml
elements:
  - type: "entities"
    pattern: 'src/domain/entities/.*\.py$'
  - type: "usecases"
    pattern: 'src/domain/usecases/.*\.py$'
  - type: "controllers"
    pattern: 'src/adapters/controllers/.*\.py$'
  - type: "presenters"
    pattern: 'src/adapters/presenters/.*\.py$'
  - type: "repositories"
    pattern: 'src/adapters/repositories/.*\.py$'
  - type: "frameworks" # e.g., Web framework, DB drivers
    pattern: 'src/frameworks/.*\.py$'

rules:
  default: "disallow" # Enforce the Dependency Rule strictly
  specific:
    # Entities depend on nothing 🧘
    - from: "entities"
      allow: []
    # Use Cases depend only on Entities 📦
    - from: "usecases"
      allow: ["entities"]
    # Controllers depend on Use Cases (and indirectly Entities) 🎮
    - from: "controllers"
      allow: ["usecases", "entities"]
    # Presenters depend only on Entities (for data transformation) 🎨
    - from: "presenters"
      allow: ["entities"]
    # Repositories depend on Entities 💾
    - from: "repositories"
      allow: ["entities"]
    # Frameworks depend on outer layers (Adapters) 🌐
    - from: "frameworks"
      allow: ["controllers", "presenters", "repositories"]
```

## License 📜

MIT
