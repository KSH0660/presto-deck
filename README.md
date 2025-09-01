# **[최종] Presto-Deck 서비스 개발 명세서 (For Coding Agent)**

## **개요**

  * **서비스명**: Presto-Deck
  * **목표**: 사용자의 프롬프트 입력을 기반으로 AI를 활용하여 고품질의 프레젠테이션 Deck을 생성, 실시간 스트리밍 및 수정을 지원하는 서비스 개발.
  * **핵심 철학**: 비동기 처리, 이벤트 기반 아키텍처, 데이터 무결성 보장, 높은 수준의 관측 가능성 확보.

-----

## **1. 시스템 아키텍처**

본 시스템은 \*\*PostgreSQL을 단일 진실 공급원(Source of Truth, SoT)\*\*으로 사용하며, **Redis는 메시징, 캐싱, 실시간 통신 보조**의 역할로 제한합니다. API 서버와 워커는 분리된 프로세스로 실행되며, 이벤트 버스를 통해 통신합니다.

  * **API 서버 (FastAPI)**: 사용자 요청(HTTP, WebSocket)을 처리합니다. 무거운 작업은 즉시 워커에게 위임하고, WebSocket을 통해 클라이언트와 실시간 통신을 유지합니다.
  * **워커 (ARQ + Python)**: 백그라운드에서 실행되며, LLM 호출, 슬라이드 생성 등 시간이 오래 걸리는 작업을 전담합니다. 작업의 모든 단계는 \*\*멱등성(Idempotent)\*\*을 보장해야 합니다.
  * **PostgreSQL (Primary Database)**: 모든 영속적 데이터(Deck, Slide, 사용자 정보, 이벤트 로그)를 저장하는 **단일 진실 공급원**입니다. 데이터 무결성과 트랜잭션을 보장합니다.
  * **Redis (In-Memory Data Store & Message Broker)**:
      * **작업 큐 (ARQ)**: API 서버가 워커에게 작업을 전달하는 채널.
      * **이벤트 버스 (Redis Streams)**: 워커에서 발생한 이벤트를 API 서버로 **안정적으로(Durable)** 전달하는 채널. Consumer Group과 ACK를 통해 메시지 유실을 방지합니다.
      * **브로드캐스트 (Redis Pub/Sub)**: 여러 API 서버 인스턴스에 WebSocket 메시지를 전파(Fan-out)하기 위한 용도.
      * **캐시/상태 저장소**: 작업 취소 플래그, 임시 상태 데이터 저장.

-----

## **2. 데이터 모델 및 스키마 (PostgreSQL)**

데이터베이스 스키마는 `Alembic`을 사용하여 관리합니다.

### **Tables**

