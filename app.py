import json
import urllib.parse
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="와글 와글 독서모임 북큐 검색", page_icon="📚", layout="centered")

# 검색창 배경 연한 보라색 및 UI 스타일링
st.markdown("""
    <style>
    div.stTextInput > div > div {
        background-color: #f3e5f5 !important;
        border-radius: 12px !important;
        border: 2px solid #8e44ad !important;
    }
    div.stTextInput > div > div > input {
        height: 50px;
        font-size: 18px;
        background-color: transparent !important;
        color: #2c3e50 !important;
        border: none !important;
    }
    div.stTextInput > div > div > input:focus {
        box-shadow: none !important;
    }
    </style>
""", unsafe_allow_html=True)

def get_gspread_client():
    SCOPE = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if "gcp_service_account" in st.secrets:
        raw = st.secrets["gcp_service_account"]
        if isinstance(raw, str):
            creds_dict = json.loads(raw)
        else:
            creds_dict = dict(raw)
            if "private_key" in creds_dict and isinstance(creds_dict["private_key"], str):
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    elif "gcp_json_str" in st.secrets:
        raw = st.secrets["gcp_json_str"]
        if isinstance(raw, str):
            creds_dict = json.loads(raw)
        else:
            creds_dict = dict(raw)
    else:
        st.error("Secrets에서 인증 정보를 찾지 못했습니다.")
        st.stop()

    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    return gspread.authorize(creds)

def clean_name(raw_name):
    """-, :, _, 그리고 공백(띄어쓰기)을 기준으로 앞의 글자만 깔끔하게 추출"""
    if not raw_name:
        return "익명"
    
    name = raw_name.strip()
    for delimiter in ["-", ":", "_", " "]:
        if delimiter in name:
            name = name.split(delimiter)[0]
            
    name = name.strip()
    return name if name else "익명"

def load_data():
    client = get_gspread_client()
    SPREADSHEET_ID = "1wKZnnf1MuI2K0efAYZhUsq3938rjzLjOZhgnNvbz5-A"
    doc = client.open_by_key(SPREADSHEET_ID)
    sheet = doc.worksheets()[0]
    data = sheet.get_all_values()
    if not data:
        return []
    headers = data[0]
    rows = data[1:]
    parsed_data = []
    for row in rows:
        item = {}
        for i, h in enumerate(headers):
            item[h] = row[i] if i < len(row) else ""
        parsed_data.append(item)
    
    # 작성일시 기준 최신순 정렬 (역순)
    parsed_data.sort(key=lambda x: x.get("작성일시", ""), reverse=True)
    return parsed_data

st.title("📚 와글 와글 독서모임 #북큐")
st.caption("모임원들이 공유한 추천 도서와 메시지를 모아모아!")

try:
    items = load_data()
    
    # 상단 컨트롤 레이아웃: 검색창과 개수 설정 박스 배치
    col_search, col_per_page = st.columns([3, 1])
    with col_search:
        search_query = st.text_input("🔍 #북큐 통합 검색", placeholder="책 제목, 작성자, 내용 입력 (예: 채채, 묘생묘세)")
    with col_per_page:
        items_per_page = st.selectbox("표시 개수", [15, 20, 25, 30], index=0)

    if st.button("🔄 새로고침"):
        st.rerun()

    filtered_items = items
    if search_query:
        query = search_query.lower()
        filtered_items = [
            item for item in items
            if query in item.get("작성일시", "").lower()
            or query in clean_name(item.get("보낸사람", "")).lower()
            or query in item.get("내용", "").lower()
            or query in item.get("링크", "").lower()
        ]

    total_count = len(filtered_items)
    st.markdown(f"**총 {total_count}건의 #북큐 메시지**")

    if search_query:
        encoded_query = urllib.parse.quote(search_query)
        yes24_url = f"https://www.yes24.com/Product/Search?domain=ALL&query={encoded_query}"
        st.markdown(
            f"""
            <div style="padding: 12px; background-color: #f8f0fc; border-radius: 8px; margin-bottom: 15px; font-size: 15px; border-left: 4px solid #8e44ad;">
                🔎 원하시는 검색 결과가 없나요? 
                <a href="{yes24_url}" target="_blank" rel="noopener noreferrer" style="font-weight: bold; color: #8e44ad; text-decoration: underline;">
                    👉 YES24에서 '{search_query}' 검색하기
                </a>
            </div>
            """, 
            unsafe_allow_html=True
        )

    st.write("")

    if total_count > 0:
        # 페이지네이션 계산 로직
        import math
        total_pages = math.ceil(total_count / items_per_page)
        
        # 페이지 상태 유지
        if "page_num" not in st.session_state:
            st.session_state.page_num = 1
        
        # 검색어가 바뀌면 페이지를 1페이지로 초기화
        if "prev_search" not in st.session_state:
            st.session_state.prev_search = search_query
        if st.session_state.prev_search != search_query:
            st.session_state.page_num = 1
            st.session_state.prev_search = search_query

        # 페이지 범위 보정
        if st.session_state.page_num > total_pages:
            st.session_state.page_num = max(1, total_pages)

        current_page = st.session_state.page_num
        
        # 현재 페이지에 해당하는 아이템 슬라이싱
        start_idx = (current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_items = filtered_items[start_idx:end_idx]

        # 데이터 카드 출력
        for item in page_items:
            with st.container():
                raw_sender = item.get("보낸사람", "익명")
                display_name = clean_name(raw_sender)
                date_str = item.get("작성일시", "")
                
                st.markdown(f"👤 **{display_name}** &nbsp;·&nbsp; <span style='color: gray; font-size: 0.85em;'>{date_str}</span>", unsafe_allow_html=True)
                
                content = item.get("내용", "")
                if "]" in content:
                    parts = content.split("]", 1)
                    title_part = parts[0].strip() + "]"
                    body_part = parts[1].strip()
                    st.markdown(f"<h4 style='margin: 5px 0 10px 0; font-size: 1.15rem; color: #2c3e50;'>{title_part}</h4>", unsafe_allow_html=True)
                    st.markdown(body_part)
                else:
                    st.markdown(content)
                    
                link = item.get("링크", "")
                if link:
                    for l in link.split("\n"):
                        l = l.strip()
                        if l:
                            st.markdown(
                                f"""🔗 <a href="{l}" target="_blank" rel="noopener noreferrer" style="color: #8e44ad; text-decoration: underline;">서점 링크 이동</a>""",
                                unsafe_allow_html=True
                            )
                            
                st.markdown("---")

        # 하단 페이지네이션 UI
        if total_pages > 1:
            st.write("")
            cols = st.columns(min(total_pages + 2, 10)) # 최대 버튼 수 조절
            
            # 이전 페이지 버튼
            with cols[0]:
                if st.button("◀ 이전", disabled=(current_page == 1)):
                    st.session_state.page_num -= 1
                    st.rerun()
            
            # 페이지 번호 버튼들
            for p in range(1, total_pages + 1):
                if p < len(cols) - 1:
                    with cols[p]:
                        btn_label = f"[{p}]" if p == current_page else str(p)
                        if st.button(btn_label, key=f"page_btn_{p}"):
                            st.session_state.page_num = p
                            st.rerun()
            
            # 다음 페이지 버튼
            with cols[-1]:
                if st.button("다음 ▶", disabled=(current_page == total_pages)):
                    st.session_state.page_num += 1
                    st.rerun()

except Exception as e:
    st.error(f"구글 시트 데이터를 불러오는 중 오류가 발생했습니다: {e}")
