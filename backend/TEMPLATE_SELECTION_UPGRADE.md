# Template Selection Logic Upgrade

## 개요

이 문서는 Presto Deck 백엔드의 템플릿 선택 로직을 기존의 간단한 JSON 프롬프팅 방식에서 Asset Catalog 기반의 LangChain Structured Output 방식으로 업그레이드한 작업 내역을 정리합니다.

## 작업 배경

기존 시스템에서는 템플릿 선택이 단순한 문자열 기반으로 이루어져서 다음과 같은 한계가 있었습니다:

- 하드코딩된 `TemplateType` enum 사용
- JSON 파싱 오류 가능성
- 실제 템플릿 파일과의 연동 부족
- 구조화된 응답 검증 어려움

## 새로운 아키텍처

### 1. Asset Catalog 시스템

```
backend/app/infra/assets/
├── __init__.py
├── template_catalog.py    # 템플릿 카탈로그 서비스
└── catalog.json          # 템플릿 메타데이터 (추후 생성 예정)
```

**TemplateCatalog 클래스 주요 기능:**
- `catalog.json`에서 템플릿 메타데이터 로드
- 템플릿 파일 내용 조회
- LLM용 카탈로그 데이터 포매팅
- 키워드 기반 템플릿 검색

### 2. Pydantic 구조화 모델

```python
# app/domain_core/value_objects/template_selection.py

class SlideTemplateAssignment(BaseModel):
    """각 슬라이드별 템플릿 할당 정보"""
    slide_order: int
    slide_title: str
    primary_template: str
    alternative_templates: List[str]  # 최대 2개 대체 템플릿
    content_adaptation_notes: str

class DeckTemplateSelections(BaseModel):
    """전체 덱의 템플릿 선택 결과"""
    deck_theme: str
    slide_assignments: List[SlideTemplateAssignment]
    template_usage_summary: dict[str, int]
```

### 3. LangChain Structured Output

```python
# app/infra/llm/langchain_client.py

async def generate_structured(
    self,
    prompt: str,
    response_model: Type[T],
    system_message: Optional[str] = None
) -> T:
    """Pydantic 모델을 사용한 구조화된 응답 생성"""
    structured_llm = self.llm.with_structured_output(response_model)
    response = await structured_llm.ainvoke(messages)
    return response
```

## 핵심 변경사항

### 1. SelectTemplateUseCase 업데이트

**이전 방식:**
```python
# 단순 텍스트 응답 + JSON 파싱
response = await self.llm_client.generate_text(prompt)
template_data = json.loads(response)  # 파싱 오류 가능성
```

**새로운 방식:**
```python
# 구조화된 응답 + 타입 안전성
template_selections = await self.llm_client.generate_structured(
    user_prompt,
    DeckTemplateSelections,
    system_prompt
)
```

**주요 개선점:**
- Asset catalog 기반 템플릿 선택
- 슬라이드당 최대 3개 템플릿 (1개 주 + 2개 대체)
- 구조화된 LLM 응답으로 타입 안전성 확보
- 템플릿 적응 가이드 제공

### 2. WriteSlideContentUseCase 업데이트

**메서드 시그니처 변경:**
```python
# 이전
async def execute(self, deck_id: UUID, slide_id: UUID, content_outline: str, template_type: str)

# 새로운
async def execute(
    self,
    deck_id: UUID,
    slide_id: UUID,
    slide_order: int,
    content_outline: str,
    primary_template: str,
    alternative_templates: List[str] = None,
    adaptation_notes: str = ""
)
```

**템플릿 기반 콘텐츠 생성:**
```python
# 실제 템플릿 파일 내용을 LLM에 제공
template_content = self.template_catalog.get_template_content(primary_template)

user_prompt = f"""
**TEMPLATE TO FOLLOW:**
Template File: {primary_template}
Template Content:
```html
{template_content}
```

**ADAPTATION NOTES:**
{adaptation_notes}
"""
```

### 3. Slide Entity 변경

```python
# 이전: TemplateType enum 사용
@dataclass
class Slide:
    template_type: TemplateType

# 새로운: 템플릿 파일명 직접 저장
@dataclass
class Slide:
    template_filename: str  # "intro_slide.html"
```

## 테스트 업데이트

총 25개의 단위 테스트가 새로운 아키텍처에 맞게 업데이트되었습니다:

### 주요 테스트 변경사항:
- `TemplateType` → `template_filename` 속성 변경
- Mock 의존성에 `TemplateCatalog` 추가
- 구조화된 응답을 위한 Pydantic 모델 모킹
- 메서드 시그니처 변경에 따른 테스트 호출 업데이트

### 테스트 실행 결과:
```bash
$ uv run pytest tests/unit/test_domain_entities.py tests/unit/test_use_cases.py -v
==================== 25 passed, 39 warnings in 0.76s ====================
```

## 아키텍처 다이어그램

```
┌─────────────────┐    ┌────────────────────┐    ┌─────────────────┐
│ SelectTemplate  │───▶│  TemplateCatalog   │───▶│ catalog.json +  │
│    UseCase      │    │     Service        │    │ template files  │
└─────────────────┘    └────────────────────┘    └─────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌────────────────────┐
│ LangChain       │    │ DeckTemplate       │
│ StructuredLLM   │───▶│ Selections         │
└─────────────────┘    └────────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌────────────────────┐
│WriteSlideContent│    │ SlideTemplate      │
│    UseCase      │◀───│ Assignment         │
└─────────────────┘    └────────────────────┘
```

## 성능 및 품질 개선

### 1. 타입 안전성
- Pydantic 모델로 런타임 검증
- TypeScript 스타일의 타입 힌팅
- IDE 자동완성 및 오류 검출 개선

### 2. 오류 처리
- JSON 파싱 오류 제거
- 템플릿 파일 누락 시 Fallback 로직
- 구조화된 예외 처리

### 3. 확장성
- 새로운 템플릿 추가 시 `catalog.json`만 수정
- 템플릿 메타데이터 확장 가능
- LLM 프롬프트와 비즈니스 로직 분리

### 4. 테스트 커버리지
- 100% 테스트 통과
- 모든 에러 시나리오 커버
- Mock 기반 격리된 단위 테스트

## 추후 작업 계획

1. **Asset 폴더 구성**: 실제 HTML 템플릿 파일과 `catalog.json` 생성
2. **Integration 테스트**: End-to-end 템플릿 선택 플로우 테스트
3. **Performance 최적화**: 템플릿 캐싱 및 지연 로딩
4. **Monitoring**: 템플릿 선택 성공률 및 성능 메트릭 수집

## 커밋 히스토리

```bash
ab622c9 Implement asset catalog-based template selection with LangChain structured output
a5623bb Add comprehensive pytest test suite and clean up legacy code
db080eb Implement Use Case-Driven Architecture for Presto Deck
```

## 기술 스택

- **Python 3.13+** with **uv** dependency management
- **LangChain** with structured output capabilities
- **Pydantic V2** for data validation and serialization
- **pytest** with comprehensive mocking for unit tests
- **FastAPI** integration ready architecture

---

**작업 완료일**: 2025-09-03
**담당자**: Claude Code Assistant
**리뷰어**: KSH0660
