"""
VOC 대시보드 - 채널톡 상담 관리
비개발자를 위한 Streamlit 기반 대시보드
"""

import os
import time
import datetime
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# 환경변수 로드
# ─────────────────────────────────────────────
load_dotenv()

CHANNEL_ACCESS_KEY = os.getenv("CHANNEL_ACCESS_KEY", "")
CHANNEL_ACCESS_SECRET = os.getenv("CHANNEL_ACCESS_SECRET", "")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_API_BASE = os.getenv("CLAUDE_API_BASE", "https://api.anthropic.com")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

# AI 서비스 선택: Claude 우선 → Ollama → Gemini
def detect_ai_service():
    # 1순위: Claude API (빠르고 품질 좋음)
    if CLAUDE_API_KEY:
        return "claude"
    # 2순위: Ollama 로컬 (무료, 무제한)
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m.get("name", "") for m in r.json().get("models", [])]
            if models:
                return "ollama"
    except Exception:
        pass
    # 3순위: Gemini API
    if GEMINI_API_KEY:
        return "gemini"
    return None

AI_SERVICE = detect_ai_service()

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
    <p>채널톡 상담 데이터 조회 & AI 요약</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 채널톡 API 함수들
# ─────────────────────────────────────────────
CHANNEL_API_BASE = "https://api.channel.io/open/v5"

def get_channel_headers():
    return {
        "x-access-key": CHANNEL_ACCESS_KEY,
        "x-access-secret": CHANNEL_ACCESS_SECRET,
        "Content-Type": "application/json",
    }

