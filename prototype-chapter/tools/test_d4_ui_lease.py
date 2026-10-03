#!/usr/bin/env python3
from __future__ import annotations

import multiprocessing
import os
import stat
import tempfile
import threading
import time
import unittest
import warnings
from pathlib import Path
from unittest import mock

import d4_ui_lease


def binding(seed: str) -> dict[str, str]:
    return {
        "run_id": seed * 16,
        "resource_fingerprint": seed * 64,
        "chapter_sha256": "b" * 64,
        "start_sha256": "c" * 64,
    }


def hold_lease(directory: str, connection: object) -> None:
    lease = d4_ui_lease.D4UILease(**binding("a"), lease_seconds=30, _test_directory=Path(directory))
    lease.acquire()
    connection.send("locked")
    connection.recv()
    lease.release()


def acquire_then_exit(directory: str, connection: object) -> None:
    lease = d4_ui_lease.D4UILease(**binding("a"), lease_seconds=30, _test_directory=Path(directory))
    lease.acquire()
    connection.send("locked")
    connection.close()
    os._exit(19)


class D4UILeaseTests(unittest.TestCase):
    def test_fork_during_release_fsync_cannot_inherit_untracked_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            status_read, status_write = os.pipe()
            control_read, control_write = os.pipe()
            controller_pid = os.fork()
            if controller_pid == 0:
                os.close(status_read)
                os.close(control_write)
                release_gap = threading.Event()
                lease = d4_ui_lease.D4UILease(
                    **binding("a"), lease_seconds=30, _test_directory=Path(temporary)
                ).acquire()
                target_descriptor = lease._descriptor
                real_fsync = d4_ui_lease.os.fsync

                def paused_fsync(descriptor: int) -> None:
                    real_fsync(descriptor)
                    if descriptor == target_descriptor:
                        release_gap.set()
                        threading.Event().wait(10)

                d4_ui_lease.os.fsync = paused_fsync
                releasing = threading.Thread(target=lease.release)
                releasing.start()
                if not release_gap.wait(10):
                    os._exit(81)
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=r"This process .* is multi-threaded, use of fork\(\) may lead to deadlocks",
                        category=DeprecationWarning,
                    )
                    keeper_pid = os.fork()
                if keeper_pid == 0:
                    os.write(status_write, b"K")
                    os.read(control_read, 1)
                    os.write(status_write, b"X")
                    os._exit(0)
                os.write(status_write, b"P")
                os._exit(23)

            os.close(status_write)
            os.close(control_read)
            try:
                markers = os.read(status_read, 2)
                while len(markers) < 2:
                    markers += os.read(status_read, 2 - len(markers))
                self.assertEqual(set(markers), {ord("K"), ord("P")})
                waited_pid, wait_status = os.waitpid(controller_pid, 0)
                self.assertEqual(waited_pid, controller_pid)
                self.assertEqual(os.waitstatus_to_exitcode(wait_status), 23)
                with d4_ui_lease.D4UILease(
                    **binding("d"), lease_seconds=30, _test_directory=Path(temporary)
                ) as lease:
                    self.assertGreater(lease.check(**binding("d")), 0)
            finally:
                os.write(control_write, b"x")
                os.close(control_write)
            self.assertEqual(os.read(status_read, 1), b"X")
            os.close(status_read)

    def test_concurrent_fork_cannot_inherit_unregistered_acquisition_fd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            status_read, status_write = os.pipe()
            control_read, control_write = os.pipe()
            controller_pid = os.fork()
            if controller_pid == 0:
                os.close(status_read)
                os.close(control_write)
                acquired_gap = threading.Event()
                resume_acquire = threading.Event()
                fork_started = threading.Event()
                fork_returned = threading.Event()
                real_flock = d4_ui_lease.fcntl.flock
                holder = []

                def paused_flock(descriptor: int, operation: int) -> None:
                    real_flock(descriptor, operation)
                    if operation == (d4_ui_lease.fcntl.LOCK_EX | d4_ui_lease.fcntl.LOCK_NB):
                        acquired_gap.set()
                        if not resume_acquire.wait(10):
                            os._exit(71)

                d4_ui_lease.fcntl.flock = paused_flock

                def acquire_in_window() -> None:
                    holder.append(d4_ui_lease.D4UILease(
                        **binding("a"), lease_seconds=30, _test_directory=Path(temporary)
                    ).acquire())

                def fork_keeper() -> None:
                    fork_started.set()
                    with warnings.catch_warnings():
                        warnings.filterwarnings(
                            "ignore",
                            message=r"This process .* is multi-threaded, use of fork\(\) may lead to deadlocks",
                            category=DeprecationWarning,
                        )
                        keeper_pid = os.fork()
                    if keeper_pid == 0:
                        os.write(status_write, b"K")
                        os.read(control_read, 1)
                        os.write(status_write, b"X")
                        os._exit(0)
                    fork_returned.set()

                acquisition = threading.Thread(target=acquire_in_window)
                acquisition.start()
                if not acquired_gap.wait(10):
                    os._exit(72)
                forking = threading.Thread(target=fork_keeper)
                forking.start()
                if not fork_started.wait(10):
                    os._exit(73)
                time.sleep(0.05)
                if fork_returned.is_set():
                    os._exit(74)
                resume_acquire.set()
                acquisition.join(10)
                forking.join(10)
                if acquisition.is_alive() or forking.is_alive() or len(holder) != 1:
                    os._exit(75)
                os.write(status_write, b"P")
                os._exit(23)

            os.close(status_write)
            os.close(control_read)
            try:
                markers = os.read(status_read, 2)
                while len(markers) < 2:
                    markers += os.read(status_read, 2 - len(markers))
                self.assertEqual(set(markers), {ord("K"), ord("P")})
                waited_pid, wait_status = os.waitpid(controller_pid, 0)
                self.assertEqual(waited_pid, controller_pid)
                self.assertEqual(os.waitstatus_to_exitcode(wait_status), 23)
                with d4_ui_lease.D4UILease(
                    **binding("d"), lease_seconds=30, _test_directory=Path(temporary)
                ) as lease:
                    self.assertGreater(lease.check(**binding("d")), 0)
            finally:
                os.write(control_write, b"x")
                os.close(control_write)
            self.assertEqual(os.read(status_read, 1), b"X")
            os.close(status_read)

    def test_fork_child_does_not_keep_lock_after_parent_abnormal_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            status_read, status_write = os.pipe()
            control_read, control_write = os.pipe()
            controller_pid = os.fork()
            if controller_pid == 0:
                os.close(status_read)
                os.close(control_write)
                lease = d4_ui_lease.D4UILease(
                    **binding("a"), lease_seconds=30, _test_directory=Path(temporary)
                ).acquire()
                keeper_pid = os.fork()
                if keeper_pid == 0:
                    os.write(status_write, b"K")
                    os.read(control_read, 1)
                    os.write(status_write, b"X")
                    os._exit(0)
                os.write(status_write, b"P")
                os._exit(23)

            os.close(status_write)
            os.close(control_read)
            try:
                markers = os.read(status_read, 2)
                while len(markers) < 2:
                    markers += os.read(status_read, 2 - len(markers))
                self.assertEqual(set(markers), {ord("K"), ord("P")})
                waited_pid, wait_status = os.waitpid(controller_pid, 0)
                self.assertEqual(waited_pid, controller_pid)
                self.assertEqual(os.waitstatus_to_exitcode(wait_status), 23)
                with d4_ui_lease.D4UILease(
                    **binding("d"), lease_seconds=30, _test_directory=Path(temporary)
                ) as lease:
                    self.assertGreater(lease.check(**binding("d")), 0)
            finally:
                os.write(control_write, b"x")
                os.close(control_write)
            self.assertEqual(os.read(status_read, 1), b"X")
            os.close(status_read)

    def test_live_process_collision_and_foreign_binding_rejected(self) -> None:
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as temporary:
            parent, child = context.Pipe()
            process = context.Process(target=hold_lease, args=(temporary, child))
            process.start()
            self.assertTrue(parent.poll(10))
            self.assertEqual(parent.recv(), "locked")
            contender = d4_ui_lease.D4UILease(
                **binding("d"), lease_seconds=30, _test_directory=Path(temporary)
            )
            with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_unavailable"):
                contender.acquire()
            parent.send("release")
            process.join(10)
            self.assertEqual(process.exitcode, 0)

            current = binding("a")
            with d4_ui_lease.D4UILease(
                **current, lease_seconds=30, _test_directory=Path(temporary)
            ) as lease:
                foreign = dict(current)
                foreign["resource_fingerprint"] = "e" * 64
                with self.assertRaisesRegex(d4_ui_lease.LeaseError, "foreign_lease_binding"):
                    lease.check(**foreign)

    def test_expired_lease_fails_closed_before_dispatch_and_cannot_renew(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            current = binding("a")
            called = []
            lease = d4_ui_lease.D4UILease(
                **current, lease_seconds=0.01, _test_directory=Path(temporary)
            ).acquire()
            time.sleep(0.03)
            with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_expired"):
                lease.dispatch(called.append, "called", binding=current)
            self.assertEqual(called, [])
            with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_expired"):
                lease.renew(30, **current)
            lease.release()

    def test_dispatch_crossing_deadline_cannot_return_success_or_retry_callback(self) -> None:
        class CallbackFailure(Exception):
            pass

        with tempfile.TemporaryDirectory() as temporary:
            current = binding("a")
            effects = []
            with d4_ui_lease.D4UILease(
                **current, lease_seconds=0.02, _test_directory=Path(temporary)
            ) as lease:
                def slow_operation() -> str:
                    effects.append("once")
                    time.sleep(0.04)
                    return "must-not-return"

                with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_expired"):
                    lease.dispatch(slow_operation, binding=current)
                self.assertEqual(effects, ["once"])

            with d4_ui_lease.D4UILease(
                **current, lease_seconds=0.02, _test_directory=Path(temporary)
            ) as lease:
                def failing_operation() -> None:
                    effects.append("failure")
                    time.sleep(0.04)
                    raise CallbackFailure("original callback failure")

                with self.assertRaisesRegex(CallbackFailure, "original callback failure"):
                    lease.dispatch(failing_operation, binding=current)
                self.assertEqual(effects, ["once", "failure"])

    def test_release_and_object_reuse_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            current = binding("a")
            lease = d4_ui_lease.D4UILease(
                **current, lease_seconds=30, _test_directory=Path(temporary)
            ).acquire()
            self.assertGreater(lease.check(**current), 0)
            self.assertGreater(lease.renew(30, **current), 0)
            lease.release()
            with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_not_active"):
                lease.check(**current)
            with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_not_active"):
                lease.release()
            with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_reused"):
                lease.acquire()

    def test_renew_metadata_failure_expires_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            current = binding("a")
            with d4_ui_lease.D4UILease(
                **current, lease_seconds=30, _test_directory=Path(temporary)
            ) as lease:
                with mock.patch.object(
                    lease,
                    "_write_metadata",
                    side_effect=d4_ui_lease.LeaseError("lease_metadata_rejected"),
                ):
                    with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_metadata_rejected"):
                        lease.renew(60, **current)
                with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_expired"):
                    lease.check(**current)

    def test_abnormal_process_exit_releases_kernel_lock(self) -> None:
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as temporary:
            parent, child = context.Pipe()
            process = context.Process(target=acquire_then_exit, args=(temporary, child))
            process.start()
            self.assertTrue(parent.poll(10))
            self.assertEqual(parent.recv(), "locked")
            process.join(10)
            self.assertEqual(process.exitcode, 19)
            with d4_ui_lease.D4UILease(
                **binding("d"), lease_seconds=30, _test_directory=Path(temporary)
            ) as lease:
                self.assertGreater(lease.check(**binding("d")), 0)

    def test_private_directory_file_and_symlink_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "lease"
            current = binding("a")
            with d4_ui_lease.D4UILease(
                **current, lease_seconds=30, _test_directory=directory
            ) as lease:
                self.assertGreater(lease.check(**current), 0)
            lock_file = directory / d4_ui_lease.LOCK_FILE_NAME
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(lock_file.stat().st_mode), 0o600)

            lock_file.chmod(0o644)
            with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_file_rejected"):
                d4_ui_lease.D4UILease(
                    **current, lease_seconds=30, _test_directory=directory
                ).acquire()
            lock_file.chmod(0o600)
            with mock.patch.object(d4_ui_lease.os, "getuid", return_value=os.getuid() + 1):
                with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_directory_rejected"):
                    d4_ui_lease.D4UILease(
                        **current, lease_seconds=30, _test_directory=directory
                    ).acquire()

            directory.chmod(0o755)
            with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_directory_rejected"):
                d4_ui_lease.D4UILease(
                    **current, lease_seconds=30, _test_directory=directory
                ).acquire()

            target = root / "target"
            target.mkdir(mode=0o700)
            symlink = root / "symlink"
            symlink.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(d4_ui_lease.LeaseError, "lease_directory_rejected"):
                d4_ui_lease.D4UILease(
                    **current, lease_seconds=30, _test_directory=symlink
                ).acquire()


if __name__ == "__main__":
    unittest.main()
