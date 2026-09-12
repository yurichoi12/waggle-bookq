import json
import urllib.parse
import streamlit as st
import gspread
from google.oauth2.service_accountCredentials if False else None # syntax safety
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="와글 와글 독서모임 북큐 검색", page_icon="📚", layout="centered")

# 전체 UI 스타일링 및 불필요한 마진/패딩 압축
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
    
    /* 버튼 형태의 페이지 개수 선택기 스타일 */
    .per-page-container {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        justify-content: center;
        width: 100%;
    }
    .per-page-label {
        font-size: 11px;
        color: #888888;
        margin-bottom: 4px;
        text-align: right;
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
    if not raw_name:
        return "익명"
    name = raw_name.strip()
    for delimiter in ["-", ":", "_", " "]:
        if delimiter in name:
            name = name.split(delimiter)[0]
    return name.strip() if name.strip() else "익명"

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
    parsed_data.sort(key=lambda x: x.get("작성일시", ""), reverse=True)
    return parsed_data

st.title("📚 와글 와글 독서모임 #북큐")
st.caption("모임원들이 공유한 추천 도서와 메시지를 모아모아!")

try:
    items = load_data()
    
    # [1행] 검색창과 새로고침 버튼 나란히 배치 (비율을 안정적으로 고정)
    col_search, col_refresh = st.columns([4, 1])
    with col_search:
        search_query = st.text_input("🔍 #북큐 통합 검색", placeholder="책 제목, 작성자, 내용 입력 (예: 채채, 묘생묘세)", label_visibility="collapsed")
    with col_refresh:
        if st.button("🔄 새로고침", use_container_width=True):
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

    # 세션 상태 초기화
    if "items_per_page" not in st.session_state:
        st.session_state.items_per_page = 15
    if "page_num" not in st.session_state:
        st.session_state.page_num = 1

    st.write("")

    # [2행] 총 건수와 '한 페이지에 볼 목록 개수' 컨트롤을 완벽하게 수평 정렬
    col_count_text, col_per_page = st.columns([2, 3])
    
    with col_count_text:
        st.markdown(f"<div style='padding-top: 10px;'><b>총 {total_count}건의 #북큐 메시지</b></div>", unsafe_allow_html=True)
        
    with col_per_page:
        st.markdown("<div class='per-page-label'>한 페이지에 볼 목록 개수</div>", unsafe_allow_html=True)
        
        # 4개의 숫자를 나란히 배치하기 위한 컬럼 구조
        opt_cols = st.columns(4)
        page_options = [15, 20, 25, 30]
        
        for idx, opt in enumerate(page_options):
            with opt_cols[idx]:
                is_selected = (st.session_state.items_per_page == opt)
                if is_selected:
                    st.markdown(f"<div style='text-align: center; font-size: 14px; font-weight: bold; color: #8e44ad; padding: 4px 0;'>{opt}</div>", unsafe_allow_html=True)
                else:
                    # 빈 테두리/배경 없는 깔끔한 버튼 구현
                    if st.button(str(opt), key=f"per_page_{opt}", use_container_width=True):
                        st.session_state.items_per_page = opt
                        st.session_state.page_num = 1
                        st.rerun()

    items_per_page = st.session_state.items_per_page

    if search_query:
        encoded_query = urllib.parse.quote(search_query)
        yes24_url = f"https://www.yes24.com/Product/Search?domain=ALL&query={encoded_query}"
        st.markdown(
            f"""
            <div style="padding: 12px; background-color: #f8f0fc; border-radius: 8px; margin: 15px 0; font-size: 15px; border-left: 4px solid #8e44ad;">
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
        import math
        total_pages = math.ceil(total_count / items_per_page)
        
        if "prev_search" not in st.session_state:
            st.session_state.prev_search = search_query
        if st.session_state.prev_search != search_query:
            st.session_state.page_num = 1
            st.session_state.prev_search = search_query

        if st.session_state.page_num > total_pages:
            st.session_state.page_num = max(1, total_pages)

        current_page = st.session_state.page_num
        
        start_idx = (current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_items = filtered_items[start_idx:end_idx]

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

        if total_pages > 1:
            st.write("")
            max_visible_buttons = min(total_pages + 2, 12)
            cols = st.columns(max_visible_buttons)
            
            with cols[0]:
                if st.button("<", disabled=(current_page == 1), key="prev_page_btn"):
                    st.session_state.page_num -= 1
                    st.rerun()
            
            for p in range(1, total_pages + 1):
                if p < max_visible_buttons - 1:
                    with cols[p]:
                        if p == current_page:
                            st.markdown(f"<div style='display: inline-block; background-color: #e2e8f0; width: 28px; height: 28px; line-height: 28px; text-align: center; border-radius: 50%; font-weight: bold; color: #000000; margin: 0 auto;'>{p}</div>", unsafe_allow_html=True)
                        else:
                            if st.button(str(p), key=f"page_num_{p}"):
                                st.session_state.page_num = p
                                st.rerun()
            
            with cols[-1]:
                if st.button(">", disabled=(current_page == total_pages), key="next_page_btn"):
                    st.session_state.page_num = current_page + 1
                    st.rerun()

except Exception as e:
    st.error(f"구글 시트 데이터를 불러오는 중 오류가 발생했습니다: {e}")