```sql
-- Deck의 상태를 정의하는 ENUM 타입
CREATE TYPE deck_status AS ENUM ('PENDING', 'PLANNING', 'GENERATING', 'COMPLETED', 'FAILED', 'CANCELLED');

-- Decks Table
CREATE TABLE decks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL, -- 사용자 식별자 (Foreign Key)
    title VARCHAR(255) NOT NULL,
    status deck_status NOT NULL DEFAULT 'PENDING',
    version INTEGER NOT NULL DEFAULT 1, -- 이벤트 기반 상태 업데이트 버전
    deck_plan JSONB, -- Deck의 전체 흐름 및 계획
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Slides Table
CREATE TABLE slides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deck_id UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    slide_order INTEGER NOT NULL,
    html_content TEXT NOT NULL,
    presenter_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (deck_id, slide_order) -- 한 Deck 내에서 슬라이드 순서는 고유해야 함
);

-- Deck Events Table (Audit & Replay 용도)
CREATE TABLE deck_events (
    id BIGSERIAL PRIMARY KEY,
    deck_id UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

-----

## **3. 핵심 워크플로우 (이벤트 기반 시퀀스)**

1.  **[Client → API]**: 사용자가 Deck 생성 요청 (`POST /api/v1/decks`).
2.  **[API]**:
      * `decks` 테이블에 새로운 레코드 생성 (status: `PENDING`).
      * ARQ를 통해 `generate_deck` 작업을 Redis 큐에 추가.
      * **즉시 `202 Accepted` 응답과 함께 `deck_id` 반환.**
3.  **[Client]**: `deck_id`를 받아 WebSocket 연결 요청 (`WS /ws/decks/{deck_id}`).
4.  **[Worker]**: Redis 큐에서 `generate_deck` 작업 수신.
      * **멱등성 체크**: `deck_id`와 현재 상태를 DB에서 확인 후 중복/완료된 작업이면 종료.
      * `decks` 테이블 상태를 `PLANNING`으로 업데이트하고 `version` 증가.
      * **`DeckStarted` 이벤트를 Redis Streams에 발행.**
      * LLM을 호출하여 Deck Plan 생성 후 DB에 저장.
      * **`PlanUpdated` 이벤트를 Redis Streams에 발행.**
5.  **[API]**: (별도 리스너) Redis Streams를 구독하고 있다가 이벤트를 수신. Redis Pub/Sub을 통해 해당 `deck_id` 채널을 구독 중인 모든 API 인스턴스에 이벤트 브로드캐스트.
6.  **[API → Client]**: WebSocket을 통해 클라이언트에게 `DeckStarted`, `PlanUpdated` 이벤트 전달.
7.  **[Worker]**: Deck Plan에 따라 슬라이드를 순차적으로 생성하는 루프 시작.
      * **루프 시작 전 취소 플래그 확인 (Redis).**
      * 슬라이드 하나를 생성.
      * `slides` 테이블에 슬라이드 데이터 저장 (트랜잭션).
      * `decks` 테이블의 `version` 증가.
      * **`SlideAdded` 이벤트를 Redis Streams에 발행.**
      * (API를 통해 Client에게 `SlideAdded` 이벤트 전달 반복)
8.  **[Worker]**: 모든 슬라이드 생성 완료.
      * `decks` 테이블 상태를 `COMPLETED`로 업데이트.
      * **`DeckCompleted` 이벤트를 Redis Streams에 발행.**
9.  **[API → Client]**: WebSocket으로 `DeckCompleted` 이벤트 전달 및 연결 종료 로직 준비.

-----

## **4. API 명세 (v1)**

### **HTTP Endpoints**

  * `POST /api/v1/decks`
      * **설명**: 새로운 Deck 생성을 시작.
      * **Body**: `(DeckCreationRequest)` - 주제, 템플릿, 테마 등.
      * **응답 (202 Accepted)**: `{"deck_id": "...", "status": "PENDING"}`
  * `GET /api/v1/decks/{deck_id}`
      * **설명**: 특정 Deck의 현재 상태와 생성된 슬라이드 전체를 조회.
      * **응답 (200 OK)**: `(DeckResponse)` - Deck 메타데이터 및 `slides` 리스트 포함.
  * `POST /api/v1/decks/{deck_id}/cancel`
      * **설명**: 진행 중인 Deck 생성을 취소.
      * **응답 (202 Accepted)**: `{"message": "Cancellation request received."}`

### **WebSocket Endpoint**

  * `WS /ws/decks/{deck_id}?last_version={version}`
      * **연결**:
          * **인증**: 연결 핸드셰이크 시 JWT 토큰 검증 필수.
          * **권한**: 요청한 `user_id`가 해당 `deck_id`의 소유주인지 DB에서 확인.
      * **리플레이 (Replay)**:
          * 클라이언트가 `last_version` 쿼리 파라미터를 제공하면, 서버는 `deck_events` 테이블 또는 Redis Streams에서 해당 버전 이후의 모든 이벤트를 순서대로 클라이언트에게 전송하여 상태를 복구시킴.
      * **서버 → 클라이언트 메시지**: `Event` 스키마를 따름 (아래 5번 항목 참조).
      * **클라이언트 → 서버 메시지**: 슬라이드 수정/추가/삭제 요청. (예: `{"type": "UpdateSlide", "data": {"slide_id": "...", "prompt": "..."}}`)

-----

## **5. 이벤트 계약 (Event Contract)**

모든 서버-클라이언트, 워커-서버 간 이벤트는 아래의 표준 Pydantic 스키마를 준수합니다.

```python
# app/schemas/events.py (Pydantic v2)
from typing import Literal, Annotated, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

EventType = Literal[
  "DeckStarted", "PlanUpdated", "SlideAdded", "SlideUpdated",
  "DeckCompleted", "DeckFailed", "DeckCancelled", "Heartbeat"
]

