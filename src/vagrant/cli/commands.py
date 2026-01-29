"""CLI command definitions using Click."""

import click

from vagrant import __version__


@click.group()
@click.version_option(version=__version__, prog_name="vagrant")
def cli() -> None:
    """Vagrant - API Explorer.
    
    Explore any API without writing code. Point at an OpenAPI spec or URL,
    browse endpoints interactively, make requests, and understand the API.
    """


@cli.command()
@click.argument("spec_or_url")
@click.option("--env", "-e", help="Environment name to use")
@click.option("--base-url", "-b", help="Override base URL")
def explore(spec_or_url: str, env: str | None, base_url: str | None) -> None:
    """Launch TUI explorer for an API.
    
    SPEC_OR_URL can be a path to an OpenAPI spec file or a URL.
    """
    click.echo(f"Exploring: {spec_or_url}")
    click.echo("TUI not yet implemented - coming soon!")


@cli.command()
@click.argument("method")
@click.argument("url")
@click.option("--data", "-d", help="Request body (JSON)")
@click.option("--header", "-H", multiple=True, help="Add header (key:value)")
@click.option("--env", "-e", help="Environment name")
def request(
    method: str,
    url: str,
    data: str | None,
    header: tuple[str, ...],
    env: str | None,
) -> None:
    """Make a single HTTP request.
    
    METHOD is the HTTP method (GET, POST, PUT, DELETE, etc.).
    URL is the full URL or path (if base_url is set in environment).
    """
    click.echo(f"{method.upper()} {url}")
    click.echo("HTTP client not yet implemented - coming soon!")


@cli.command()
@click.option("--limit", "-n", default=50, help="Number of entries to show")
def history(limit: int) -> None:
    """Show request history."""
    click.echo(f"History (last {limit} requests)")
    click.echo("History storage not yet implemented - coming soon!")


@cli.group()
def env() -> None:
    """Environment management commands."""


@env.command("list")
def env_list() -> None:
    """List all environments."""
    click.echo("Environments:")
    click.echo("  (none configured)")


@env.command("set")
@click.argument("name")
@click.argument("value")
def env_set(name: str, value: str) -> None:
    """Set an environment variable."""
    click.echo(f"Set {name} = {value}")
    click.echo("Environment storage not yet implemented - coming soon!")


@env.command("get")
@click.argument("name")
def env_get(name: str) -> None:
    """Get an environment variable value."""
    click.echo(f"Get {name}")
    click.echo("Environment storage not yet implemented - coming soon!")


if __name__ == "__main__":
    cli()
