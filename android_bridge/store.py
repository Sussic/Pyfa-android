"""Atomic storage for a complete declarative fit graph, separate from EOS SQL.

A commit is acknowledged only after a fresh connection identifies its unique
token, generation and digest. Existing invalid files are never initialized anew.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import NamedTuple
import uuid

SCHEMA_VERSION = 1
APPLICATION_ID = 0x50594641
SCHEMA_SQL = ("CREATE TABLE graph_state (slot INTEGER PRIMARY KEY CHECK(slot=1), "
              "generation INTEGER NOT NULL CHECK(generation>=1), commit_token TEXT NOT NULL, "
              "payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL)")


class StoreError(RuntimeError):
    pass


class StoreUncertain(StoreError):
    pass


class StoreWriteRejected(StoreError):
    pass


def encode_graph(graph):
    return json.dumps(graph, sort_keys=True, separators=(",", ":"), allow_nan=False)


def decode_graph(payload):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise StoreError("Saved fits contain duplicate fields")
            result[key] = value
        return result

    def nonfinite(value):
        raise StoreError("Saved fits contain a nonfinite number")

    try:
        graph = json.loads(payload, object_pairs_hook=pairs, parse_constant=nonfinite)
        if type(graph) is not dict or encode_graph(graph) != payload:
            raise StoreError("Saved fits have an invalid graph encoding")
        return graph
    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        raise StoreError("Saved fits have an invalid graph encoding") from error


class StoredGraph(NamedTuple):
    generation: int
    token: str
    payload: str
    digest: str


class WriteAttempt(NamedTuple):
    before: StoredGraph | None
    after: StoredGraph


class GraphStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.current = self._read() if self.path.exists() else None
        self.opened_existing = self.current is not None

    def _connect(self, path=None):
        # mode=rw must not manufacture a missing/corrupt store during reopen.
        connection = sqlite3.connect((path or self.path).as_uri() + "?mode=rw", uri=True,
                                     isolation_level=None, timeout=5)
        try:
            connection.execute("PRAGMA synchronous=FULL")
        except Exception:
            connection.close()
            raise
        return connection

    def _read(self):
        try:
            connection = self._connect()
            try:
                if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise StoreError("Saved fits failed the database integrity check")
                if (connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID or
                        connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
                    raise StoreError("Saved fits use an unsupported database format")
                if connection.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                    raise StoreError("Saved fits use an unsupported journal mode")
                schema = connection.execute(
                    "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
                if schema != [("table", "graph_state", SCHEMA_SQL)]:
                    raise StoreError("Saved fits have an unsupported schema")
                rows = connection.execute(
                    "SELECT slot,generation,commit_token,payload,payload_sha256 FROM graph_state").fetchall()
                if len(rows) != 1 or rows[0][0] != 1:
                    raise StoreError("Saved fits are missing their committed graph")
                _, generation, token, payload, digest = rows[0]
                if (type(generation) is not int or not 1 <= generation < 2**63 or
                        type(token) is not str or len(token) != 32 or
                        any(char not in "0123456789abcdef" for char in token) or
                        type(payload) is not str or type(digest) is not str or
                        hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest):
                    raise StoreError("Saved fits have an invalid generation or checksum")
                decode_graph(payload)
                return StoredGraph(generation, token, payload, digest)
            finally:
                connection.close()
        except (sqlite3.Error, OSError) as error:
            raise StoreError("Saved fits could not be read; the file has been preserved") from error

    def prepare(self, graph):
        payload = encode_graph(graph)
        generation = self.current.generation + 1 if self.current else 1
        if generation >= 2**63:
            raise StoreError("Saved fit generation limit reached")
        return WriteAttempt(self.current, StoredGraph(generation, uuid.uuid4().hex, payload,
                            hashlib.sha256(payload.encode("utf-8")).hexdigest()))

    @staticmethod
    def _commit(connection):
        connection.commit()

    def write(self, attempt):
        """Attempt one commit. The caller must confirm even if this raises."""
        if attempt.before is None:
            self._initialize(attempt.after)
            return
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            before = attempt.before
            cursor = connection.execute(
                "UPDATE graph_state SET generation=?,commit_token=?,payload=?,payload_sha256=? "
                "WHERE slot=1 AND generation=? AND commit_token=? AND payload_sha256=?",
                (*attempt.after, before.generation, before.token, before.digest))
            if cursor.rowcount != 1:
                raise StoreUncertain("Saved fits changed in another session; reopen them")
            self._commit(connection)
        finally:
            connection.close()

    def _initialize(self, candidate):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".pyfa-fits-", suffix=".sqlite", dir=self.path.parent)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            connection = self._connect(temporary)
            try:
                if connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
                    raise StoreError("Cannot create the saved fit database")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                connection.execute(SCHEMA_SQL)
                connection.execute("INSERT INTO graph_state VALUES(1,?,?,?,?)", candidate)
                self._commit(connection)
            finally:
                connection.close()
            self._install_initial(temporary)
        finally:
            temporary.unlink(missing_ok=True)
            Path(str(temporary) + "-journal").unlink(missing_ok=True)

    def _install_initial(self, temporary):
        # Android forbids app hard links. All creators of this app-private store
        # instead serialize installation through one permanent lock inode.
        # Never unlink that inode: waiters must continue locking the same file.
        if os.name == "nt":
            # Windows rename already refuses any existing destination.
            os.rename(temporary, self.path)
            return
        import fcntl
        with Path(str(self.path) + ".init.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if os.path.lexists(self.path):
                raise FileExistsError("Saved fits already exist")
            os.rename(temporary, self.path)
            if hasattr(os, "O_DIRECTORY"):
                directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)

    def confirm(self, attempt):
        """Identify new, old or uncertain durable state through a new connection."""
        try:
            current = self._read() if self.path.exists() else None
        except Exception as error:
            raise StoreUncertain("Cannot confirm the saved fit commit; reopen the app") from error
        if current == attempt.after:
            return "new"
        if current == attempt.before:
            return "old"
        raise StoreUncertain("Saved fit state changed unexpectedly; reopen the app")

    def accept(self, attempt):
        self.current = attempt.after