class Event(BaseModel):
    event_type: EventType
    deck_id: str
    version: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict)
```

  * **`payload` 예시 (`SlideAdded`)**: `{"slide_id": "...", "order": 3, "html_content": "<h1>...</h1>"}`

-----

## **6. 기술 스택 및 라이브러리**

  * **Backend**: Python 3.11+, FastAPI, Pydantic V2
  * **Database**: PostgreSQL 15+
  * **DB Driver/ORM**: `psycopg[binary]`, `SQLAlchemy 2.0` (Core 또는 ORM)
  * **DB Migration**: `Alembic`
  * **Async Task Queue**: `arq`
  * **LLM Integration**: `LangChain` (Structured Output 활용)
  * **Dependency Management**: `uv`
  * **Testing**: `pytest`, `pytest-asyncio`, `httpx`
  * **Security**: `python-jose` (JWT), `bleach` (HTML Sanitize)

-----

## **7. 핵심 요구사항 (Non-functional)**

  * **보안**:
      * 모든 API 엔드포인트(WebSocket 포함)는 JWT 기반 인증을 통과해야 합니다.
      * 사용자는 자신의 Deck에만 접근할 수 있어야 합니다 (소유권 검증).
      * LLM이 생성한 모든 HTML 콘텐츠는 서버에서 `bleach` 라이브러리를 사용해 XSS 공격 방지를 위해 Sanitize 처리 후 DB에 저장해야 합니다.
  * **안정성 및 재시도**:
      * 모든 워커 작업은 \*\*멱등성(idempotent)\*\*을 가져야 합니다.
      * LLM 및 외부 API 호출 실패 시 \*\*지수 백오프(exponential backoff)\*\*를 적용한 재시도 로직을 구현해야 합니다.
      * 모든 외부 호출에 적절한 **타임아웃**을 설정해야 합니다.
  * **관측 가능성 (Observability)**:
      * `OpenTelemetry`를 사용하여 분산 추적(Distributed Tracing)을 구현합니다. `deck_id`가 Trace ID의 일부가 되어 요청의 전체 생명주기를 추적할 수 있어야 합니다.
      * `Prometheus`를 통해 주요 메트릭(큐 대기 시간, 슬라이드 생성 속도, LLM 토큰 사용량/비용, 에러율)을 수집합니다.
      * 구조화된 로깅(JSON 형식)을 적용합니다.
  * **확장성**:
      * API 서버와 워커는 독립적으로 스케일 아웃이 가능해야 합니다.

-----

## **8. 테스트 및 검증**

  * **단위 테스트**: 서비스 계층의 비즈니스 로직을 LLM, DB 모킹을 통해 테스트합니다.
  * **통합 테스트**: 실제 PostgreSQL, Redis 인스턴스를 사용하여 API부터 워커까지의 전체 워크플로우를 검증합니다. 특히 WebSocket 이벤트 리플레이 시나리오를 포함해야 합니다.
  * **E2E 테스트**: 실제 클라이언트와 유사한 환경에서 전체 시나리오를 테스트합니다.
  * **부하 테스트**: `Locust` 또는 `k6`를 사용하여 동시 WebSocket 연결 및 Deck 생성 요청에 대한 성능을 측정합니다.

-----

## **9. 프로젝트 구조 (Ports & Adapters 제안)**

코드의 유지보수성과 테스트 용이성을 극대화하기 위해 Ports & Adapters (Hexagonal) 아키텍처를 채택합니다.

```
backend/
├── app/
│   ├── api/                # FastAPI 라우터, 요청/응답 DTO (Schemas)
│   ├── application/        # 유스케이스 구현 (DeckService 등), 트랜잭션 경계
│   ├── domain/             # 핵심 도메인 모델 (Deck, Slide 엔티티), 비즈니스 규칙
│   ├── infrastructure/     # 외부 시스템 연동 구현체 (Adapters)
│   │   ├── db/             # PostgreSQL Repository 구현
│   │   ├── llm/            # LangChain 클라이언트 구현
│   │   └── messaging/      # Redis (ARQ, Streams) 구현
│   └── core/               # 설정, 의존성 주입 등 공통 기능
├── tests/
└── main.py
```