"""CLI command definitions using Click."""

from __future__ import annotations

import asyncio
import functools
import json
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from vagrant import __version__
from vagrant.core.config import get_config_dir, get_config_value, load_config, set_config_value
from vagrant.core.errors import ConfigError, SpecParseError, VagrantError
from vagrant.http.auth import AuthConfig
from vagrant.http.client import HttpClient, HttpRequest
from vagrant.parser.openapi import parse_spec
from vagrant.storage.environments import Environment, EnvironmentManager
from vagrant.storage.history import HistoryEntry, HistoryStorage, redact_headers

console = Console()
quiet_mode = False


def output_print(*args, **kwargs):
    """Print unless in quiet mode."""
    if not quiet_mode:
        console.print(*args, **kwargs)


def handle_errors(func):
    """Decorator to handle VagrantError exceptions with proper exit codes."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SpecParseError as e:
            output_print(f"[red]Parse error:[/red] {e}")
            sys.exit(3)  # Parse error
        except ConfigError as e:
            output_print(f"[red]Config error:[/red] {e}")
            sys.exit(2)  # Config error
        except VagrantError as e:
            output_print(f"[red]Error:[/red] {e}")
            sys.exit(4)  # Network/other error
        except FileNotFoundError as e:
            output_print(f"[red]File not found:[/red] {e}")
            sys.exit(2)
        except KeyboardInterrupt:
            output_print("\n[dim]Cancelled.[/dim]")
            sys.exit(130)
    return wrapper


def parse_auth_string(auth_str: str) -> AuthConfig | None:
    """Parse auth string in format type:value.
    
    Formats:
        bearer:TOKEN
        basic:user:pass
        apikey:KEY
        apikey:header:X-API-Key:KEY
        apikey:query:api_key:KEY
    """
    if not auth_str:
        return None

    parts = auth_str.split(":", 1)
    if len(parts) < 2:
        return None

    auth_type = parts[0].lower()
    value = parts[1]

    if auth_type == "bearer":
        return AuthConfig(type="bearer", credentials={"token": value})
    elif auth_type == "basic":
        if ":" in value:
            user, password = value.split(":", 1)
            return AuthConfig(type="basic", credentials={"username": user, "password": password})
        return AuthConfig(type="basic", credentials={"username": value, "password": ""})
    elif auth_type == "apikey":
        # Check for location specifier: apikey:header:X-Key:VALUE or apikey:query:key:VALUE
        subparts = value.split(":", 2)
        if len(subparts) >= 3 and subparts[0] in ("header", "query"):
            return AuthConfig(
                type="apikey",
                credentials={"key": subparts[2], "name": subparts[1], "location": subparts[0]}
            )
        return AuthConfig(type="apikey", credentials={"key": value})

    return None


class GlobalContext:
    """Store global CLI options."""
    def __init__(self):
        self.verbose = False
        self.quiet = False
        self.env_name: str | None = None
        self.base_url: str | None = None
        self.auth: AuthConfig | None = None
        self.headers: dict[str, str] = {}
        self.timeout: int = 30
        self.verify_ssl: bool = True
        self.output_format: str = "json"


pass_context = click.make_pass_decorator(GlobalContext, ensure=True)


@click.group()
@click.version_option(version=__version__, prog_name="vagrant")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output (errors only)")
@click.option("--env", "-e", "env_name", help="Environment to use")
@click.option("--base-url", "-b", help="Override base URL")
@click.option("--auth", "-a", "auth_str", help="Auth (bearer:TOKEN, basic:user:pass, apikey:KEY)")
@click.option("--header", "-H", "headers", multiple=True, help="Add header (key:value), repeatable")
@click.option("--timeout", "-t", type=int, default=30, help="Request timeout in seconds")
@click.option("--no-verify", is_flag=True, help="Skip TLS certificate verification")
@click.option("--output", "-o", type=click.Choice(["json", "yaml", "raw"]), default="json", help="Output format")
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    quiet: bool,
    env_name: str | None,
    base_url: str | None,
    auth_str: str | None,
    headers: tuple[str, ...],
    timeout: int,
    no_verify: bool,
    output: str,
) -> None:
    """Vagrant - API Explorer.
    
    Explore any API without writing code. Point at an OpenAPI spec or URL,
    browse endpoints interactively, make requests, and understand the API.
    """
    global quiet_mode
    quiet_mode = quiet

    gctx = GlobalContext()
    gctx.verbose = verbose
    gctx.quiet = quiet
    gctx.env_name = env_name
    gctx.base_url = base_url
    gctx.auth = parse_auth_string(auth_str) if auth_str else None
    gctx.timeout = timeout
    gctx.verify_ssl = not no_verify
    gctx.output_format = output

    # Parse headers
    for h in headers:
        if ":" in h:
            key, value = h.split(":", 1)
            gctx.headers[key.strip()] = value.strip()

    ctx.obj = gctx

    # Auto-cleanup history on startup (per spec 7.2)
    try:
        config = load_config()
        storage = HistoryStorage()
        storage.cleanup(config.history_limit)
    except Exception:
        # Don't fail startup if cleanup fails
        pass


@cli.command()
@click.argument("spec_or_url")
@click.option("--info", "-i", is_flag=True, help="Show spec info without launching TUI")
@pass_context
@handle_errors
def explore(gctx: GlobalContext, spec_or_url: str, info: bool) -> None:
    """Launch TUI explorer for an API.
    
    SPEC_OR_URL can be a path to an OpenAPI spec file or a URL.
    """
    # Parse the spec
    spec = parse_spec(spec_or_url)

    # If --info flag, just show spec summary
    if info:
        output_print(f"[bold]{spec.title}[/bold] v{spec.version}")
        if spec.description:
            output_print(f"[dim]{spec.description}[/dim]")
        output_print()

        if spec.servers:
            output_print("[bold]Servers:[/bold]")
            for server in spec.servers:
                desc = f" - {server.description}" if server.description else ""
                output_print(f"  {server.url}{desc}")
            output_print()

        output_print(f"[bold]Operations:[/bold] {len(spec.operations)} endpoints")
        output_print()

        tags: dict[str, list] = {}
        for op in spec.operations:
            tag = op.tags[0] if op.tags else "default"
            if tag not in tags:
                tags[tag] = []
            tags[tag].append(op)

        for tag, ops in sorted(tags.items()):
            output_print(f"[bold cyan]{tag}[/bold cyan]")
            for op in ops:
                method_colors = {
                    "GET": "green",
                    "POST": "blue",
                    "PUT": "yellow",
                    "PATCH": "yellow",
                    "DELETE": "red",
                }
                color = method_colors.get(op.method, "white")
                output_print(f"  [{color}]{op.method:7}[/{color}] {op.path}")
        return

    # Load environment if specified
    env = None
    env_mgr = EnvironmentManager()
    config = load_config()

    if gctx.env_name:
        env = env_mgr.get(gctx.env_name)
    elif config.default_environment and env_mgr.exists(config.default_environment):
        env = env_mgr.get(config.default_environment)

    # Launch TUI
    from vagrant.tui.app import run_app
    run_app(spec, env)


@cli.command("import")
@click.argument("spec_file")
@click.option("--name", "-n", help="Name for the cached spec (defaults to filename)")
@pass_context
@handle_errors
def import_spec(gctx: GlobalContext, spec_file: str, name: str | None) -> None:
    """Import and cache an OpenAPI spec.
    
    SPEC_FILE is a path to an OpenAPI spec file (JSON or YAML).
    """
    path = Path(spec_file)
    if not path.exists():
        raise SpecParseError(f"File not found: {spec_file}")

    # Parse to validate
    spec = parse_spec(spec_file)

    # Determine cache name
    cache_name = name or path.stem

    # Cache directory
    cache_dir = get_config_dir() / "specs"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Copy spec to cache
    cache_path = cache_dir / f"{cache_name}.yaml"

    # Read and re-save as YAML for consistency
    content = path.read_text()
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        data = json.loads(content)

    with open(cache_path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False)

    output_print(f"[green]Imported '{spec.title}' as '{cache_name}'[/green]")
    output_print(f"[dim]Cached at: {cache_path}[/dim]")
    output_print(f"[dim]Use with: vagrant explore {cache_name}[/dim]")


@cli.command("request")
@click.argument("method")
@click.argument("url")
@click.option("--data", "-d", help="Request body (JSON)")
@click.option("--no-history", is_flag=True, help="Don't save to history")
@pass_context
@handle_errors
def request_cmd(
    gctx: GlobalContext,
    method: str,
    url: str,
    data: str | None,
    no_history: bool,
) -> None:
    """Make a single HTTP request.
    
    METHOD is the HTTP method (GET, POST, PUT, DELETE, etc.).
    URL is the full URL or path (if base_url is set).
    """
    config = load_config()

    # Load environment if specified
    env = None
    env_mgr = EnvironmentManager()
    env_name = gctx.env_name

    if env_name:
        env = env_mgr.get(env_name)
    elif config.default_environment and env_mgr.exists(config.default_environment):
        env = env_mgr.get(config.default_environment)
        env_name = config.default_environment

    # Build client with global options
    client = HttpClient(
        timeout=gctx.timeout,
        verify_ssl=gctx.verify_ssl,
    )

    # Apply base URL (priority: CLI > env > config)
    if gctx.base_url:
        client.set_base_url(gctx.base_url)
    elif env and env.base_url:
        client.set_base_url(env.base_url)

    # Apply auth (priority: CLI > env)
    if gctx.auth:
        client.set_auth(gctx.auth)
    elif env and env.auth:
        client.set_auth(env.auth)

    # Substitute variables in URL
    if env:
        url = env_mgr.substitute(url, env)

    # Merge headers (env + global)
    headers = dict(gctx.headers)

    # Parse body
    body = None
    if data:
        try:
            body = json.loads(data)
        except json.JSONDecodeError:
            body = data  # Use as raw string

    # Build request
    req = HttpRequest(
        method=method.upper(),  # type: ignore
        url=url,
        headers=headers,
        body=body,
    )

    # Execute
    async def do_request():
        return await client.send(req)

    response = asyncio.run(do_request())

    # Check for HTTP errors (exit code 1)
    if response.is_error:
        exit_code = 1
    else:
        exit_code = 0

    # Display response based on output format
    if gctx.quiet:
        # Quiet mode: just output body for piping
        if isinstance(response.body, (dict, list)):
            if gctx.output_format == "yaml":
                print(yaml.safe_dump(response.body, default_flow_style=False))
            else:
                print(json.dumps(response.body))
        else:
            print(response.body or "")
    else:
        # Normal output
        status_color = "green" if response.is_success else "red"
        output_print(
            f"[{status_color}]{response.status_code} {response.status_text}[/{status_color}] "
            f"[dim]({response.elapsed_ms:.0f}ms, {response.size_bytes} bytes)[/dim]"
        )
        output_print()

        # Display headers if verbose
        if gctx.verbose:
            output_print("[bold]Response Headers:[/bold]")
            for key, value in response.headers.items():
                output_print(f"  {key}: {value}")
            output_print()

        # Display body
        if response.body:
            if gctx.output_format == "raw":
                output_print(str(response.body))
            elif gctx.output_format == "yaml" and isinstance(response.body, (dict, list)):
                output_print(yaml.safe_dump(response.body, default_flow_style=False))
            elif isinstance(response.body, (dict, list)):
                json_str = json.dumps(response.body, indent=2)
                syntax = Syntax(json_str, "json", theme="monokai")
                output_print(syntax)
            else:
                output_print(response.body)

    # Save to history (redact sensitive headers per spec 6.3)
    if not no_history:
        from datetime import datetime
        storage = HistoryStorage()
        entry = HistoryEntry(
            id=None,
            timestamp=datetime.now(),
            method=method.upper(),
            url=url,
            headers=redact_headers(headers),
            params={},
            body=data,
            status_code=response.status_code,
            response_body=json.dumps(response.body) if isinstance(response.body, (dict, list)) else str(response.body),
            elapsed_ms=response.elapsed_ms,
            environment=env_name,
        )
        storage.add(entry)

    if exit_code != 0:
        sys.exit(exit_code)


@cli.command()
@click.option("--limit", "-n", default=20, help="Number of entries to show")
@click.option("--search", "-s", help="Search by URL or method")
@pass_context
@handle_errors
def history(gctx: GlobalContext, limit: int, search: str | None) -> None:
    """Show request history."""
    storage = HistoryStorage()

    if search:
        entries = storage.search(search)[:limit]
    else:
        entries = storage.list(limit=limit)

    if not entries:
        output_print("[dim]No history entries found.[/dim]")
        return

    table = Table(title=f"Request History (last {len(entries)})")
    table.add_column("ID", style="dim")
    table.add_column("Time", style="dim")
    table.add_column("Method")
    table.add_column("URL")
    table.add_column("Status")
    table.add_column("Time")

    method_colors = {
        "GET": "green",
        "POST": "blue",
        "PUT": "yellow",
        "PATCH": "yellow",
        "DELETE": "red",
    }

    for entry in entries:
        color = method_colors.get(entry.method, "white")
        status_color = "green" if 200 <= entry.status_code < 300 else "red"

        # Truncate URL if too long
        url = entry.url
        if len(url) > 50:
            url = url[:47] + "..."

        table.add_row(
            str(entry.id),
            entry.timestamp.strftime("%H:%M:%S"),
            f"[{color}]{entry.method}[/{color}]",
            url,
            f"[{status_color}]{entry.status_code}[/{status_color}]",
            f"{entry.elapsed_ms:.0f}ms",
        )

    output_print(table)


@cli.group()
def env() -> None:
    """Environment management commands."""


@env.command("list")
@handle_errors
def env_list() -> None:
    """List all environments."""
    manager = EnvironmentManager()
    envs = manager.list()

    if not envs:
        output_print("[dim]No environments configured.[/dim]")
        output_print("[dim]Create one with: vagrant env create <name>[/dim]")
        return

    config = load_config()

    output_print("[bold]Environments:[/bold]")
    for name in envs:
        environment = manager.get(name)
        default = " [dim](default)[/dim]" if name == config.default_environment else ""
        output_print(f"  [cyan]{name}[/cyan]{default}")
        if environment.base_url:
            output_print(f"    [dim]URL: {environment.base_url}[/dim]")


@env.command("create")
@click.argument("name")
@click.option("--base-url", "-u", help="Base URL for API")
@click.option("--auth-type", "-a", type=click.Choice(["bearer", "basic", "apikey"]), help="Auth type")
@click.option("--token", "-t", help="Auth token or API key")
@handle_errors
def env_create(name: str, base_url: str | None, auth_type: str | None, token: str | None) -> None:
    """Create a new environment."""
    manager = EnvironmentManager()

    if manager.exists(name):
        output_print(f"[red]Environment '{name}' already exists.[/red]")
        sys.exit(2)

    auth = None
    if auth_type and token:
        if auth_type == "bearer":
            auth = AuthConfig(type="bearer", credentials={"token": token})
        elif auth_type == "apikey":
            auth = AuthConfig(type="apikey", credentials={"key": token})
        elif auth_type == "basic":
            # Expect token as user:pass
            auth = AuthConfig(type="basic", credentials={"username": token.split(":")[0], "password": token.split(":")[-1]})

    environment = Environment(
        name=name,
        base_url=base_url or "",
        auth=auth,
    )
    manager.save(environment)
    output_print(f"[green]Created environment '{name}'[/green]")


@env.command("delete")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this environment?")
@handle_errors
def env_delete(name: str) -> None:
    """Delete an environment."""
    manager = EnvironmentManager()
    manager.delete(name)
    output_print(f"[green]Deleted environment '{name}'[/green]")


@env.command("show")
@click.argument("name")
@handle_errors
def env_show(name: str) -> None:
    """Show environment details."""
    manager = EnvironmentManager()
    environment = manager.get(name)

    output_print(f"[bold]Environment: {environment.name}[/bold]")
    output_print()

    if environment.base_url:
        output_print(f"[bold]Base URL:[/bold] {environment.base_url}")

    if environment.auth:
        output_print(f"[bold]Auth Type:[/bold] {environment.auth.type}")

    if environment.variables:
        output_print("[bold]Variables:[/bold]")
        for key, value in environment.variables.items():
            display_value = value if not key.startswith("secret") else "****"
            output_print(f"  {key}: {display_value}")


@env.command("set")
@click.argument("name")
@click.argument("value")
@pass_context
@handle_errors
def env_set(gctx: GlobalContext, name: str, value: str) -> None:
    """Set a variable in the current environment.
    
    NAME is the variable name. Use secret_ prefix for secrets.
    VALUE is the variable value.
    
    Uses the environment specified by --env or the default environment.
    
    If use_keychain is enabled, variables prefixed with secret_ will be
    stored in the system keychain instead of the YAML file.
    """
    manager = EnvironmentManager()
    config = load_config()

    # Determine which environment to use
    env_name = gctx.env_name or config.default_environment
    if not env_name:
        output_print("[red]No environment specified. Use --env or set a default.[/red]")
        sys.exit(2)

    if not manager.exists(env_name):
        output_print(f"[red]Environment '{env_name}' not found.[/red]")
        sys.exit(2)

    environment = manager.get(env_name)
    environment.variables[name] = value
    manager.save(environment)

    # Indicate if stored in keychain
    from vagrant.storage.secrets import is_secret_variable
    if is_secret_variable(name) and config.use_keychain:
        output_print(f"[green]Set {name} in '{env_name}' (stored in keychain)[/green]")
    else:
        output_print(f"[green]Set {name} in '{env_name}'[/green]")


@env.command("keychain-status")
@handle_errors
def env_keychain_status() -> None:
    """Show keychain status and configuration.
    
    Displays whether system keychain is available and enabled.
    """
    from vagrant.storage.secrets import SecretStorage

    config = load_config()
    available = SecretStorage.is_available()
    enabled = config.use_keychain

    output_print("[bold]Keychain Status[/bold]")
    output_print()

    if available:
        output_print("  System keychain: [green]available[/green]")
    else:
        output_print("  System keychain: [red]not available[/red]")
        output_print("  [dim]Install keyring backends or check system configuration[/dim]")

    if enabled:
        output_print("  Keychain storage: [green]enabled[/green]")
    else:
        output_print("  Keychain storage: [dim]disabled[/dim]")
        output_print("  [dim]Enable with: vagrant config set use_keychain true[/dim]")

    if enabled and available:
        output_print()
        output_print("  [green]Secrets will be stored securely in system keychain.[/green]")
        output_print("  [dim]Variables prefixed with secret_ are stored in keychain.[/dim]")
    elif enabled and not available:
        output_print()
        output_print("  [yellow]Warning: Keychain enabled but not available.[/yellow]")
        output_print("  [dim]Secrets will be stored in plain text until keychain is available.[/dim]")


@cli.group()
def config() -> None:
    """Configuration management commands."""


@config.command("get")
@click.argument("key")
@handle_errors
def config_get(key: str) -> None:
    """Get a config value."""
    value = get_config_value(key)
    output_print(f"{key}: {value}")


@config.command("set")
@click.argument("key")
@click.argument("value")
@handle_errors
def config_set(key: str, value: str) -> None:
    """Set a config value."""
    set_config_value(key, value)
    output_print(f"[green]Set {key} = {value}[/green]")


@config.command("list")
@handle_errors
def config_list() -> None:
    """List all config values."""
    cfg = load_config()
    output_print("[bold]Configuration:[/bold]")
    for key, value in cfg.to_dict().items():
        output_print(f"  {key}: {value}")


@cli.command("mock")
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", type=int, default=8080, help="Port to listen on")
@click.option("--delay", "-d", type=int, default=0, help="Response delay in milliseconds")
@handle_errors
def mock(spec_path: str, host: str, port: int, delay: int) -> None:
    """Start a mock server from an OpenAPI spec.
    
    Generates mock responses based on examples and schemas in the spec.
    Useful for testing API integrations without a real backend.
    
    Examples:
    
        vagrant mock openapi.yaml
        vagrant mock ./spec.json --port 3000
        vagrant mock api.yaml --delay 100
    """
    from vagrant.mock.server import run_mock_server

    output_print(f"[bold]Starting mock server from {spec_path}[/bold]")

    try:
        asyncio.run(run_mock_server(spec_path, host=host, port=port, delay_ms=delay))
    except KeyboardInterrupt:
        output_print("\n[dim]Server stopped.[/dim]")


if __name__ == "__main__":
    cli()
