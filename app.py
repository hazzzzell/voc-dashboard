"""
VOC 대시보드 v2.1 - 엑셀 업로드 + Claude AI 심층 분석
채널톡 내보내기 파일 업로드 → 자동 분석 → Claude AI로 심층 분석
"""

import os
import time
import datetime
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(page_title="VOC 대시보드", page_icon="📋", layout="wide")

# ─────────────────────────────────────────────
# 커스텀 스타일
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #fafafa; }
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white; padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem;
    }
    .main-header h1 { margin: 0; font-size: 1.6rem; }
    .main-header p { margin: 0.3rem 0 0 0; opacity: 0.8; font-size: 0.9rem; }
    .stat-card {
        background: white; border: 1px solid #e8e8e8;
        border-radius: 10px; padding: 1.2rem; text-align: center;
    }
    .stat-card .number { font-size: 2rem; font-weight: 700; color: #1a1a2e; }
    .stat-card .label { font-size: 0.85rem; color: #888; margin-top: 0.3rem; }
    .cx-low {
        background: #FFF3F0; border: 1px solid #FFB4A2;
        border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.5rem;
    }
    .ai-tag {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 2px 8px; border-radius: 12px;
        font-size: 0.7rem; font-weight: 600; margin-left: 4px;
    }
    .sentiment-neg { color: #E63946; font-weight: 600; }
    .sentiment-pos { color: #2D6A4F; font-weight: 600; }
    .sentiment-neu { color: #888; font-weight: 600; }
    .type-badge {
        display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-size: 0.75rem; font-weight: 600; margin: 1px 2px;
    }
    .type-문의 { background: #E8F0FE; color: #1967D2; }
    .type-요청 { background: #E6F4EA; color: #137333; }
    .type-불만 { background: #FCE8E6; color: #C5221F; }
    .type-오류 { background: #FFF3E0; color: #E65100; }
    .type-건의 { background: #F3E8FD; color: #7627BB; }
    .type-기타 { background: #F0F0F0; color: #666; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>📋 VOC 대시보드</h1>
    <p>채널톡 엑셀 업로드 → Claude AI 심층 분석</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 인입 경로 매핑
# ─────────────────────────────────────────────
MEDIUM_MAP = {
    "native": "채널톡",
    "app": "카카오톡",
    "kakao": "카카오톡",
    "phone": "전화",
    "email": "이메일",
    "sms": "SMS",
}

MEDIUM_NAME_MAP = {
    "appKakao": "카카오톡",
    "appLine": "라인",
    "appInstagram": "인스타그램",
}


# ─────────────────────────────────────────────
# Claude AI 심층 분석
# ─────────────────────────────────────────────
ANALYSIS_PROMPT = """아래는 고객 상담 요약 내용이다. 다음 4가지를 분석해줘.

1. 음슴체 요약 (15자 이내, 예: "환불 처리 요청함", "코스 접근 권한 문의함")
2. 문의 유형 (문의/요청/불만/오류/건의/기타 중 택1)
3. 감정 (긍정/중립/부정 중 택1)
4. 핵심 키워드 (2-3개, 쉼표 구분)

반드시 아래 형식으로만 답해. 부가 설명 없이 딱 4줄만:
요약: ...
유형: ...
감정: ...
키워드: ...

상담 요약:
{text}"""


def analyze_with_claude(text, api_key, api_base, model):
    """Claude API로 상담 내용 심층 분석"""
    try:
        resp = requests.post(
            f"{api_base}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 100,
                "messages": [{"role": "user", "content": ANALYSIS_PROMPT.format(text=text[:2000])}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()["choices"][0]["message"]["content"].strip()

        # 결과 파싱
        parsed = {"요약": "", "유형": "기타", "감정": "중립", "키워드": ""}
        for line in result.split("\n"):
            line = line.strip()
            for key in parsed:
                if line.startswith(f"{key}:") or line.startswith(f"{key}："):
                    parsed[key] = line.split(":", 1)[-1].split("：", 1)[-1].strip()
                    break

        # 요약 정리
        summary = parsed["요약"].strip('"').strip("'").strip("-").strip("• ").strip()
        if not summary:
            summary = text.split("\n")[0][:15]

        # 유형 정리
        valid_types = ["문의", "요청", "불만", "오류", "건의", "기타"]
        doc_type = parsed["유형"]
        if doc_type not in valid_types:
            doc_type = "기타"

        # 감정 정리
        valid_sentiments = ["긍정", "중립", "부정"]
        sentiment = parsed["감정"]
        if sentiment not in valid_sentiments:
            sentiment = "중립"

        return {
            "ai_요약": summary[:20],
            "문의_유형": doc_type,
            "감정": sentiment,
            "키워드": parsed["키워드"],
        }
    except Exception as e:
        return {
            "ai_요약": f"분석 실패",
            "문의_유형": "기타",
            "감정": "중립",
            "키워드": "",
        }


# ─────────────────────────────────────────────
# 파일 파싱
# ─────────────────────────────────────────────
def parse_uploaded_file(uploaded_file):
    """업로드된 엑셀/CSV 파일을 파싱하여 정제된 DataFrame 반환"""
    if uploaded_file.name.endswith(".csv"):
        raw = pd.read_csv(uploaded_file)
    else:
        raw = pd.read_excel(uploaded_file)

    rows = []
    all_tags = set()

    for _, r in raw.iterrows():
        name = str(r.get("name", "알 수 없음")) if pd.notna(r.get("name")) else "알 수 없음"

        managed = r.get("managedAt", r.get("createdAt", ""))
        if pd.notna(managed):
            try:
                dt = pd.to_datetime(managed)
                time_str = dt.strftime("%y/%m/%d %H:%M")
            except Exception:
                time_str = str(managed)
        else:
            time_str = "-"

        summary = ""
        if pd.notna(r.get("summarizedMessage")):
            first_line = str(r["summarizedMessage"]).split("\n")[0].strip()
            summary = first_line[:50]
        else:
            summary = "(요약 없음)"

        medium_name = str(r.get("mediumName", "")) if pd.notna(r.get("mediumName")) else ""
        medium_type = str(r.get("mediumType", "")) if pd.notna(r.get("mediumType")) else ""
        if medium_name in MEDIUM_NAME_MAP:
            channel = MEDIUM_NAME_MAP[medium_name]
        else:
            channel = MEDIUM_MAP.get(medium_type, medium_type if medium_type else "기타")

        tags_raw = str(r.get("tags", "")) if pd.notna(r.get("tags")) else ""
        tag_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
        all_tags.update(tag_list)
        tags_str = ", ".join(tag_list) if tag_list else "-"

        cx = r.get("cxScore", None)
        cx_score = float(cx) if pd.notna(cx) else None

        state = str(r.get("state", "")) if pd.notna(r.get("state")) else ""
        state_map = {"closed": "종료", "opened": "진행 중", "snoozed": "보류", "initial": "초기"}
        state_kr = state_map.get(state, state)

        rows.append({
            "고객명": name,
            "인입 시간": time_str,
            "채널톡 요약": summary,
            "AI 요약": "",
            "문의 유형": "",
            "감정": "",
            "키워드": "",
            "인입 경로": channel,
            "태그": tags_str,
            "CX 점수": cx_score,
            "상태": state_kr,
            "_tags_list": tag_list,
            "_full_summary": str(r.get("summarizedMessage", "")) if pd.notna(r.get("summarizedMessage")) else "",
        })

    df = pd.DataFrame(rows)
    return df, list(all_tags)


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 파일 업로드")
    st.markdown("---")

    uploaded_file = st.file_uploader(
        "채널톡 내보내기 파일 (xlsx/csv)",
        type=["xlsx", "xls", "csv"],
        help="채널톡 → 상담 목록 → 내보내기 → 다운로드한 파일",
    )

    if uploaded_file:
        st.success(f"✅ {uploaded_file.name}")

        if "uploaded_name" not in st.session_state or st.session_state.uploaded_name != uploaded_file.name:
            df, all_tags = parse_uploaded_file(uploaded_file)
            st.session_state.df = df
            st.session_state.all_tags = all_tags
            st.session_state.uploaded_name = uploaded_file.name
            st.session_state.ai_analyzed = False

        st.markdown("---")
        st.markdown("**🏷️ 태그 필터**")
        if st.session_state.all_tags:
            tag_options = ["전체"] + sorted(st.session_state.all_tags)
            selected_tags = st.multiselect("태그 선택", options=tag_options, default=["전체"])
        else:
            selected_tags = ["전체"]

        st.markdown("---")
        st.markdown("**📊 CX 점수 필터**")
        cx_filter = st.select_slider(
            "최대 CX 점수",
            options=["전체", "1.0", "2.0", "3.0", "4.0", "5.0"],
            value="전체",
        )

        st.markdown("---")
        st.markdown("**🤖 Claude AI 설정**")
        st.caption("심층 분석에 필요 (선택사항)")

        # 환경변수 또는 Secrets에서 기본값 로드
        default_key = os.getenv("CLAUDE_API_KEY", "")
        default_base = os.getenv("CLAUDE_API_BASE", "https://aigw.grepp.co")
        default_model = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")

        if not default_key and hasattr(st, "secrets"):
            default_key = st.secrets.get("CLAUDE_API_KEY", "")
            default_base = st.secrets.get("CLAUDE_API_BASE", "https://aigw.grepp.co")
            default_model = st.secrets.get("CLAUDE_MODEL", "claude-haiku-4-5")

        claude_key = st.text_input("API Key", value=default_key, type="password")
        claude_base = st.text_input("API Base URL", value=default_base)
        claude_model = st.text_input("모델명", value=default_model)

        if claude_key:
            st.success("✅ Claude API 설정됨")
        else:
            st.info("💡 API 키 없이도 기본 분석은 가능합니다")

    else:
        selected_tags = ["전체"]
        cx_filter = "전체"
        claude_key = ""
        claude_base = ""
        claude_model = ""


# ─────────────────────────────────────────────
# 메인 영역
# ─────────────────────────────────────────────
if "df" in st.session_state and st.session_state.df is not None and len(st.session_state.df) > 0:
    df = st.session_state.df.copy()

    # 태그 필터 적용
    if "전체" not in selected_tags and selected_tags:
        mask = df["태그"].apply(lambda x: any(tag in x for tag in selected_tags))
        df = df[mask]

    # CX 점수 필터 적용
    if cx_filter != "전체":
        cx_val = float(cx_filter)
        df = df[df["CX 점수"].fillna(99) <= cx_val]

    # ─── 통계 카드 ───
    total = len(df)
    cx_scores = df["CX 점수"].dropna()
    avg_cx = cx_scores.mean() if len(cx_scores) > 0 else 0
    low_cx = (cx_scores <= 3.0).sum() if len(cx_scores) > 0 else 0
    tag_count = len(st.session_state.all_tags)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card"><div class="number">{total}</div><div class="label">전체 상담</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card"><div class="number">{avg_cx:.1f}</div><div class="label">평균 CX 점수</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-card"><div class="number">{low_cx}</div><div class="label">CX 3.0 이하 ⚠️</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-card"><div class="number">{tag_count}</div><div class="label">태그 종류</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── AI 심층 분석 버튼 ───
    if claude_key:
        ai_col1, ai_col2 = st.columns([3, 1])
        with ai_col1:
            analyze_btn = st.button(
                "🤖 Claude AI 심층 분석 실행",
                use_container_width=True,
                type="primary",
                help="각 상담을 Claude가 분석하여 음슴체 요약, 문의 유형, 감정, 키워드를 추출합니다",
            )
        with ai_col2:
            if st.session_state.get("ai_analyzed"):
                st.success("✅ 분석 완료")

        if analyze_btn:
            full_df = st.session_state.df
            progress = st.progress(0, text="Claude AI 심층 분석 중...")
            success_count = 0
            fail_count = 0

            for i in range(len(full_df)):
                progress.progress(
                    (i + 1) / len(full_df),
                    text=f"AI 분석 중... ({i+1}/{len(full_df)}) ✅{success_count} ❌{fail_count}"
                )

                full_summary = full_df.at[i, "_full_summary"]
                if not full_summary or full_summary == "(요약 없음)":
                    full_df.at[i, "AI 요약"] = "(원본 없음)"
                    full_df.at[i, "문의 유형"] = "기타"
                    full_df.at[i, "감정"] = "중립"
                    full_df.at[i, "키워드"] = ""
                    continue

                result = analyze_with_claude(full_summary, claude_key, claude_base, claude_model)

                if "분석 실패" in result["ai_요약"]:
                    fail_count += 1
                else:
                    success_count += 1

                full_df.at[i, "AI 요약"] = result["ai_요약"]
                full_df.at[i, "문의 유형"] = result["문의_유형"]
                full_df.at[i, "감정"] = result["감정"]
                full_df.at[i, "키워드"] = result["키워드"]

                time.sleep(0.5)

            progress.empty()
            st.session_state.df = full_df
            st.session_state.ai_analyzed = True
            st.success(f"✅ AI 심층 분석 완료! (성공: {success_count}건, 실패: {fail_count}건)")
            df = full_df.copy()
            # 필터 다시 적용
            if "전체" not in selected_tags and selected_tags:
                mask = df["태그"].apply(lambda x: any(tag in x for tag in selected_tags))
                df = df[mask]
            if cx_filter != "전체":
                cx_val = float(cx_filter)
                df = df[df["CX 점수"].fillna(99) <= cx_val]

    # ─── AI 분석 완료 여부에 따라 탭 구성 ───
    ai_done = st.session_state.get("ai_analyzed", False)

    if ai_done:
        tab_table, tab_ai, tab_issues, tab_cx = st.tabs(
            ["📋 상담 테이블", "🤖 AI 분석 결과", "🔥 이슈 모음", "📊 CX 분석"]
        )
    else:
        tab_table, tab_issues, tab_cx = st.tabs(
            ["📋 상담 테이블", "🔥 이슈 모음", "📊 CX 분석"]
        )

    # ── 탭: 상담 테이블 ──
    with tab_table:
        st.markdown(f"""
        <div style="margin-bottom: 0.5rem;">
            <span style="font-size: 1.1rem; font-weight: 600;">📋 상담 테이블</span>
            <span style="color: #888; font-size: 0.9rem; margin-left: 8px;">총 {len(df)}건</span>
        </div>
        """, unsafe_allow_html=True)

        if ai_done:
            display_cols = ["고객명", "인입 시간", "AI 요약", "문의 유형", "감정", "인입 경로", "태그", "CX 점수"]
            col_config = {
                "고객명": st.column_config.TextColumn("고객명", width="small"),
                "인입 시간": st.column_config.TextColumn("인입 시간", width="medium"),
                "AI 요약": st.column_config.TextColumn("AI 요약 🤖", width="large"),
                "문의 유형": st.column_config.TextColumn("유형", width="small"),
                "감정": st.column_config.TextColumn("감정", width="small"),
                "인입 경로": st.column_config.TextColumn("경로", width="small"),
                "태그": st.column_config.TextColumn("태그", width="medium"),
                "CX 점수": st.column_config.NumberColumn("CX", format="%.1f", width="small"),
            }
        else:
            display_cols = ["고객명", "인입 시간", "채널톡 요약", "인입 경로", "태그", "CX 점수", "상태"]
            col_config = {
                "고객명": st.column_config.TextColumn("고객명", width="small"),
                "인입 시간": st.column_config.TextColumn("인입 시간", width="medium"),
                "채널톡 요약": st.column_config.TextColumn("채널톡 요약", width="large"),
                "인입 경로": st.column_config.TextColumn("경로", width="small"),
                "태그": st.column_config.TextColumn("태그", width="medium"),
                "CX 점수": st.column_config.NumberColumn("CX", format="%.1f", width="small"),
                "상태": st.column_config.TextColumn("상태", width="small"),
            }

        display_df = df[display_cols].copy()
        st.dataframe(
            display_df,
            use_container_width=True,
            height=min(len(display_df) * 40 + 60, 600),
            column_config=col_config,
            hide_index=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        csv_data = display_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 분석 결과 CSV 다운로드",
            data=csv_data,
            file_name=f"VOC_분석결과_{datetime.date.today().strftime('%y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # ── 탭: AI 분석 결과 (AI 분석 후에만 표시) ──
    if ai_done:
        with tab_ai:
            st.markdown("""
            <div style="margin-bottom: 1rem;">
                <span style="font-size: 1.1rem; font-weight: 600;">🤖 AI 심층 분석 결과</span>
                <span style="color: #888; font-size: 0.9rem; margin-left: 8px;">Claude가 분석한 문의 유형 · 감정 · 키워드</span>
            </div>
            """, unsafe_allow_html=True)

            full_df = st.session_state.df

            # 문의 유형 분포
            col_type, col_sent = st.columns(2)

            with col_type:
                st.markdown("**📊 문의 유형 분포**")
                type_counts = full_df["문의 유형"].value_counts()
                type_chart = pd.DataFrame({"유형": type_counts.index, "건수": type_counts.values})
                st.bar_chart(type_chart, x="유형", y="건수")

            with col_sent:
                st.markdown("**😊 감정 분포**")
                sent_counts = full_df["감정"].value_counts()
                sent_chart = pd.DataFrame({"감정": sent_counts.index, "건수": sent_counts.values})
                st.bar_chart(sent_chart, x="감정", y="건수")

            st.markdown("---")

            # 키워드 빈도
            st.markdown("**🔑 핵심 키워드 TOP 15**")
            all_keywords = []
            for kw_str in full_df["키워드"].dropna():
                for kw in str(kw_str).split(","):
                    kw = kw.strip()
                    if kw and kw != "":
                        all_keywords.append(kw)

            if all_keywords:
                from collections import Counter
                kw_counts = Counter(all_keywords).most_common(15)
                kw_chart = pd.DataFrame(kw_counts, columns=["키워드", "건수"])
                st.bar_chart(kw_chart, x="키워드", y="건수")

            st.markdown("---")

            # 부정 감정 상담 목록
            st.markdown("**😡 부정 감정 상담**")
            neg_df = full_df[full_df["감정"] == "부정"]
            if len(neg_df) > 0:
                for _, row in neg_df.iterrows():
                    cx_str = f"CX {row['CX 점수']:.1f}" if pd.notna(row['CX 점수']) else ""
                    st.markdown(
                        f'<div class="cx-low">'
                        f'<strong>😡 {row["고객명"]}</strong> '
                        f'<span class="type-badge type-{row["문의 유형"]}">{row["문의 유형"]}</span> '
                        f'<span style="color: #888; font-size: 0.85rem;">| {row["인입 시간"]} | {row["인입 경로"]} {cx_str}</span>'
                        f'<br><span style="font-size: 0.95rem; font-weight: 500;">{row["AI 요약"]}</span>'
                        f'<br><span style="font-size: 0.8rem; color: #888;">키워드: {row["키워드"]} | 태그: {row["태그"]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.success("부정 감정 상담이 없습니다! 👍")

    # ── 탭: 이슈 모음 ──
    with tab_issues:
        st.markdown("""
        <div style="margin-bottom: 1rem;">
            <span style="font-size: 1.1rem; font-weight: 600;">🔥 이슈 모음</span>
            <span style="color: #888; font-size: 0.9rem; margin-left: 8px;">주의가 필요한 상담</span>
        </div>
        """, unsafe_allow_html=True)

        full_df = st.session_state.df

        # 이슈 카테고리 (AI 분석 완료 시 유형 기반도 추가)
        ISSUE_CATEGORIES = {}

        if ai_done:
            ISSUE_CATEGORIES["😡 부정 감정 (AI 분석)"] = {"type": "sentiment", "value": "부정"}
            ISSUE_CATEGORIES["🔴 불만 유형 (AI 분석)"] = {"type": "ai_type", "value": "불만"}
            ISSUE_CATEGORIES["🐛 오류 유형 (AI 분석)"] = {"type": "ai_type", "value": "오류"}

        ISSUE_CATEGORIES["😡 불만 태그"] = {"type": "tag", "keywords": ["불만"]}
        ISSUE_CATEGORIES["💡 개선 태그"] = {"type": "tag", "keywords": ["개선"]}
        ISSUE_CATEGORIES["🐛 오류 태그"] = {"type": "tag", "keywords": ["오류"]}
        ISSUE_CATEGORIES["⚠️ CX 점수 3.0 이하"] = {"type": "cx_low", "threshold": 3.0}

        issue_found = False

        for category_label, config in ISSUE_CATEGORIES.items():
            if config["type"] == "tag":
                category_mask = full_df["태그"].apply(
                    lambda x: any(kw in str(x) for kw in config["keywords"])
                )
            elif config["type"] == "cx_low":
                category_mask = full_df["CX 점수"].apply(
                    lambda x: x is not None and pd.notna(x) and float(x) <= config["threshold"]
                )
            elif config["type"] == "sentiment":
                category_mask = full_df["감정"] == config["value"]
            elif config["type"] == "ai_type":
                category_mask = full_df["문의 유형"] == config["value"]
            else:
                continue

            category_df = full_df[category_mask]
            count = len(category_df)

            if count > 0:
                issue_found = True

            with st.expander(f"{category_label}  ({count}건)", expanded=(count > 0)):
                if count == 0:
                    st.markdown(
                        "<div style='text-align: center; padding: 1rem; color: #aaa;'>해당 항목 없음</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    summary_col = "AI 요약" if ai_done else "채널톡 요약"
                    issue_cols = ["고객명", "인입 시간", summary_col, "인입 경로", "태그", "CX 점수"]
                    if ai_done:
                        issue_cols.insert(3, "문의 유형")
                        issue_cols.insert(4, "감정")

                    issue_display = category_df[issue_cols].copy()
                    st.dataframe(
                        issue_display,
                        use_container_width=True,
                        height=min(count * 40 + 60, 400),
                        hide_index=True,
                    )

        if not issue_found:
            st.info("이슈에 해당하는 상담이 없습니다.")

    # ── 탭: CX 분석 ──
    with tab_cx:
        st.markdown("""
        <div style="margin-bottom: 1rem;">
            <span style="font-size: 1.1rem; font-weight: 600;">📊 CX 만족도 분석</span>
        </div>
        """, unsafe_allow_html=True)

        cx_data = st.session_state.df[st.session_state.df["CX 점수"].notna()].copy()

        if len(cx_data) > 0:
            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("**점수 분포**")
                cx_bins = cx_data["CX 점수"].value_counts().sort_index()
                chart_data = pd.DataFrame({"CX 점수": cx_bins.index, "건수": cx_bins.values})
                st.bar_chart(chart_data, x="CX 점수", y="건수")

            with col_b:
                st.markdown("**구간별 현황**")
                ranges = [
                    ("⭐ 5.0 (최고)", cx_data["CX 점수"] == 5.0),
                    ("😊 4.0~4.9 (좋음)", (cx_data["CX 점수"] >= 4.0) & (cx_data["CX 점수"] < 5.0)),
                    ("😐 3.1~3.9 (보통)", (cx_data["CX 점수"] > 3.0) & (cx_data["CX 점수"] < 4.0)),
                    ("⚠️ 3.0 이하 (주의)", cx_data["CX 점수"] <= 3.0),
                ]
                for label, mask in ranges:
                    cnt = mask.sum()
                    pct = cnt / len(cx_data) * 100
                    st.markdown(f"**{label}**: {cnt}건 ({pct:.0f}%)")

            st.markdown("---")

            st.markdown("**⚠️ CX 점수 3.0 이하 상담 상세**")
            low_cx_df = cx_data[cx_data["CX 점수"] <= 3.0].sort_values("CX 점수")

            if len(low_cx_df) > 0:
                for _, row in low_cx_df.iterrows():
                    score = row["CX 점수"]
                    emoji = "🔴" if score <= 2.0 else "🟡"
                    summary = row["AI 요약"] if ai_done and row["AI 요약"] else row["채널톡 요약"]
                    st.markdown(
                        f'<div class="cx-low">'
                        f'<strong>{emoji} {row["고객명"]}</strong> '
                        f'<span style="color: #E63946; font-weight: 600;">CX {score:.1f}</span> '
                        f'<span style="color: #888; font-size: 0.85rem;">| {row["인입 시간"]} | {row["인입 경로"]}</span>'
                        f'<br><span style="font-size: 0.9rem;">{summary}</span>'
                        f'<br><span style="font-size: 0.8rem; color: #888;">태그: {row["태그"]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.success("CX 3.0 이하 상담이 없습니다! 👍")
        else:
            st.info("CX 점수 데이터가 없습니다.")

    # ─── 태그 분포 (하단) ───
    st.markdown("---")
    st.markdown("**🏷️ 태그 분포**")
    tag_all = []
    for tags_list in st.session_state.df["_tags_list"]:
        tag_all.extend(tags_list)
    if tag_all:
        from collections import Counter
        tag_counts = Counter(tag_all)
        tag_chart = pd.DataFrame(
            sorted(tag_counts.items(), key=lambda x: -x[1]),
            columns=["태그", "건수"]
        )
        st.bar_chart(tag_chart, x="태그", y="건수")

else:
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem; color: #888;">
        <div style="font-size: 3rem; margin-bottom: 1rem;">📂</div>
        <div style="font-size: 1.2rem; font-weight: 500; margin-bottom: 0.5rem;">
            좌측 사이드바에서 채널톡 엑셀 파일을 업로드해주세요
        </div>
        <div style="font-size: 0.9rem; margin-bottom: 1.5rem;">
            채널톡 → 상담 목록 → 내보내기 → 다운로드한 .xlsx 또는 .csv 파일
        </div>
        <div style="background: #f0f0f0; border-radius: 8px; padding: 1rem; display: inline-block; text-align: left;">
            <div style="font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem;">💡 사용 방법</div>
            <div style="font-size: 0.8rem; line-height: 1.8;">
                1. 채널톡에서 상담 목록 엑셀 내보내기<br>
                2. 좌측 사이드바에 파일 드래그 & 드롭<br>
                3. 자동으로 기본 분석 표시<br>
                4. (선택) Claude AI 키 입력 → 심층 분석 실행
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #aaa; font-size: 0.8rem;'>"
    "VOC 대시보드 v2.1 | 엑셀 업로드 + Claude AI | Powered by Streamlit"
    "</div>",
    unsafe_allow_html=True,
)
