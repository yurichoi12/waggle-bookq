import json
import urllib.parse
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="와글 와글 독서모임 북큐 검색", page_icon="📚", layout="centered")

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
    
    search_query = st.text_input("🔍 검색어 입력 (책 제목, 작성자, 내용)", placeholder="예: 채채, 묘생묘세, 소설...")

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

    st.markdown(f"**총 {len(filtered_items)}건의 #북큐 메시지**")

    if search_query:
        encoded_query = urllib.parse.quote(search_query)
        yes24_url = f"https://www.yes24.com/Product/Search?domain=ALL&query={encoded_query}"
        # HTML <a> 태그를 직접 사용하여 target="_blank" 속성 부여 (카카오톡 인앱 브라우저 제어 우회)
        st.markdown(
            f"""
            <div style="padding: 10px; background-color: #f0f2f6; border-radius: 5px; margin-bottom: 15px;">
                🔎 원하시는 검색 결과가 없나요? 
                <a href="{yes24_url}" target="_blank" rel="noopener noreferrer" style="font-weight: bold; color: #ff4b4b; text-decoration: underline;">
                    👉 YES24에서 '{search_query}' 검색하기
                </a>
            </div>
            """, 
            unsafe_allow_html=True
        )

    st.write("")

    for item in filtered_items:
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
                st.markdown(f"### {title_part}")
                st.markdown(body_part)
            else:
                st.markdown(content)
                
            link = item.get("링크", "")
            if link:
                for l in link.split("\n"):
                    l = l.strip()
                    if l:
                        # 서점 링크도 HTML 태그로 안전하게 새 창 열기 적용
                        st.markdown(
                            f"""🔗 <a href="{l}" target="_blank" rel="noopener noreferrer" style="color: #1f77b4; text-decoration: underline;">서점 링크 이동</a>""",
                            unsafe_allow_html=True
                        )
                        
            st.markdown("---")

except Exception as e:
    st.error(f"구글 시트 데이터를 불러오는 중 오류가 발생했습니다: {e}")
