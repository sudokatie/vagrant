"""Integration tests for Vagrant.

Tests full workflows across multiple components.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import respx
from httpx import Response

from vagrant.core.config import Config, load_config, save_config
from vagrant.http.auth import AuthConfig
from vagrant.http.client import HttpClient, HttpRequest
from vagrant.parser.models import ApiSpec, Operation, Parameter, Schema, Server
from vagrant.parser.openapi import OpenAPIParser
from vagrant.storage.environments import Environment, EnvironmentManager
from vagrant.storage.history import HistoryEntry, HistoryStorage

# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def petstore_spec() -> ApiSpec:
    """Parse the petstore fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "specs" / "petstore.yaml"
    if fixture_path.exists():
        parser = OpenAPIParser()
        return parser.parse_file(fixture_path)

    # Create minimal spec if fixture missing
    return ApiSpec(
        title="Petstore API",
        version="1.0.0",
        servers=[Server(url="https://api.petstore.com/v1")],
        operations=[
            Operation(
                method="GET",
                path="/pets",
                operation_id="listPets",
                summary="List all pets",
                tags=["pets"],
            ),
            Operation(
                method="POST",
                path="/pets",
                operation_id="createPet",
                summary="Create a pet",
                tags=["pets"],
            ),
            Operation(
                method="GET",
                path="/pets/{petId}",
                operation_id="getPet",
                summary="Get a pet by ID",
                tags=["pets"],
                parameters=[
                    Parameter(
                        name="petId",
                        location="path",
                        required=True,
                        schema=Schema.integer(),
                    ),
                ],
            ),
            Operation(
                method="DELETE",
                path="/pets/{petId}",
                operation_id="deletePet",
                summary="Delete a pet",
                tags=["pets"],
                parameters=[
                    Parameter(
                        name="petId",
                        location="path",
                        required=True,
                        schema=Schema.integer(),
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def history_storage(tmp_path: Path) -> HistoryStorage:
    """Create temporary history storage."""
    db_path = tmp_path / "test_history.db"
    return HistoryStorage(db_path)


@pytest.fixture
def env_manager(tmp_path: Path) -> EnvironmentManager:
    """Create temporary environment manager."""
    return EnvironmentManager(tmp_path)


# --------------------------------------------------------------------------
# Parser -> HTTP Client Integration
# --------------------------------------------------------------------------


class TestParserToClientFlow:
    """Test parsing a spec and making requests."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_parse_and_request(self, petstore_spec: ApiSpec) -> None:
        """Parse spec and make a request to an endpoint."""
        # Mock API response - use actual base URL from spec
        base_url = petstore_spec.base_url or "https://api.petstore.com/v1"
        respx.get(f"{base_url}/pets").mock(
            return_value=Response(
                200,
                json=[{"id": 1, "name": "Fluffy"}, {"id": 2, "name": "Max"}],
            )
        )

        # Get operation from parsed spec
        list_pets = petstore_spec.find_operation("GET", "/pets")
        assert list_pets is not None

        # Build request from operation
        client = HttpClient(base_url=base_url)
        request = HttpRequest(
            method=list_pets.method,
            url=list_pets.path,
        )

        # Send request
        response = await client.send(request)

        assert response.status_code == 200
        assert isinstance(response.body, list)
        assert len(response.body) == 2
        assert response.body[0]["name"] == "Fluffy"

    @respx.mock
    @pytest.mark.asyncio
    async def test_path_parameters(self, petstore_spec: ApiSpec) -> None:
        """Test request with path parameters."""
        base_url = petstore_spec.base_url or "https://api.petstore.com/v1"
        respx.get(f"{base_url}/pets/42").mock(
            return_value=Response(
                200,
                json={"id": 42, "name": "Whiskers"},
            )
        )

        get_pet = petstore_spec.find_operation("GET", "/pets/{petId}")
        assert get_pet is not None

        # Substitute path parameter
        path = get_pet.path.replace("{petId}", "42")

        client = HttpClient(base_url=base_url)
        response = await client.get(path)

        assert response.status_code == 200
        assert response.body["id"] == 42

    @respx.mock
    @pytest.mark.asyncio
    async def test_post_with_body(self, petstore_spec: ApiSpec) -> None:
        """Test POST request with JSON body."""
        base_url = petstore_spec.base_url or "https://api.petstore.com/v1"
        respx.post(f"{base_url}/pets").mock(
            return_value=Response(
                201,
                json={"id": 3, "name": "Buddy"},
            )
        )

        client = HttpClient(base_url=base_url)
        response = await client.post("/pets", body={"name": "Buddy"})

        assert response.status_code == 201
        assert response.body["name"] == "Buddy"


# --------------------------------------------------------------------------
# HTTP Client -> History Integration
# --------------------------------------------------------------------------


class TestClientToHistoryFlow:
    """Test making requests and storing in history."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_request_stored_in_history(
        self,
        history_storage: HistoryStorage,
    ) -> None:
        """Requests are stored in history with all details."""
        respx.get("https://api.example.com/users").mock(
            return_value=Response(
                200,
                json=[{"id": 1, "name": "Alice"}],
            )
        )

        client = HttpClient()
        request = HttpRequest(
            method="GET",
            url="https://api.example.com/users",
            headers={"Authorization": "Bearer token123"},
        )

        response = await client.send(request)

        # Store in history
        entry = HistoryEntry(
            id=None,
            timestamp=datetime.now(),
            method=request.method,
            url=request.url,
            headers=request.headers,
            params=request.params,
            body=None,
            status_code=response.status_code,
            response_body=json.dumps(response.body),
            elapsed_ms=response.elapsed_ms,
        )

        entry_id = history_storage.add(entry)
        assert entry_id > 0

        # Retrieve and verify
        retrieved = history_storage.get(entry_id)
        assert retrieved is not None
        assert retrieved.method == "GET"
        assert retrieved.url == "https://api.example.com/users"
        assert retrieved.status_code == 200
        assert "Alice" in retrieved.response_body

    def test_history_search_finds_requests(
        self,
        history_storage: HistoryStorage,
    ) -> None:
        """History search finds matching requests."""
        # Add multiple entries
        for i, url in enumerate([
            "https://api.github.com/users",
            "https://api.github.com/repos",
            "https://api.example.com/data",
        ]):
            history_storage.add(
                HistoryEntry(
                    id=None,
                    timestamp=datetime.now(),
                    method="GET",
                    url=url,
                    headers={},
                    params={},
                    body=None,
                    status_code=200,
                    response_body="{}",
                    elapsed_ms=100.0,
                )
            )

        # Search for github
        results = history_storage.search("github")
        assert len(results) == 2

        # Search for example
        results = history_storage.search("example")
        assert len(results) == 1


# --------------------------------------------------------------------------
# Environment -> HTTP Client Integration
# --------------------------------------------------------------------------


class TestEnvironmentToClientFlow:
    """Test environment variable substitution in requests."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_base_url_from_environment(
        self,
        env_manager: EnvironmentManager,
    ) -> None:
        """Base URL comes from environment config."""
        respx.get("https://staging.api.example.com/health").mock(
            return_value=Response(200, json={"status": "ok"})
        )

        # Create environment
        env = Environment(
            name="staging",
            base_url="https://staging.api.example.com",
        )
        env_manager.save(env)

        # Load and use
        loaded = env_manager.get("staging")
        assert loaded is not None

        client = HttpClient(base_url=loaded.base_url)
        response = await client.get("/health")

        assert response.status_code == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_from_environment(
        self,
        env_manager: EnvironmentManager,
    ) -> None:
        """Auth config comes from environment."""
        def check_auth(request):
            auth = request.headers.get("Authorization", "")
            if auth == "Bearer env-token-123":
                return Response(200, json={"authenticated": True})
            return Response(401, json={"error": "unauthorized"})

        respx.get("https://api.example.com/me").mock(side_effect=check_auth)

        # Create environment with auth - use correct AuthConfig format
        env = Environment(
            name="prod",
            base_url="https://api.example.com",
            auth=AuthConfig(type="bearer", credentials={"token": "env-token-123"}),
        )
        env_manager.save(env)

        # Load and use
        loaded = env_manager.get("prod")
        assert loaded is not None

        client = HttpClient(base_url=loaded.base_url)
        if loaded.auth:
            client.set_auth(loaded.auth)

        response = await client.get("/me")
        assert response.status_code == 200
        assert response.body["authenticated"] is True

    def test_variable_substitution_in_url(
        self,
        env_manager: EnvironmentManager,
    ) -> None:
        """Variables in URLs are substituted from environment."""
        env = Environment(
            name="test",
            base_url="https://api.example.com",
            variables={"api_version": "v2", "tenant": "acme"},
        )

        url_template = "{{base_url}}/{{api_version}}/{{tenant}}/users"
        result = env_manager.substitute(url_template, env)

        assert result == "https://api.example.com/v2/acme/users"


# --------------------------------------------------------------------------
# Full Pipeline Integration
# --------------------------------------------------------------------------


class TestFullPipeline:
    """Test complete workflows from parsing to response."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_parse_request_store_workflow(
        self,
        petstore_spec: ApiSpec,
        history_storage: HistoryStorage,
        env_manager: EnvironmentManager,
    ) -> None:
        """Complete workflow: parse spec, configure env, request, store."""
        base_url = petstore_spec.base_url or "https://api.petstore.com/v1"

        # Mock API
        respx.get(f"{base_url}/pets").mock(
            return_value=Response(
                200,
                json=[{"id": 1, "name": "Fluffy", "status": "available"}],
            )
        )

        # 1. Create environment
        env = Environment(
            name="petstore-test",
            base_url=base_url,
            variables={"max_results": "100"},
        )
        env_manager.save(env)

        # 2. Find operation in spec
        list_pets = petstore_spec.find_operation("GET", "/pets")
        assert list_pets is not None

        # 3. Build and send request
        client = HttpClient(base_url=env.base_url)
        request = HttpRequest(
            method=list_pets.method,
            url=list_pets.path,
            params={"limit": env.variables["max_results"]},
        )

        response = await client.send(request)
        assert response.status_code == 200

        # 4. Store in history
        entry = HistoryEntry(
            id=None,
            timestamp=datetime.now(),
            method=request.method,
            url=f"{env.base_url}{request.url}",
            headers=request.headers,
            params=request.params,
            body=None,
            status_code=response.status_code,
            response_body=json.dumps(response.body),
            elapsed_ms=response.elapsed_ms,
            environment=env.name,
        )

        entry_id = history_storage.add(entry)

        # 5. Verify retrieval
        retrieved = history_storage.get(entry_id)
        assert retrieved is not None
        assert retrieved.environment == "petstore-test"
        assert "Fluffy" in retrieved.response_body


# --------------------------------------------------------------------------
# Config Integration
# --------------------------------------------------------------------------


class TestConfigIntegration:
    """Test configuration across components."""

    def test_config_affects_client(self, tmp_path: Path, monkeypatch) -> None:
        """Config settings affect HTTP client behavior."""
        # Monkeypatch config path
        config_path = tmp_path / "config.yaml"
        monkeypatch.setattr("vagrant.core.config.get_config_path", lambda: config_path)

        # Save config with custom timeout
        config = Config(timeout=5, verify_ssl=False)
        save_config(config)

        # Load and apply to client
        loaded = load_config()
        client = HttpClient(
            timeout=loaded.timeout,
            verify_ssl=loaded.verify_ssl,
        )

        assert client.timeout == 5
        assert client.verify_ssl is False

    def test_config_roundtrip(self, tmp_path: Path, monkeypatch) -> None:
        """Config survives save/load cycle."""
        # Monkeypatch config path
        config_path = tmp_path / "config.yaml"
        monkeypatch.setattr("vagrant.core.config.get_config_path", lambda: config_path)

        original = Config(
            timeout=45,
            verify_ssl=True,
            theme="dark",
            history_limit=500,
        )

        save_config(original)
        loaded = load_config()

        assert loaded.timeout == 45
        assert loaded.verify_ssl is True
        assert loaded.theme == "dark"
        assert loaded.history_limit == 500


# --------------------------------------------------------------------------
# Error Handling Integration
# --------------------------------------------------------------------------


class TestErrorHandlingIntegration:
    """Test error handling across components."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_network_error_captured(
        self,
        history_storage: HistoryStorage,
    ) -> None:
        """Network errors are handled gracefully."""
        from vagrant.core.errors import NetworkError

        # Use httpx.ConnectError which is what respx wraps
        respx.get("https://api.example.com/fail").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        client = HttpClient()

        with pytest.raises(NetworkError) as exc_info:
            await client.get("https://api.example.com/fail")

        assert "Connection failed" in str(exc_info.value)

    def test_invalid_spec_handled(self, tmp_path: Path) -> None:
        """Invalid specs raise helpful errors."""
        from vagrant.core.errors import SpecParseError

        bad_spec = tmp_path / "bad.yaml"
        bad_spec.write_text("not: valid: yaml: content:")

        parser = OpenAPIParser()

        with pytest.raises(SpecParseError):
            parser.parse_file(bad_spec)


# --------------------------------------------------------------------------
# Multi-Environment Workflow
# --------------------------------------------------------------------------


class TestMultiEnvironmentWorkflow:
    """Test switching between environments."""

    def test_switch_environments(self, env_manager: EnvironmentManager) -> None:
        """Can switch between dev/staging/prod environments."""
        # Create three environments - use correct AuthConfig format
        envs = {
            "dev": Environment(
                name="dev",
                base_url="http://localhost:3000",
                variables={"debug": "true"},
            ),
            "staging": Environment(
                name="staging",
                base_url="https://staging.api.example.com",
                auth=AuthConfig(type="bearer", credentials={"token": "staging-token"}),
            ),
            "prod": Environment(
                name="prod",
                base_url="https://api.example.com",
                auth=AuthConfig(type="bearer", credentials={"token": "prod-token"}),
            ),
        }

        for env in envs.values():
            env_manager.save(env)

        # List all
        names = env_manager.list()
        assert set(names) == {"dev", "staging", "prod"}

        # Switch between them
        dev = env_manager.get("dev")
        assert dev is not None
        assert dev.base_url == "http://localhost:3000"

        prod = env_manager.get("prod")
        assert prod is not None
        assert prod.auth is not None
        assert prod.auth.credentials.get("token") == "prod-token"
