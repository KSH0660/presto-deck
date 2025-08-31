
사용자 입장 UX 플로우

# 1. 본인이 만들고자 하는 덱 요청사항 자연어로 입력 후 제출

# 2. 1차적으로 만들어진 Deck Plan 를 사용자에게 제시. 필요시 수정 후 제출
## endpoint (/decks/{deck_id}/plan) 코드 :   `app/api/v1/decks.py`

# 3. 각 슬라이드 id 별로 렌더링 되어 나타날 위치가 정해져있으며, 스트리밍 도착하는 순서대로 각 슬라이드 위치에서 서서히 나타나는 효과.
## api endpoint (/decks/{deck_id}/render/stream) 위치: `app/api/v1/decks.py`

# 4. 사용자가 자연어로 수정 가능. (/decks/{deck_id}/slides/{slide_id}/edit)
## `app/api/v1/decks.py`


# 공통.
- 환경설정은 uv add "pakage"
- backend: fastapi
- frontend: htmx (예제는 htmx_example.md 참고) & tailwindcss
- 참고 업체 UI: reference/gensparkai
- reddis DB 사용
- pytest 를 통해 uv run pytest 통과 목표.
- 시스템 설계의 지침은 "what_is_good_system.md" 를 참고할 것!
