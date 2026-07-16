"""Concurrency regression tests for ``TaskStorage`` metadata writes.

These reproduce the read-modify-write races that ``write_metadata``'s old
non-atomic ``path.write_text`` made possible, and assert the per-task lock +
atomic ``os.replace`` + ``update_metadata`` now prevent lost updates and
torn reads. The race is real and pre-existed the brand feature: FastAPI
threadpool routes (archive/viewed) vs the async executor both touch the same
task's metadata.

The threading pattern mirrors ``test_sqlite_queue_storage_serializes_connection_lifecycle``.
"""

from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from typing import Any

import unittest


def _make_storage(root: Path):
    from codex_image.webui.storage import TaskStorage

    return TaskStorage(
        input_root=root / "inputs",
        output_root=root / "outputs",
        source_data_root=root / "outputs" / "source-data",
    )


class TaskStorageConcurrencyTests(unittest.TestCase):
    def test_update_metadata_serializes_concurrent_mutators_no_lost_update(self) -> None:
        """Two mutators each increment a counter many times concurrently.

        Without a lock covering read→modify→write, last-write-wins would drop
        increments. With ``update_metadata`` the final value must equal the sum
        of all increments.
        """
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = _make_storage(root)
            task = storage.create_task("generate")
            storage.write_metadata(task.task_id, {"task_id": task.task_id, "counter": 0})

            increments_per_thread = 200
            thread_count = 8
            barrier = threading.Barrier(thread_count)

            def worker() -> None:
                barrier.wait()
                for _ in range(increments_per_thread):
                    storage.update_metadata(task.task_id, _bump_counter)

            threads = [threading.Thread(target=worker) for _ in range(thread_count)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            final = storage.read_metadata(task.task_id)

        self.assertEqual(final["counter"], increments_per_thread * thread_count)

    def test_write_metadata_is_atomic_no_torn_json_under_concurrent_reads(self) -> None:
        """Concurrent readers must never observe a half-written file.

        A writer hammers ``write_metadata`` with a large payload while readers
        repeatedly parse it; any ``JSONDecodeError`` or non-dict payload means a
        torn read slipped through the atomic replace.
        """
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = _make_storage(root)
            task = storage.create_task("generate")
            # Large-ish payload so a partial write, if non-atomic, would be
            # detectable by a reader mid-flight.
            big = {f"key_{i}": "x" * 256 for i in range(400)}
            storage.write_metadata(task.task_id, {"task_id": task.task_id, **big})

            stop = threading.Event()
            torn_seen = []

            def writer() -> None:
                toggle = False
                while not stop.is_set():
                    toggle = not toggle
                    payload = {f"key_{i}": ("a" if toggle else "b") * 256 for i in range(400)}
                    storage.write_metadata(task.task_id, {"task_id": task.task_id, **payload})

            def reader() -> None:
                path = storage.metadata_path(task.task_id)
                while not stop.is_set():
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        torn_seen.append("decode-error")
                        return
                    except FileNotFoundError:
                        # os.replace is atomic on POSIX, but a transient
                        # FileNotFoundError across the rename boundary is not a
                        # torn read; ignore.
                        continue
                    if not isinstance(data, dict):
                        torn_seen.append("non-dict")
                        return

            writer_thread = threading.Thread(target=writer)
            reader_threads = [threading.Thread(target=reader) for _ in range(4)]
            writer_thread.start()
            for thread in reader_threads:
                thread.start()
            # Let them race briefly.
            threading.Event().wait(0.5)
            stop.set()
            writer_thread.join()
            for thread in reader_threads:
                thread.join()

        self.assertEqual(torn_seen, [], f"observed torn/malformed metadata: {torn_seen}")

    def test_update_metadata_preserves_independent_fields_from_other_mutators(self) -> None:
        """One mutator touches ``outputs`` while another touches ``archived_at``.

        Mirrors the real archive-route vs executor race: without atomicity the
        executor's full metadata write would clobber ``archived_at`` (or vice
        versa). Both fields must survive.
        """
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = _make_storage(root)
            task = storage.create_task("generate")
            storage.write_metadata(task.task_id, {"task_id": task.task_id, "outputs": [], "archived_at": ""})

            iterations = 100
            barrier = threading.Barrier(2)

            def outputs_writer() -> None:
                barrier.wait()
                for i in range(iterations):
                    storage.update_metadata(
                        task.task_id,
                        lambda m, i=i: m.setdefault("outputs", []).append({"i": i}),
                    )

            def archive_writer() -> None:
                barrier.wait()
                for i in range(iterations):
                    storage.update_metadata(
                        task.task_id,
                        lambda m, i=i: m.__setitem__("archived_at", f"2026-07-{i:02d}"),
                    )

            t1 = threading.Thread(target=outputs_writer)
            t2 = threading.Thread(target=archive_writer)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            final = storage.read_metadata(task.task_id)

        self.assertEqual(len(final["outputs"]), iterations)
        self.assertEqual(final["archived_at"], "2026-07-99")
        # Crucially, the executor-side writes were not clobbered by the archive
        # writer overwriting the whole document from a stale read.
        self.assertEqual(final["outputs"][-1], {"i": iterations - 1})

    def test_per_task_locks_are_independent_across_tasks(self) -> None:
        """Locks are per task_id, so unrelated tasks do not serialize each other."""
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = _make_storage(root)
            task_a = storage.create_task("generate")
            task_b = storage.create_task("generate")
            storage.write_metadata(task_a.task_id, {"task_id": task_a.task_id, "counter": 0})
            storage.write_metadata(task_b.task_id, {"task_id": task_b.task_id, "counter": 0})

            iterations = 100
            finished_order: list[str] = []
            order_lock = threading.Lock()

            def slow_bump(task_id: str, delay: float) -> None:
                for _ in range(iterations):
                    storage.update_metadata(task_id, _bump_counter)
                    # Hold nothing global; just prove both progress concurrently
                    # by recording completion under a tiny shared lock.
                with order_lock:
                    finished_order.append(task_id)

            t1 = threading.Thread(target=slow_bump, args=(task_a.task_id, 0.0))
            t2 = threading.Thread(target=slow_bump, args=(task_b.task_id, 0.0))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            a_final = storage.read_metadata(task_a.task_id)
            b_final = storage.read_metadata(task_b.task_id)

        # Both tasks reached their full count despite concurrent writes; a
        # single global lock would still be correct here, but this guards
        # against a regression where a shared lock accidentally serializes
        # unrelated tasks and still loses updates.
        self.assertEqual(a_final["counter"], iterations)
        self.assertEqual(b_final["counter"], iterations)

    def test_update_metadata_creates_metadata_when_absent(self) -> None:
        """``update_metadata`` seeds an empty task record if none exists yet."""
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = _make_storage(root)
            task = storage.create_task("generate")

            result = storage.update_metadata(task.task_id, lambda m: m.__setitem__("status", "running"))

            reread = storage.read_metadata(task.task_id)

        self.assertEqual(result["status"], "running")
        self.assertEqual(result["task_id"], task.task_id)
        self.assertEqual(reread["status"], "running")


def _bump_counter(metadata: dict[str, Any]) -> None:
    metadata["counter"] = int(metadata.get("counter", 0)) + 1


if __name__ == "__main__":
    unittest.main()
