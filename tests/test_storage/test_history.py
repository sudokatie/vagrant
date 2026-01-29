"""Tests for history storage."""

import pytest
from datetime import datetime
from pathlib import Path

from vagrant.storage.history import HistoryEntry, HistoryStorage


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Return path to temporary database file."""
    return tmp_path / "test_history.db"


@pytest.fixture
def storage(temp_db: Path) -> HistoryStorage:
    """Create test history storage."""
    return HistoryStorage(db_path=temp_db)


@pytest.fixture
def sample_entry() -> HistoryEntry:
    """Create sample history entry."""
    return HistoryEntry(
        id=None,
        timestamp=datetime(2026, 1, 29, 12, 0, 0),
        method="GET",
        url="https://api.example.com/users",
        headers={"Accept": "application/json"},
        params={"page": "1"},
        body=None,
        status_code=200,
        response_body='[{"id": 1, "name": "Test"}]',
        elapsed_ms=50.5,
        environment="production",
    )


class TestHistoryEntry:
    """Tests for HistoryEntry dataclass."""

    def test_create_entry(self, sample_entry: HistoryEntry):
        """Entry can be created with all fields."""
        assert sample_entry.method == "GET"
        assert sample_entry.url == "https://api.example.com/users"
        assert sample_entry.status_code == 200

    def test_optional_fields(self):
        """Entry with minimal fields."""
        entry = HistoryEntry(
            id=None,
            timestamp=datetime.now(),
            method="GET",
            url="https://example.com",
            headers={},
            params={},
            body=None,
            status_code=200,
            response_body="",
            elapsed_ms=0.0,
        )
        assert entry.environment is None


class TestHistoryStorageInit:
    """Tests for HistoryStorage initialization."""

    def test_creates_database(self, temp_db: Path):
        """Storage creates database file."""
        HistoryStorage(db_path=temp_db)
        assert temp_db.exists()

    def test_creates_tables(self, storage: HistoryStorage):
        """Storage creates required tables."""
        # Should not raise
        storage.count()


class TestHistoryStorageAdd:
    """Tests for adding entries."""

    def test_add_returns_id(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """add() returns the entry ID."""
        entry_id = storage.add(sample_entry)
        assert entry_id > 0

    def test_add_increments_id(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """Subsequent adds get incrementing IDs."""
        id1 = storage.add(sample_entry)
        id2 = storage.add(sample_entry)
        assert id2 > id1


class TestHistoryStorageGet:
    """Tests for retrieving entries."""

    def test_get_existing(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """get() retrieves existing entry."""
        entry_id = storage.add(sample_entry)
        retrieved = storage.get(entry_id)
        
        assert retrieved is not None
        assert retrieved.id == entry_id
        assert retrieved.method == sample_entry.method
        assert retrieved.url == sample_entry.url

    def test_get_nonexistent(self, storage: HistoryStorage):
        """get() returns None for nonexistent ID."""
        retrieved = storage.get(99999)
        assert retrieved is None

    def test_get_preserves_data(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """get() preserves all entry data."""
        entry_id = storage.add(sample_entry)
        retrieved = storage.get(entry_id)
        
        assert retrieved.timestamp == sample_entry.timestamp
        assert retrieved.headers == sample_entry.headers
        assert retrieved.params == sample_entry.params
        assert retrieved.status_code == sample_entry.status_code
        assert retrieved.elapsed_ms == sample_entry.elapsed_ms
        assert retrieved.environment == sample_entry.environment


class TestHistoryStorageList:
    """Tests for listing entries."""

    def test_list_empty(self, storage: HistoryStorage):
        """list() returns empty for no entries."""
        entries = storage.list()
        assert entries == []

    def test_list_returns_entries(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """list() returns added entries."""
        storage.add(sample_entry)
        entries = storage.list()
        assert len(entries) == 1

    def test_list_order_newest_first(self, storage: HistoryStorage):
        """list() returns entries newest first."""
        older = HistoryEntry(
            id=None,
            timestamp=datetime(2026, 1, 1, 12, 0, 0),
            method="GET",
            url="https://example.com/older",
            headers={},
            params={},
            body=None,
            status_code=200,
            response_body="",
            elapsed_ms=0.0,
        )
        newer = HistoryEntry(
            id=None,
            timestamp=datetime(2026, 1, 29, 12, 0, 0),
            method="GET",
            url="https://example.com/newer",
            headers={},
            params={},
            body=None,
            status_code=200,
            response_body="",
            elapsed_ms=0.0,
        )
        
        storage.add(older)
        storage.add(newer)
        
        entries = storage.list()
        assert entries[0].url.endswith("/newer")

    def test_list_limit(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """list() respects limit."""
        for _ in range(10):
            storage.add(sample_entry)
        
        entries = storage.list(limit=5)
        assert len(entries) == 5

    def test_list_offset(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """list() respects offset."""
        for _ in range(10):
            storage.add(sample_entry)
        
        all_entries = storage.list(limit=10)
        offset_entries = storage.list(limit=10, offset=5)
        
        assert len(offset_entries) == 5
        assert offset_entries[0].id == all_entries[5].id


class TestHistoryStorageSearch:
    """Tests for searching entries."""

    def test_search_by_url(self, storage: HistoryStorage):
        """search() finds by URL substring."""
        entry = HistoryEntry(
            id=None,
            timestamp=datetime.now(),
            method="GET",
            url="https://api.example.com/users",
            headers={},
            params={},
            body=None,
            status_code=200,
            response_body="",
            elapsed_ms=0.0,
        )
        storage.add(entry)
        
        results = storage.search("users")
        assert len(results) == 1
        assert "users" in results[0].url

    def test_search_by_method(self, storage: HistoryStorage):
        """search() finds by method."""
        entry = HistoryEntry(
            id=None,
            timestamp=datetime.now(),
            method="POST",
            url="https://example.com/test",
            headers={},
            params={},
            body=None,
            status_code=201,
            response_body="",
            elapsed_ms=0.0,
        )
        storage.add(entry)
        
        results = storage.search("POST")
        assert len(results) == 1

    def test_search_no_results(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """search() returns empty for no matches."""
        storage.add(sample_entry)
        results = storage.search("nonexistent")
        assert results == []


class TestHistoryStorageClear:
    """Tests for clearing history."""

    def test_clear_removes_all(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """clear() removes all entries."""
        storage.add(sample_entry)
        storage.add(sample_entry)
        
        storage.clear()
        
        assert storage.count() == 0


class TestHistoryStorageCleanup:
    """Tests for cleanup."""

    def test_cleanup_removes_old(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """cleanup() removes oldest entries."""
        for _ in range(10):
            storage.add(sample_entry)
        
        deleted = storage.cleanup(max_entries=5)
        
        assert deleted == 5
        assert storage.count() == 5

    def test_cleanup_noop_when_under_limit(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """cleanup() does nothing when under limit."""
        for _ in range(5):
            storage.add(sample_entry)
        
        deleted = storage.cleanup(max_entries=10)
        
        assert deleted == 0
        assert storage.count() == 5


class TestHistoryStorageCount:
    """Tests for count."""

    def test_count_empty(self, storage: HistoryStorage):
        """count() returns 0 for empty storage."""
        assert storage.count() == 0

    def test_count_after_adds(self, storage: HistoryStorage, sample_entry: HistoryEntry):
        """count() reflects added entries."""
        storage.add(sample_entry)
        storage.add(sample_entry)
        assert storage.count() == 2
