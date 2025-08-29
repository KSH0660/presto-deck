# app/core/state.py

"""인메모리 상태 및 안전한 ID 생성기."""

from itertools import count
from typing import List, Dict, Any

# In-memory store for slides (for MVP)
slides_db: List[Dict[str, Any]] = []

# Monotonic counter for slide IDs
_slide_id_counter = count(1)


def reset_slide_ids(start: int = 1) -> None:
    """슬라이드 ID 카운터를 재설정합니다."""
    global _slide_id_counter
    _slide_id_counter = count(start)


def get_next_slide_id() -> int:
    """다음 슬라이드 ID를 반환합니다."""
    return next(_slide_id_counter)
