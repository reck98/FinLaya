"""Environment and dependency verification script."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def check_environment() -> bool:
    print("=" * 60)
    print("FinLaya Environment Verification")
    print("=" * 60)

    all_passed = True

    # 1. Python version
    py_ver = sys.version_info
    print(f"Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    if (py_ver.major, py_ver.minor) < (3, 11) or (py_ver.major, py_ver.minor) >= (3, 13):
        print("  [FAIL] Python version must be >= 3.11 and < 3.13")
        all_passed = False
    else:
        print("  [PASS] Python version compatible")

    # 2. Virtual environment
    in_venv = sys.prefix != sys.base_prefix or "VIRTUAL_ENV" in os.environ
    print(f"Virtual Environment Active: {in_venv} ({sys.prefix})")
    if not in_venv:
        print("  [WARN] Not running inside a virtual environment (.venv)")
    else:
        print("  [PASS] Virtual environment active")

    # 3. Core dependencies
    packages = [
        ("aiosqlite", "aiosqlite"),
        ("laya", "laya"),
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("protobuf", "google.protobuf"),
        ("pydantic", "pydantic"),
        ("rich", "rich"),
        ("torch", "torch"),
        ("transformers", "transformers"),
        ("typer", "typer"),
        ("upstox-python-sdk", "upstox_client"),
        ("websockets", "websockets"),
    ]

    print("\nPackage Verification:")
    for pkg_name, import_name in packages:
        try:
            mod = __import__(import_name)
            ver = getattr(mod, "__version__", "installed")
            print(f"  [PASS] {pkg_name}: {ver}")
        except ImportError as e:
            print(f"  [FAIL] {pkg_name} could not be imported: {e}")
            all_passed = False

    # 4. PyTorch & Acceleration
    try:
        import torch
        print(f"\nPyTorch Device Check:")
        print(f"  PyTorch Version: {torch.__version__}")
        print(f"  CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  Device Name: {torch.cuda.get_device_name(0)}")
    except Exception:
        pass

    # 5. Directory permissions
    print("\nDirectory Permissions:")
    for path_str in ["data", "data/logs", "data/runtime"]:
        p = Path(path_str)
        p.mkdir(parents=True, exist_ok=True)
        test_file = p / ".test_write"
        try:
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
            print(f"  [PASS] Write permission in {path_str}")
        except Exception as e:
            print(f"  [FAIL] Cannot write to {path_str}: {e}")
            all_passed = False

    # 6. SQLite check
    print("\nSQLite Database Check:")
    try:
        import sqlite3
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test (id INT);")
        cursor.execute("INSERT INTO test VALUES (1);")
        conn.commit()
        conn.close()
        print("  [PASS] In-memory SQLite operational")
    except Exception as e:
        print(f"  [FAIL] SQLite error: {e}")
        all_passed = False

    print("=" * 60)
    if all_passed:
        print("[SUCCESS] ALL CHECKS PASSED. Environment is ready for FinLaya.")
    else:
        print("[FAILURE] SOME CHECKS FAILED. Review issues above.")
    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    success = check_environment()
    sys.exit(0 if success else 1)
