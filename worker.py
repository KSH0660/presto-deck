#!/usr/bin/env python3
"""
ARQ Worker entry point for Presto-Deck background tasks.

This is a convenience wrapper around the ARQ CLI.
The actual worker logic is in app.infrastructure.messaging.arq_config.WorkerSettings

Usage:
    python worker.py [extra args passed to ARQ]
    make worker
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import List, Tuple


ARQ_SETTINGS_PATH = "app.infrastructure.messaging.arq_config.WorkerSettings"


def _print_header() -> None:
    print("🚀 Starting Presto-Deck ARQ Worker...")
    print(f"📍 Settings: {ARQ_SETTINGS_PATH}")
    print(f"🐍 Python : {sys.executable} ({sys.version.split()[0]})")
    print()


def _ensure_project_root() -> None:
    if not os.path.exists("app"):
        print("❌ Error: Must run from the project root (missing 'app/' directory).")
        sys.exit(1)


def _quick_import_check() -> None:
    """
    빠른 임포트 체크로 경로/의존성 기본 이상 여부만 확인.
    (실제 리소스 연결은 ARQ startup 훅에서 이루어짐)
    """
    try:
        __import__("app.infrastructure.messaging.arq_config")
    except Exception as e:
        print(
            "❌ Import error: cannot import 'app.infrastructure.messaging.arq_config'"
        )
        print(f"   → {e}")
        print("💡 Tip: PYTHONPATH='.' 또는 가상환경/의존성(uv sync) 확인")
        sys.exit(1)


def _build_candidate_cmds(extra_argv: List[str]) -> List[Tuple[List[str], str]]:
    """
    시도할 실행 커맨드 후보를 우선순위대로 반환.
    각 후보 옆에 사용자에게 보여줄 설명 문자열을 함께 둔다.
    """
    arq_target = ARQ_SETTINGS_PATH
    return [
        (["uv", "run", "arq", arq_target, *extra_argv], "uv run (가상환경 일관 실행)"),
        (
            [sys.executable, "-m", "arq", arq_target, *extra_argv],
            "python -m arq (직접 모듈 실행)",
        ),
        (["arq", arq_target, *extra_argv], "arq (PATH 상의 실행파일)"),
    ]


def _print_cmd(cmd: List[str], label: str) -> None:
    print("=" * 72)
    print(f"🔧 Attempt via: {label}")
    print(f"▶️  {' '.join(cmd)}")
    print("=" * 72)


def _env_with_pythonpath() -> dict:
    env = os.environ.copy()
    # 프로젝트 루트 import 보장
    env["PYTHONPATH"] = env.get("PYTHONPATH", ".") or "."
    return env


def main() -> None:
    _print_header()
    _ensure_project_root()
    _quick_import_check()

    # 추가 인자(예: --watch, --burst 등)를 그대로 ARQ CLI로 전달
    extra_argv = sys.argv[1:]

    env = _env_with_pythonpath()
    candidates = _build_candidate_cmds(extra_argv)

    last_err: Exception | None = None
    for cmd, label in candidates:
        # 실행 파일 존재 여부(첫 토큰) 빠른 확인
        exe = cmd[0]
        if os.path.sep in exe or exe.endswith(".exe"):
            exists = os.path.exists(exe)
        else:
            exists = shutil.which(exe) is not None

        if not exists:
            # 다음 후보로
            continue

        _print_cmd(cmd, label)

        try:
            # check=False 로 실행해서 returncode를 직접 전달
            proc = subprocess.run(cmd, env=env)
            rc = proc.returncode

            if rc == 0:
                print("✅ Worker exited cleanly.")
            else:
                print(f"⚠️  Worker exited with code {rc}.")

            # 종료 코드 그대로 전파 (CI/CD에서 유용)
            sys.exit(rc)

        except FileNotFoundError as e:
            last_err = e
            # 다음 후보로 폴백
            continue
        except KeyboardInterrupt:
            print("\n👋 Worker interrupted by user")
            sys.exit(130)  # 128 + SIGINT
        except Exception as e:
            last_err = e
            print(f"❌ Error running command: {e}")
            # 다음 후보로 폴백
            continue

    # 여기까지 왔다면 모든 후보 실패
    print("❌ Failed to start ARQ worker: no viable runner found.")
    if last_err:
        print(f"   Last error: {last_err}")

    print("\n🔎 Troubleshooting checklist")
    print("  1) 가상환경/의존성 설치:   uv sync")
    print("  2) CLI 설치 여부 확인:     which uv / which arq")
    print(
        "  3) 파이썬 모듈 실행:        python -m arq app.infrastructure.messaging.arq_config.WorkerSettings"
    )
    print("  4) PYTHONPATH 확인:        export PYTHONPATH=.")
    print(
        "  5) Import 오류 상세:       python -c \"import app.infrastructure.messaging.arq_config; print('ok')\""
    )
    sys.exit(1)


if __name__ == "__main__":
    # 권장: 3.11+
    min_py = (3, 11)
    if sys.version_info < min_py:
        print(f"❌ Error: Python {min_py[0]}.{min_py[1]}+ is required")
        sys.exit(1)

    main()
