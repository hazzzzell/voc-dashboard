"""
VOC 대시보드 v2.0 - 엑셀 업로드 방식
채널톡 내보내기 파일을 업로드하면 자동 분석
API 키 불필요!
"""

import datetime
import pandas as pd
import streamlit as st

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
    .cx-high {
        background: #F0FFF4; border: 1px solid #A2D2B4;
        border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.5rem;
    }
    .ai-tag {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 2px 8px; border-radius: 12px;
        font-size: 0.7rem; font-weight: 600; margin-left: 4px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>📋 VOC 대시보드</h1>
    <p>채널톡 엑셀 업로드 → 자동 분석 (API 키 불필요)</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 인입 경로 매핑
# ─────────────────────────────────────────────
MEDIUM_MAP = {
    "native": "채널톡",
    "app": "앱",
    "kakao": "카카오톡",
    "phone": "전화",
    "email": "이메일",
    "sms": "SMS",
}


def parse_uploaded_file(uploaded_file):
    """업로드된 엑셀/CSV 파일을 파싱하여 정제된 DataFrame 반환"""
    if uploaded_file.name.endswith(".csv"):
        raw = pd.read_csv(uploaded_file)
    else:
        raw = pd.read_excel(uploaded_file)

    rows = []
    all_tags = set()

    for _, r in raw.iterrows():
        # 고객명
        name = str(r.get("name", "알 수 없음")) if pd.notna(r.get("name")) else "알 수 없음"

        # 인입 시간
        managed = r.get("managedAt", r.get("createdAt", ""))
        if pd.notna(managed):
            try:
                dt = pd.to_datetime(managed)
                time_str = dt.strftime("%y/%m/%d %H:%M")
            except Exception:
                time_str = str(managed)
        else:
            time_str = "-"

        # AI 요약 (채널톡 자체 요약)
        summary = ""
        if pd.notna(r.get("summarizedMessage")):
            # 첫 줄만 가져오고 50자 제한
            first_line = str(r["summarizedMessage"]).split("\n")[0].strip()
            summary = first_line[:50]
        else:
            summary = "(요약 없음)"

        # 인입 경로
        medium = str(r.get("mediumType", "")) if pd.notna(r.get("mediumType")) else ""
        channel = MEDIUM_MAP.get(medium, medium if medium else "기타")

        # 태그
        tags_raw = str(r.get("tags", "")) if pd.notna(r.get("tags")) else ""
        tag_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
        all_tags.update(tag_list)
        tags_str = ", ".join(tag_list) if tag_list else "-"

        # CX 만족도
        cx = r.get("cxScore", None)
        cx_score = float(cx) if pd.notna(cx) else None

        # 상태
        state = str(r.get("state", "")) if pd.notna(r.get("state")) else ""
        state_map = {"closed": "종료", "opened": "진행 중", "snoozed": "보류", "initial": "초기"}
        state_kr = state_map.get(state, state)

        # 방향
        direction = str(r.get("direction", "")) if pd.notna(r.get("direction")) else ""

        rows.append({
            "고객명": name,
            "인입 시간": time_str,
            "핵심 요약": summary,
            "인입 경로": channel,
            "태그": tags_str,
            "CX 점수": cx_score,
            "상태": state_kr,
            "_datetime": pd.to_datetime(managed) if pd.notna(managed) else None,
            "_tags_list": tag_list,
            "_full_summary": str(r.get("summarizedMessage", "")) if pd.notna(r.get("summarizedMessage")) else "",
        })

    df = pd.DataFrame(rows)
    return df, list(all_tags)


# ─────────────────────────────────────────────
# 사이드바: 파일 업로드 & 필터
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 파일 업로드")
    st.markdown("---")

    uploaded_file = st.file_uploader(
        "채널톡 내보내기 파일 (xlsx/csv)",
        type=["xlsx", "xls", "csv"],
        help="채널톡 → 상담 목록 → 내보내기 → 다운로드한 파일을 여기에 올려주세요",
    )

    if uploaded_file:
        st.success(f"✅ {uploaded_file.name}")

        # 데이터 파싱 (캐싱)
        if "uploaded_name" not in st.session_state or st.session_state.uploaded_name != uploaded_file.name:
            df, all_tags = parse_uploaded_file(uploaded_file)
            st.session_state.df = df
            st.session_state.all_tags = all_tags
            st.session_state.uploaded_name = uploaded_file.name

        st.markdown("---")
        st.markdown("**🏷️ 태그 필터**")
        if st.session_state.all_tags:
            tag_options = ["전체"] + sorted(st.session_state.all_tags)
            selected_tags = st.multiselect(
                "태그 선택",
                options=tag_options,
                default=["전체"],
            )
        else:
            selected_tags = ["전체"]

        st.markdown("---")
        st.markdown("**📊 CX 점수 필터**")
        cx_filter = st.select_slider(
            "최대 CX 점수",
            options=["전체", "1.0", "2.0", "3.0", "4.0", "5.0"],
            value="전체",
        )
    else:
        selected_tags = ["전체"]
        cx_filter = "전체"


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

    # ─── 탭 구성 ───
    tab_table, tab_issues, tab_cx = st.tabs(["📋 상담 테이블", "🔥 이슈 모음", "📊 CX 분석"])

    # ── 탭 1: 상담 테이블 ──
    with tab_table:
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
            <div>
                <span style="font-size: 1.1rem; font-weight: 600;">📋 상담 테이블</span>
                <span style="color: #888; font-size: 0.9rem; margin-left: 8px;">총 {len(df)}건</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        display_df = df[["고객명", "인입 시간", "핵심 요약", "인입 경로", "태그", "CX 점수", "상태"]].copy()
        st.dataframe(
            display_df,
            use_container_width=True,
            height=min(len(display_df) * 40 + 60, 600),
            column_config={
                "고객명": st.column_config.TextColumn("고객명", width="small"),
                "인입 시간": st.column_config.TextColumn("인입 시간", width="medium"),
                "핵심 요약": st.column_config.TextColumn("핵심 요약", width="large"),
                "인입 경로": st.column_config.TextColumn("인입 경로", width="small"),
                "태그": st.column_config.TextColumn("🏷️ 태그", width="medium"),
                "CX 점수": st.column_config.NumberColumn("CX 점수", format="%.1f", width="small"),
                "상태": st.column_config.TextColumn("상태", width="small"),
            },
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

    # ── 탭 2: 이슈 모음 ──
    with tab_issues:
        st.markdown("""
        <div style="margin-bottom: 1rem;">
            <span style="font-size: 1.1rem; font-weight: 600;">🔥 이슈 모음</span>
            <span style="color: #888; font-size: 0.9rem; margin-left: 8px;">주의가 필요한 상담 모아보기</span>
        </div>
        """, unsafe_allow_html=True)

        full_df = st.session_state.df

        # 이슈 카테고리 정의
        ISSUE_CATEGORIES = {
            "😡 불만": {"type": "tag", "keywords": ["불만"]},
            "💡 개선": {"type": "tag", "keywords": ["개선"]},
            "🐛 오류": {"type": "tag", "keywords": ["오류"]},
            "⚠️ CX 점수 낮음 (3.0 이하)": {"type": "cx_low", "threshold": 3.0},
        }

        issue_found = False

        for category_label, config in ISSUE_CATEGORIES.items():
            if config["type"] == "tag":
                # 태그 기반 필터
                category_mask = full_df["태그"].apply(
                    lambda x: any(kw in str(x) for kw in config["keywords"])
                )
            elif config["type"] == "cx_low":
                # CX 점수 기반 필터
                category_mask = full_df["CX 점수"].apply(
                    lambda x: x is not None and pd.notna(x) and float(x) <= config["threshold"]
                )
            else:
                continue

            category_df = full_df[category_mask]
            count = len(category_df)

            if count > 0:
                issue_found = True

            with st.expander(f"{category_label}  ({count}건)", expanded=(count > 0)):
                if count == 0:
                    st.markdown(
                        "<div style='text-align: center; padding: 1rem; color: #aaa;'>"
                        "해당 항목이 없습니다."
                        "</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    issue_display = category_df[["고객명", "인입 시간", "핵심 요약", "인입 경로", "태그", "CX 점수"]].copy()
                    st.dataframe(
                        issue_display,
                        use_container_width=True,
                        height=min(count * 40 + 60, 400),
                        column_config={
                            "고객명": st.column_config.TextColumn("고객명", width="small"),
                            "인입 시간": st.column_config.TextColumn("인입 시간", width="medium"),
                            "핵심 요약": st.column_config.TextColumn("핵심 요약", width="large"),
                            "인입 경로": st.column_config.TextColumn("인입 경로", width="small"),
                            "태그": st.column_config.TextColumn("🏷️ 태그", width="medium"),
                            "CX 점수": st.column_config.NumberColumn("CX 점수", format="%.1f", width="small"),
                        },
                        hide_index=True,
                    )

        if not issue_found:
            st.info("이슈에 해당하는 상담이 없습니다.")

    # ── 탭 3: CX 분석 ──
    with tab_cx:
        st.markdown("""
        <div style="margin-bottom: 1rem;">
            <span style="font-size: 1.1rem; font-weight: 600;">📊 CX 만족도 분석</span>
        </div>
        """, unsafe_allow_html=True)

        cx_data = full_df[full_df["CX 점수"].notna()].copy()

        if len(cx_data) > 0:
            # CX 점수 분포
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
                    pct = cnt / len(cx_data) * 100 if len(cx_data) > 0 else 0
                    st.markdown(f"**{label}**: {cnt}건 ({pct:.0f}%)")

            st.markdown("---")

            # CX 점수 낮은 상담 상세
            st.markdown("**⚠️ CX 점수 3.0 이하 상담 상세**")
            low_cx_df = cx_data[cx_data["CX 점수"] <= 3.0].sort_values("CX 점수")

            if len(low_cx_df) > 0:
                for _, row in low_cx_df.iterrows():
                    score = row["CX 점수"]
                    emoji = "🔴" if score <= 2.0 else "🟡"
                    st.markdown(
                        f'<div class="cx-low">'
                        f'<strong>{emoji} {row["고객명"]}</strong> '
                        f'<span style="color: #E63946; font-weight: 600;">CX {score:.1f}</span> '
                        f'<span style="color: #888; font-size: 0.85rem;">| {row["인입 시간"]} | {row["인입 경로"]}</span>'
                        f'<br><span style="font-size: 0.9rem;">{row["핵심 요약"]}</span>'
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
    for tags_list in full_df["_tags_list"]:
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
                3. 자동으로 분석 결과 표시!
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #aaa; font-size: 0.8rem;'>"
    "VOC 대시보드 v2.0 | 엑셀 업로드 방식 | Powered by Streamlit"
    "</div>",
    unsafe_allow_html=True,
)
