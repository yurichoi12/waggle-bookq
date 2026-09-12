import json
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="와글 와글 독서모임 북큐 검색", page_icon="📚", layout="wide")

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
    """닉네임에 -, : 등이 포함된 경우 그 앞부분만 깔끔하게 추출"""
    if not raw_name:
        return "익명"
    # '-' 또는 ':' 기준으로 나누고 가장 앞 단어를 가져옴
    name = raw_name.split("-")[0].split(":")[0].strip()
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
    return parsed_data

st.title("📚 와글 와글 독서모임 #북큐 검색")
st.caption("모임원들이 공유한 #북큐 추천 도서와 메시지를 한눈에 확인하세요!")

try:
    items = load_data()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("🔍 책 제목, 작성자, 내용 검색어 입력", placeholder="예: 채채, 스토아, 소설...")
    with col2:
        st.write("")
        st.write("")
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

    st.markdown(f"**총 {len(filtered_items)}건의 #북큐 메시지가 검색되었습니다.**")
    st.divider()

    for item in filtered_items:
        with st.container():
            col_a, col_b = st.columns([1, 4])
            with col_a:
                raw_sender = item.get("보낸사람", "익명")
                display_name = clean_name(raw_sender)
                st.markdown(f"**👤 {display_name}**")
                st.caption(f"📅 {item.get('작성일시', '')}")
            with col_b:
                content = item.get("내용", "")
                st.markdown(content)
                link = item.get("링크", "")
                if link:
                    for l in link.split("\n"):
                        l = l.strip()
                        if l:
                            st.markdown(f"🔗 [서점 링크 이동]({l})")
            st.divider()

except Exception as e:
    st.error(f"구글 시트 데이터를 불러오는 중 오류가 발생했습니다: {e}")