def fetch_user_chats(state="closed", limit=50):
    all_chats = []
    url = f"{CHANNEL_API_BASE}/user-chats"
    params = {"state": state, "limit": limit, "sortOrder": "desc"}
    while True:
        try:
            resp = requests.get(url, headers=get_channel_headers(), params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            st.error(f"채널톡 API 호출 실패: {e}")
            break
        chats = data.get("userChats", [])
        all_chats.extend(chats)
        next_cursor = data.get("next")
        if not next_cursor or len(chats) == 0:
            break
        params["since"] = next_cursor
        time.sleep(0.3)
    return all_chats

def fetch_messages(user_chat_id, limit=50):
    url = f"{CHANNEL_API_BASE}/user-chats/{user_chat_id}/messages"
    params = {"limit": limit, "sortOrder": "asc"}
    try:
        resp = requests.get(url, headers=get_channel_headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("messages", [])
    except requests.exceptions.RequestException as e:
        st.warning(f"메시지 조회 실패 (chat: {user_chat_id}): {e}")
        return []

def get_user_info(user_id):
    url = f"{CHANNEL_API_BASE}/users/{user_id}"
    try:
        resp = requests.get(url, headers=get_channel_headers(), timeout=15)
        resp.raise_for_status()
        return resp.json().get("user", {})
    except Exception:
        return {}


# ─────────────────────────────────────────────
# AI 요약 함수
# ─────────────────────────────────────────────
SUMMARY_PROMPT = """아래는 고객 상담 대화임. 핵심만 음슴체로 15자 이내 초간결 요약해.

규칙:
- 반드시 15자 이내
- 음슴체 사용 (예: ~문의함, ~요청함, ~확인 요청함, ~안내받음)
- 부가 설명 없이 핵심 키워드 + 동사만
- 한 문장만 출력

좋은 예시:
- 코스 접근 권한 문의함
- 환불 처리 요청함
- 수강료 결제 오류 문의함
- USB 마이크 사용 가능 여부 문의함
- 수료증 발급 요청함

대화 내용:
{text}"""


def summarize_with_claude(conversation_text):
    """Claude API 요약 (회사 AI Gateway 또는 Anthropic 공식 API 모두 지원)"""
    try:
        # 회사 게이트웨이(aigw.grepp.co)는 OpenAI 호환 형식 사용
        if "anthropic.com" not in CLAUDE_API_BASE:
            # 회사 AI Gateway 방식 (OpenAI 호환)
            resp = requests.post(
                f"{CLAUDE_API_BASE}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {CLAUDE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 60,
                    "messages": [{
                        "role": "user",
                        "content": SUMMARY_PROMPT.format(text=conversation_text[:3000])
                    }]
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"].strip()
        else:
            # Anthropic 공식 API 방식
            resp = requests.post(
                f"{CLAUDE_API_BASE}/v1/messages",
                headers={
                    "x-api-key": CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 60,
                    "messages": [{
                        "role": "user",
                        "content": SUMMARY_PROMPT.format(text=conversation_text[:3000])
                    }]
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()["content"][0]["text"].strip()

        return result.split("\n")[0].strip().strip('"').strip("'").strip("-").strip("• ").strip()
    except Exception as e:
        return f"요약 실패: {e}"


def summarize_with_ollama(conversation_text):
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": SUMMARY_PROMPT.format(text=conversation_text[:3000]),
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 50}
            },
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json().get("response", "").strip()
        return result.split("\n")[0].strip().strip('"').strip("'").strip("-").strip("• ").strip()
    except Exception as e:
        return f"요약 실패: {e}"


def summarize_with_gemini(conversation_text):
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": SUMMARY_PROMPT.format(text=conversation_text[:3000])}]}]},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return result.split("\n")[0].strip().strip('"').strip("'").strip("-").strip("• ").strip()
    except Exception as e:
        return f"요약 실패: {e}"


def summarize_conversation(conversation_text):
    if AI_SERVICE == "claude":
        return summarize_with_claude(conversation_text)
    elif AI_SERVICE == "ollama":
        return summarize_with_ollama(conversation_text)
    elif AI_SERVICE == "gemini":
        return summarize_with_gemini(conversation_text)
    else:
        return "(AI가 연결되지 않음)"


def messages_to_text(messages):
    lines = []
    for msg in messages:
        person_type = msg.get("personType", "")
        role = "고객" if person_type == "user" else "매니저"
        text = msg.get("plainText", "")
        if text and text.strip():
            lines.append(f"[{role}] {text.strip()}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# 인입 경로 매핑
# ─────────────────────────────────────────────
CHANNEL_MAP = {
    "CHANNEL_TALK": "채널톡",
    "channel": "채널톡",
    "KAKAOTALK": "카카오톡",
    "kakao": "카카오톡",
    "PHONE": "전화",
    "phone": "전화",
    "MEET": "전화",
    "meet": "전화",
}

def get_channel_name(chat):
    medium = chat.get("contactMediumType", "")
    if isinstance(medium, str) and medium in CHANNEL_MAP:
        return CHANNEL_MAP[medium]
    source = chat.get("source", "")
    if isinstance(source, str) and source in CHANNEL_MAP:
        return CHANNEL_MAP[source]
    front_id = str(chat.get("frontMessageId", ""))
    if "kakao" in front_id.lower():
        return "카카오톡"
    if isinstance(medium, str) and medium:
        return medium
    return "채널톡"


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 조회 설정")
    st.markdown("---")
    st.markdown("**API 연결 상태**")

    if CHANNEL_ACCESS_KEY and CHANNEL_ACCESS_SECRET:
        st.success("✅ 채널톡 API 연결됨")
    else:
        st.error("❌ 채널톡 API 키 없음")

    if AI_SERVICE == "claude":
        st.success("✅ Claude AI 연결됨")
    elif AI_SERVICE == "ollama":
        st.success(f"✅ 로컬 AI 연결됨 ({OLLAMA_MODEL})")
        st.caption("💡 무료 · 무제한 · 내 PC에서 실행")
    elif AI_SERVICE == "gemini":
        st.success("✅ Gemini AI 연결됨")
    else:
        st.warning("⚠️ AI 없음")

    st.markdown("---")
    st.markdown("**📅 조회 기간**")
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("시작일", value=week_ago)
    with col_end:
        end_date = st.date_input("종료일", value=today)

    if start_date > end_date:
        st.error("시작일이 종료일보다 뒤에 있습니다!")

    st.markdown("---")
    chat_state = st.selectbox(
        "상담 상태",
        options=["closed", "opened", "snoozed"],
        format_func=lambda x: {"closed": "종료됨", "opened": "진행 중", "snoozed": "보류 중"}[x],
        index=0,
    )
    st.markdown("---")
    fetch_btn = st.button("🔍 데이터 조회하기", use_container_width=True, type="primary")


# ─────────────────────────────────────────────
# 메인: 데이터 조회
# ─────────────────────────────────────────────
if "df" not in st.session_state:
    st.session_state.df = None
if "raw_chats" not in st.session_state:
    st.session_state.raw_chats = []

if fetch_btn:
    if not CHANNEL_ACCESS_KEY or not CHANNEL_ACCESS_SECRET:
        st.error("⚠️ `.env` 파일에 채널톡 API 키를 먼저 입력해주세요!")
    else:
        with st.spinner("채널톡에서 데이터를 불러오는 중..."):
            chats = fetch_user_chats(state=chat_state)
            if not chats:
                st.warning("조회된 상담이 없습니다.")
            else:
                start_ts = int(datetime.datetime.combine(start_date, datetime.time.min).timestamp() * 1000)
                end_ts = int(datetime.datetime.combine(end_date, datetime.time.max).timestamp() * 1000)

                filtered = []
                for chat in chats:
                    created = chat.get("createdAt", 0)
                    if created < start_ts or created > end_ts:
                        continue
                    channel = get_channel_name(chat)
                    if channel not in ["채널톡", "카카오톡"]:
                        continue
                    filtered.append(chat)

                if not filtered:
                    st.warning("선택한 조건에 맞는 상담이 없습니다.")
                else:
                    rows = []
                    progress = st.progress(0, text="고객 정보 조회 중...")
                    for i, chat in enumerate(filtered):
                        progress.progress((i + 1) / len(filtered), text=f"상담 정보 조회 중... ({i+1}/{len(filtered)})")
                        user_id = chat.get("userId", "")
                        customer_name = chat.get("name", "")
                        if not customer_name and user_id:
                            user_info = get_user_info(user_id)
                            customer_name = (
                                user_info.get("profile", {}).get("name", "")
                                or user_info.get("name", "")
                                or "알 수 없음"
                            )
                        created_at = chat.get("createdAt", 0)
                        if created_at:
                            dt = datetime.datetime.fromtimestamp(created_at / 1000)
                            time_str = dt.strftime("%y/%m/%d %H:%M")
                        else:
                            time_str = "-"
                        rows.append({
                            "chat_id": chat.get("id", ""),
                            "고객명": customer_name or "알 수 없음",
                            "최근 인입 시간": time_str,
                            "핵심 요약": "",
                            "인입 경로": get_channel_name(chat),
                        })
                        time.sleep(0.1)
                    progress.empty()
                    df = pd.DataFrame(rows)
                    st.session_state.df = df
                    st.session_state.raw_chats = filtered
                    st.success(f"✅ 총 {len(df)}건의 상담을 불러왔습니다!")


# ─────────────────────────────────────────────
# 데이터 표시
# ─────────────────────────────────────────────
if st.session_state.df is not None and len(st.session_state.df) > 0:
    df = st.session_state.df

    col1, col2, col3 = st.columns(3)
    total = len(df)
    ch_count = len(df[df["인입 경로"] == "채널톡"])
    kakao_count = len(df[df["인입 경로"] == "카카오톡"])

    with col1:
        st.markdown(f'<div class="stat-card"><div class="number">{total}</div><div class="label">전체 상담</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card"><div class="number">{ch_count}</div><div class="label">채널톡</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-card"><div class="number">{kakao_count}</div><div class="label">카카오톡</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # AI 요약 버튼
    if AI_SERVICE:
        ai_labels = {"claude": "Claude", "ollama": f"로컬 AI ({OLLAMA_MODEL})", "gemini": "Gemini"}
        ai_label = ai_labels.get(AI_SERVICE, AI_SERVICE)

        summarize_btn = st.button(
            f"🤖 AI 요약 생성 ({ai_label})",
            use_container_width=True,
            help="각 상담의 대화 내용을 AI가 자동으로 요약합니다.",
        )
        if summarize_btn:
            chats = st.session_state.raw_chats
            progress = st.progress(0, text="AI 요약 생성 중...")
            success_count = 0
            fail_count = 0

            for i, chat in enumerate(chats):
                progress.progress(
                    (i + 1) / len(chats),
                    text=f"AI 요약 생성 중... ({i+1}/{len(chats)}) ✅{success_count} ❌{fail_count}"
                )
                chat_id = chat.get("id", "")
                messages = fetch_messages(chat_id)
                if messages:
                    conv_text = messages_to_text(messages)
                    if conv_text.strip():
                        summary = summarize_conversation(conv_text)
                        st.session_state.df.at[i, "핵심 요약"] = summary
                        if "요약 실패" in summary:
                            fail_count += 1
                        else:
                            success_count += 1
                    else:
                        st.session_state.df.at[i, "핵심 요약"] = "(대화 내용 없음)"
                else:
                    st.session_state.df.at[i, "핵심 요약"] = "(메시지 조회 실패)"

                # Claude: 1초 / Gemini: 5초 / Ollama: 대기 없음
                if AI_SERVICE == "gemini":
                    time.sleep(5)
                elif AI_SERVICE == "claude":
                    time.sleep(1)

            progress.empty()
            st.success(f"✅ AI 요약 완료! (성공: {success_count}건, 실패: {fail_count}건)")
            df = st.session_state.df

    # 테이블
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <div>
            <span style="font-size: 1.1rem; font-weight: 600;">📋 상담 테이블</span>
            <span style="color: #888; font-size: 0.9rem; margin-left: 8px;">총 {len(df)}건의 상담</span>
        </div>
        <div><span style="font-size: 0.8rem; color: #888;">핵심 요약 <span class="ai-tag">AI</span></span></div>
    </div>
    """, unsafe_allow_html=True)

    display_df = df[["고객명", "최근 인입 시간", "핵심 요약", "인입 경로"]].copy()
    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(len(display_df) * 40 + 60, 600),
        column_config={
            "고객명": st.column_config.TextColumn("고객명", width="small"),
            "최근 인입 시간": st.column_config.TextColumn("최근 인입 시간", width="medium"),
            "핵심 요약": st.column_config.TextColumn("핵심 요약 🤖", width="large"),
            "인입 경로": st.column_config.TextColumn("인입 경로", width="small"),
        },
        hide_index=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    csv_data = display_df.to_csv(index=False, encoding="utf-8-sig")
    date_label = f"{start_date.strftime('%y%m%d')}_{end_date.strftime('%y%m%d')}"
    st.download_button(
        label="📥 엑셀(CSV) 다운로드",
        data=csv_data,
        file_name=f"VOC_상담내역_{date_label}.csv",
        mime="text/csv",
        use_container_width=True,
    )

else:
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem; color: #888;">
        <div style="font-size: 3rem; margin-bottom: 1rem;">📋</div>
        <div style="font-size: 1.2rem; font-weight: 500; margin-bottom: 0.5rem;">
            좌측 사이드바에서 날짜를 선택하고<br>"데이터 조회하기" 버튼을 눌러주세요
        </div>
        <div style="font-size: 0.9rem;">채널톡 & 카카오톡 상담 내역을 조회합니다</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #aaa; font-size: 0.8rem;'>"
    "VOC 대시보드 v1.0 | Powered by Streamlit"
    "</div>",
    unsafe_allow_html=True,
)
