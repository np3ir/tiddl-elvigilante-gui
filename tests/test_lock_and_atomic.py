"""Download lock is exclusive; settings writes are atomic."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402


def test_lock_is_exclusive_and_stale_is_reclaimed(tmp_path, monkeypatch):
    lock = tmp_path / "dl.lock"
    monkeypatch.setattr(main, "download_lock_path", lambda: lock)
    assert main.acquire_download_lock()
    # a live OTHER process holds it -> refuse
    lock.write_text("1", encoding="utf-8")
    monkeypatch.setattr(main, "_pid_alive", lambda pid: True)
    assert not main.acquire_download_lock()
    assert lock.read_text(encoding="utf-8") == "1"
    # holder died -> reclaim
    monkeypatch.setattr(main, "_pid_alive", lambda pid: False)
    assert main.acquire_download_lock()
    assert lock.read_text(encoding="utf-8") == str(os.getpid())


def test_write_text_atomic_replaces_and_leaves_no_tmp(tmp_path):
    f = tmp_path / "sub" / "gui.json"
    main.write_text_atomic(f, "a")
    main.write_text_atomic(f, "b")
    assert f.read_text(encoding="utf-8") == "b"
    assert [p.name for p in f.parent.iterdir()] == ["gui.json"]
