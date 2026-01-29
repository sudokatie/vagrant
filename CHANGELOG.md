# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.4] - 2026-01-29

### Added

- **Mark endpoints as visited** (spec 4.3 compliance)
  - Endpoints show checkmark after a request is sent
  - `mark_visited()`, `is_visited()`, `get_visited_count()`, `clear_visited()` methods
  - Visual indicator in endpoint tree

- **Type-aware parameter inputs** (spec 4.3 compliance)
  - Boolean parameters use Switch widget
  - Enum parameters use Select dropdown
  - Date/datetime parameters show format hints (YYYY-MM-DD, ISO 8601)
  - Number/integer parameters show type hints
  - Email, UUID, URI formats show hints

- **Auth configuration in Request Builder** (spec 4.3 compliance)
  - Auth type selector (None, Bearer, Basic, API Key)
  - Password-masked credentials input
  - Per-request auth overrides environment auth

## [0.1.3] - 2026-01-29

### Added

- **System keychain support** (spec 6.3 compliance)
  - Secrets can be stored in system keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service)
  - Enable with `vagrant config set use_keychain true`
  - Variables prefixed with `secret_` are stored in keychain instead of YAML files
  - New `vagrant env keychain-status` command to check availability
  - Automatic fallback to YAML storage if keychain unavailable
- New `keyring` dependency for cross-platform keychain access
- 20 new tests for secrets and keychain integration

### Changed

- Test count increased from 295 to 315

## [0.1.2] - 2026-01-29

### Security

- **Secrets no longer stored in history** (spec 6.3 compliance)
  - Authorization headers redacted before storing
  - API key headers redacted (X-API-Key, api-key, etc.)
  - Cookie/Set-Cookie headers redacted
  - Any header matching secret/token/password/key/auth pattern redacted
  - Non-sensitive headers (Accept, Content-Type, etc.) preserved

### Added

- `redact_headers()` utility function for sanitizing sensitive data
- 11 new tests for header redaction

### Changed

- Test count increased from 284 to 295

## [0.1.1] - 2026-01-29

### Added

- API key authentication now supports query parameter location (in addition to header)
- Response variable substitution: `{{response.field.path}}` extracts values from last response
- Array index support in response paths: `{{response.items.0.name}}`
- Comprehensive tests for all new features

### Fixed

- History auto-cleanup now runs on CLI startup (per spec 7.2)
- API key auth correctly handles location parameter for header vs query

### Changed

- Test count increased from 225 to 284
- Non-TUI code coverage at 87%+

## [0.1.0] - 2026-01-29

### Added

- Initial release of Vagrant - API exploration for the terminal
- OpenAPI 3.0 spec parsing with full $ref resolution
- Interactive TUI with endpoint browser, request builder, response viewer
- Request history with SQLite persistence
- Environment management for switching contexts
- Multiple authentication types: Bearer, Basic, API Key
- CLI commands for single requests and config management
- Variable substitution in URLs and headers
- 225 tests

### Features

**Parser**
- OpenAPI 3.0 JSON/YAML support
- Component schema resolution
- Path and operation parsing
- Parameter and request body handling

**HTTP Client**
- Async request execution with httpx
- Timing and size capture
- Automatic JSON parsing
- SSL verification control

**TUI**
- Endpoint browser with tag grouping
- Request builder with parameter forms
- Response viewer with JSON formatting
- History panel with search
- Keyboard-driven navigation

**Storage**
- SQLite history database
- YAML environment files
- Automatic cleanup of old entries

**CLI**
- `explore` - Launch interactive TUI
- `request` - Send single HTTP request
- `history` - View request history
- `env` - Manage environments
- `config` - Manage settings

### Technical

- Python 3.10+ required
- Dependencies: httpx, textual, click, pyyaml
- Fully async HTTP layer
- Type hints throughout
