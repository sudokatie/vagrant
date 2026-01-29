"""Tests for CLI commands."""

from click.testing import CliRunner

from vagrant.cli.commands import cli


def test_cli_help():
    """CLI shows help text."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Vagrant - API Explorer" in result.output


def test_cli_version():
    """CLI shows version."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_explore_command():
    """Explore command accepts spec argument."""
    runner = CliRunner()
    result = runner.invoke(cli, ["explore", "test.yaml"])
    assert result.exit_code == 0
    assert "Exploring: test.yaml" in result.output


def test_request_command():
    """Request command accepts method and URL."""
    runner = CliRunner()
    result = runner.invoke(cli, ["request", "GET", "https://example.com/api"])
    assert result.exit_code == 0
    assert "GET https://example.com/api" in result.output


def test_history_command():
    """History command runs."""
    runner = CliRunner()
    result = runner.invoke(cli, ["history"])
    assert result.exit_code == 0
    assert "History" in result.output


def test_env_list_command():
    """Env list command runs."""
    runner = CliRunner()
    result = runner.invoke(cli, ["env", "list"])
    assert result.exit_code == 0
    assert "Environments" in result.output


def test_env_set_command():
    """Env set command accepts name and value."""
    runner = CliRunner()
    result = runner.invoke(cli, ["env", "set", "API_KEY", "test123"])
    assert result.exit_code == 0
    assert "Set API_KEY" in result.output


def test_env_get_command():
    """Env get command accepts name."""
    runner = CliRunner()
    result = runner.invoke(cli, ["env", "get", "API_KEY"])
    assert result.exit_code == 0
    assert "Get API_KEY" in result.output
