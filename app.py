import os
import io
import sys
import json
import zipfile
from pathlib import Path
from typing import List

import streamlit as st
from xhtml2pdf import pisa

# --- src 모듈 임포트 세팅 ---
# 프로젝트 루트/app.py 기준으로 src 경로 추가
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.append(
    str(ROOT)
)  # src를 패키지로 임포트 가능하게 (src.__init__ 없어도 상대 import용)
sys.path.append(str(SRC))

# --- 내부 모듈 임포트 ---
from presto.pipeline import run_pipeline, load_template_catalog, catalog_to_prompt  # type: ignore # noqa: E402
from presto.models import DeckPlan, SlideHTML  # type: ignore # noqa: E402


# =============== Streamlit UI ===============
st.set_page_config(page_title="PPT 자동생성 AI", layout="wide")
st.title("📑 PPT 자동생성 AI (LangChain + Streamlit)")

with st.sidebar:
    st.header("⚙️ 설정")
    model = st.text_input("모델 이름", value="gpt-4o-mini")
    max_concurrency = st.number_input(
        "동시성 (슬라이드 렌더링)", min_value=1, max_value=32, value=6, step=1
    )
    template_dir = st.text_input("템플릿 폴더 경로", value=str(ROOT / "templates"))
    st.caption(
        "※ 환경변수 OPENAI_API_KEY 필수. OPENAI_BASE_URL 사용 시 프록시/호환 서버로 전환됩니다."
    )

# 사용자 입력
st.subheader("🧑‍💼 사용자 요청(프롬프트)")
user_req_default = (
    "Create an investor-focused deck for an 'AI-powered PPT auto-generation' product. "
    "Audience: seed/Series A VCs. Include problem, solution, product demo outline, "
    "TAM/SAM/SOM with reasonable numbers, GTM, competition & differentiation (Gamma/Tome/Canva), "
    "pricing, roadmap(6-12 months), and KPIs."
)
user_request = st.text_area(
    "요청 내용을 입력하세요:", value=user_req_default, height=160
)

col_run1, col_run2 = st.columns([1, 2])
with col_run1:
    run_btn = st.button("🚀 생성 실행", use_container_width=True)

# 세션 상태 초기화
if "deck_plan" not in st.session_state:
    st.session_state.deck_plan: DeckPlan | None = None
if "slides" not in st.session_state:
    st.session_state.slides: List[SlideHTML] = []
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

# 실행
if run_btn:
    if not os.getenv("OPENAI_API_KEY"):
        st.error("환경변수 OPENAI_API_KEY가 설정되어 있지 않습니다.")
    else:
        with st.spinner("LLM으로 기획 생성 → 슬라이드 HTML 렌더링 중..."):
            try:
                deck_plan, rendered = run_pipeline(
                    user_request=user_request,
                    model=model,
                    max_concurrency=int(max_concurrency),
                )
                st.session_state.deck_plan = deck_plan
                st.session_state.slides = rendered
                st.success(f"생성 완료! 총 {len(rendered)}개 슬라이드.")
            except Exception as e:
                st.exception(e)

# 결과 시각화
deck_plan = st.session_state.deck_plan
slides = st.session_state.slides

