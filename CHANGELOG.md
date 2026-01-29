# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- 225 tests with 85%+ coverage

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
