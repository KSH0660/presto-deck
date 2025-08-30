사용자에겐 다음과 같은 플로우를 제시하고 싶어.

# 1) 처음 사용자가 접속해서, 본인이 만들고자 하는 덱에 관련된 요청사항 + 파일 등을 업로드. 그 다음 submit 버튼.

# 2) 출력된 DeckPlan 를 사용자에게 출력.

    topic: str
    audience: str
    theme: Optional[str] = None
    color_preference: Optional[str] = None
    slides: List[SlideSpec]

공통사항: topic, audience, theme, color_preference 등
각 슬라이드 별: SlideSpec 리스트

class SlideContent(BaseModel):
    """Slide content without layout information."""

    slide_id: int
    title: str
    key_points: Optional[List[str]] = None  # bullet points
    numbers: Optional[Dict[str, float]] = None  # KPI/지표
    notes: Optional[str] = None
    section: Optional[str] = None


class SlideSpec(SlideContent):
    """Slide content with layout candidates."""

    layout_candidates: Optional[List[str]] = None

를 사용자에게 보여주고, 사용자가 여기서 각 항목을 수정할 수 있도록.
완료 버튼 후 제출


# 3. 각 장을 render. 렌더 결과 후에도 사용자가 자연어로 수정 가능
확정된 SlideSpec 을 기반으로 개별 슬라이드 렌더링


# 공통.
- 환경설정은 uv add "pakage" 또는 uv pip install 로.
- 각 과정에서 각 llm 토큰 사용량, 걸린 시간 등 모니터링을 편하게 할 수잇는 프레임워크 도입.
- reddis DB 사용
- pytest 를 통해 테스트 커버리지 확보 (90% 이상); uv run pytest 통과 목표.
- 시스템 설계의 지침은 "what_is_good_system.md" 를 참고할 것!