if deck_plan and slides:
    tabs = st.tabs(["🗂 Deck Plan", "🖼 Slides Preview", "📦 Export"])

    # --- Tab 1: Deck Plan 구조 데이터 ---
    with tabs[0]:
        st.subheader("Deck Plan (Pydantic)")
        st.json(json.loads(deck_plan.model_dump_json()), expanded=False)

        # 표 형태(간단)로 슬라이드 목록
        rows = []
        print(deck_plan.slides)
        for s in deck_plan.slides:
            print(f"{s.numbers=}")
            rows.append(
                {
                    "slide_id": s.slide_id,
                    "title": s.title,
                    "key_points": " | ".join(s.key_points[:5]),
                    "numbers": (
                        ", ".join([f"{k}:{v}" for k, v in list(s.numbers.items())[:5]])
                        if s.numbers
                        else ""
                    ),
                    "section": s.section or "",
                }
            )
        st.dataframe(rows, use_container_width=True)

    # --- Tab 2: Slides Preview ---
    with tabs[1]:
        st.subheader("Rendered Slides (HTML)")
        st.caption("아래 미리보기는 각 슬라이드의 최종 HTML을 임베드한 것입니다.")
        # 간단한 공통 스타일(옵션)
        base_css = """
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans KR", sans-serif; margin: 0; padding: 0; }
          .slide { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 18px; }
          .slide h2 { margin-top: 0; }
          .two-col .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
          .metrics { margin-top: 10px; font-size: 14px; color: #555; }
          footer { margin-top: 12px; color: #666; font-size: 12px; }
        </style>
        """
        for s in sorted(slides, key=lambda x: x.slide_id):
            st.markdown(
                f"**Slide {s.slide_id} — Template: `{s.template_name}` — {deck_plan.slides[s.slide_id-1].title if s.slide_id-1 < len(deck_plan.slides) else ''}**"
            )
            html_doc = f"<!doctype html><html><head><meta charset='utf-8'>{base_css}</head><body>{s.html}</body></html>"
            st.components.v1.html(html_doc, height=450, scrolling=False)

    # --- Tab 3: Export ---
    with tabs[2]:
        st.subheader("내보내기")
        # 1) 개별 HTML 파일 저장
        out_dir = ROOT / "out_slides"
        st.write(f"저장 경로: `{out_dir}`")
        if st.button("💾 슬라이드 HTML 파일로 저장", use_container_width=True):
            out_dir.mkdir(exist_ok=True)
            for s in slides:
                fname = out_dir / f"slide_{s.slide_id:02d}.html"
                html_doc = f"<!doctype html><html><head><meta charset='utf-8'></head><body>{s.html}</body></html>"
                fname.write_text(html_doc, encoding="utf-8")
            st.success(f"{len(slides)}개 슬라이드를 {out_dir}에 저장 완료!")

        # 2) ZIP 다운로드
        zip_bytes = io.BytesIO()
        with zipfile.ZipFile(
            zip_bytes, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zf:
            # Deck plan JSON
            zf.writestr(
                "deck_plan.json",
                deck_plan.model_dump_json(indent=2),
            )
            # Slides HTML
            for s in slides:
                html_doc = f"<!doctype html><html><head><meta charset='utf-8'></head><body>{s.html}</body></html>"
                zf.writestr(f"slides/slide_{s.slide_id:02d}.html", html_doc)
        zip_bytes.seek(0)

        st.download_button(
            label="⬇️ ZIP 다운로드 (deck_plan.json + slides/*.html)",
            data=zip_bytes,
            file_name="ppt_ai_output.zip",
            mime="application/zip",
            use_container_width=True,
        )

        st.divider()
        st.subheader("PDF로 내보내기 (xhtml2pdf 사용)")
        if st.button("⚙️ PDF 생성", use_container_width=True):
            with st.spinner("PDF 변환 중..."):
                # 1. 모든 슬라이드 HTML을 하나로 합치기
                combined_html = "".join(
                    f"<section>{s.html}</section>"
                    for s in sorted(slides, key=lambda x: x.slide_id)
                )

                # 2. 전체 HTML 문서 구성 (PDF 페이지 크기 및 스타일 지정)
                full_html = """
                <!doctype html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Presentation</title>
                    <style>
                        @page {
                            size: 1280px 720px; /* 16:9 aspect ratio */
                            margin: 0;
                        }
                        body {
                            margin: 0;
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans KR", sans-serif;
                        }
                        section {
                            width: 1280px;
                            height: 720px;
                            box-sizing: border-box;
                            padding: 40px;
                            page-break-after: always;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                            align-items: center;
                            text-align: center;
                        }
                        section:last-child {
                            page-break-after: auto;
                        }
                    </style>
                </head>
                <body>{combined_html}</body>
                </html>
                """

                # 3. PDF 생성
                pdf_bytes = io.BytesIO()
                pisa_status = pisa.CreatePDF(io.StringIO(full_html), dest=pdf_bytes)

                if not pisa_status.err:
                    st.session_state.pdf_bytes = pdf_bytes.getvalue()
                    st.success("PDF 생성 완료! 아래 버튼으로 다운로드하세요.")
                else:
                    st.error("PDF 생성 실패: {pisa_status.err}")

        if "pdf_bytes" in st.session_state and st.session_state.pdf_bytes:
            st.download_button(
                label="⬇️ 생성된 PDF 다운로드",
                data=st.session_state.pdf_bytes,
                file_name="presentation.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

# 템플릿 미리보기(사이드 유틸)
st.divider()
st.subheader("📚 템플릿 카탈로그 미리보기(읽기 전용)")
if os.path.isdir(template_dir):
    catalog = load_template_catalog(template_dir)
else:
    catalog = load_template_catalog("templates")  # fallback
st.text(f"총 {len(catalog)}개 템플릿 감지")
with st.expander("템플릿 원문 보기"):
    st.code(catalog_to_prompt(catalog), language="html")
