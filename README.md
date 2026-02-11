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
- **GraphQL introspection** - Fetch and parse GraphQL schemas automatically
- **Interactive TUI** - Browse endpoints, build requests, view responses
- **Terminal-native** - Works over SSH, no browser required
- **Request history** - See what you've tried, replay it
- **Request chaining** - Extract response values and use in subsequent requests
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

Use `--info` to see a quick spec summary without launching the TUI:

```bash
vagrant explore --info <spec-or-url>
```

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

### Request Chaining

Extract values from responses and use them in subsequent requests:

```python
from vagrant.http import ChainContext, ExtractRule, extract_from_response, interpolate_dict

# Create a context to store variables
ctx = ChainContext()

# After a login request, extract the token
login_response = {"data": {"token": "abc123", "user": {"id": 456}}}
rules = [
    ExtractRule(name="token", path="data.token"),
    ExtractRule(name="user_id", path="data.user.id"),
]
extract_from_response(login_response, rules, ctx)

# Use in next request
headers = interpolate_dict({"Authorization": "Bearer {{token}}"}, ctx)
# => {"Authorization": "Bearer abc123"}

url = interpolate_string("/users/{{user_id}}/profile", ctx)
# => "/users/456/profile"
```

Extraction supports:
- Dot notation for nested values: `data.user.id`
- Array indexing: `items.0.name`
- Default values when path not found

### GraphQL Support

Vagrant can introspect GraphQL APIs and parse their schemas:

```python
import asyncio
from vagrant.parser import GraphQLParser, build_query

async def explore_graphql():
    parser = GraphQLParser()
    
    # Fetch schema via introspection
    spec = await parser.parse_endpoint(
        "https://api.example.com/graphql",
        headers={"Authorization": "Bearer TOKEN"}
    )
    
    # Browse available operations
    for op in spec.get_operations():
        print(f"{op.operation_type}: {op.name}")
        for arg in op.args:
            print(f"  - {arg.name}: {arg.type.display_name()}")
    
    # Build a query
    user_query = next(op for op in spec.get_operations() if op.name == "user")
    request_body = build_query(
        user_query,
        variables={"id": "123"},
        selection="id name email"
    )
    # => {"query": "query($id: ID!) { user(id: $id) { id name email } }", "variables": {"id": "123"}}

asyncio.run(explore_graphql())
```

The parser supports:
- Full introspection query with type resolution
- Queries, mutations, and subscriptions
- Input types, enums, and interfaces
- Deprecated field detection
- Automatic query building with variables

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

Katie

---

*The tool you wish you had the first time you faced an unfamiliar API.*
