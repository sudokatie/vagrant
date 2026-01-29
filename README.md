# Vagrant

API exploration for people who'd rather understand the API than fight with curl.

Point at an OpenAPI spec (or just a URL), browse endpoints interactively, make requests, see what comes back. Build a mental model of the API by actually using it, not by reading documentation that may or may not reflect reality.

## Why?

Because every time you integrate a new API, you do the same dance:

1. Find the docs (if they exist)
2. Squint at example requests
3. Write throwaway curl commands
4. Get cryptic errors
5. Tweak auth headers
6. Finally get a response
7. Realize you need a value from that response to call the next endpoint
8. Repeat

Vagrant collapses this into: point, click, explore.

## Features

- **OpenAPI import** - Load specs from files or URLs
- **Interactive TUI** - Browse endpoints, build requests, view responses
- **Terminal-native** - Works over SSH, no browser required
- **Request history** - See what you've tried, replay it
- **Environments** - Switch between prod/staging/local with one keystroke
- **Multiple auth types** - Bearer, Basic, API key
- **Secure secret storage** - Optional system keychain integration

## Quick Start

```bash
# Install
pip install vagrant

# Explore an API by its OpenAPI spec
vagrant explore https://petstore.swagger.io/v2/swagger.json

# Or point at a local spec
vagrant explore ./openapi.yaml

# Quick one-off request
vagrant request GET https://api.example.com/users
```

## Usage

### Explore Mode (TUI)

```bash
vagrant explore <spec-or-url>
```

Launches an interactive terminal interface where you can:
- Browse all endpoints in a tree view
- Click to populate request parameters
- Send requests and see formatted responses
- Save interesting requests to history

### Single Request

```bash
vagrant request GET https://api.example.com/users
vagrant request POST https://api.example.com/users -d '{"name": "test"}'
vagrant request GET https://api.example.com/users -H "Authorization: Bearer TOKEN"
```

### Environments

```bash
# List environments
vagrant env list

# Set a variable
vagrant env set API_TOKEN "your-secret-token"

# Use in requests
vagrant request GET {{base_url}}/users -e production
```

## Configuration

Config lives at `~/.config/vagrant/config.yaml`:

```yaml
default_environment: production
history_limit: 1000
timeout: 30
verify_ssl: true
use_keychain: false
```

### Secure Secret Storage

Store API keys and tokens in your system's secure keychain instead of plain text:

```bash
# Check if keychain is available
vagrant env keychain-status

# Enable keychain storage
vagrant config set use_keychain true

# Secrets use the secret_ prefix
vagrant env set secret_api_key "your-api-key" -e production
```

With keychain enabled, variables prefixed with `secret_` are stored in:
- macOS Keychain
- Windows Credential Manager  
- Linux Secret Service (GNOME Keyring, KWallet)

Non-secret variables remain in YAML files for easy editing.

## License

MIT

## Author

Katie the Clawdius Prime

---

*The tool you wish you had the first time you faced an unfamiliar API.*
