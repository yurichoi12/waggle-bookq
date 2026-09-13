import json
import html
import itertools
import urllib.parse
import concurrent.futures
import streamlit as st
import gspread
import requests
from google.oauth2.service_account import Credentials
from collections import defaultdict
import math
import re

st.set_page_config(page_title="와글 와글 독서모임 북큐 검색", page_icon="📚", layout="centered")

# 책 표지가 없을 때 사용할 기본 아이콘 (작은 책 모양 SVG)
PLACEHOLDER_COVER = "data:image/svg+xml;utf8," + urllib.parse.quote(
    """<svg xmlns='http://www.w3.org/2000/svg' width='60' height='84' viewBox='0 0 60 84'>
    <rect width='60' height='84' rx='4' fill='#f3e5f5'/>
    <rect x='6' y='10' width='48' height='6' rx='2' fill='#d5b8e0'/>
    <rect x='6' y='22' width='36' height='5' rx='2' fill='#e3cdec'/>
    <rect x='6' y='32' width='40' height='5' rx='2' fill='#e3cdec'/>
    <text x='30' y='66' font-size='22' text-anchor='middle'>📖</text>
    </svg>"""
)

COVER_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 전체 UI 스타일링 및 검색창/버튼/카드 레이아웃 스타일
st.markdown("""
    <style>
    div[data-testid="InputInstructions"], div[data-testid="stInputInstruction"] {
        display: none !important;
    }
    div.stTextInput > div > div {
        background-color: #f3e5f5 !important;
        border-radius: 12px !important;
        border: 2px solid #8e44ad !important;
        height: 50px !important;
    }
    div.stTextInput > div > div > input {
        height: 50px !important;
        font-size: 18px;
        background-color: transparent !important;
        color: #2c3e50 !important;
        border: none !important;
        padding-top: 0px !important;
        padding-bottom: 0px !important;
    }
    div.stTextInput > div > div > input:focus {
        box-shadow: none !important;
    }
    .stButton > button {
        height: 50px !important;
        border-radius: 12px !important;
        border: 2px solid #8e44ad !important;
        background-color: #ffffff !important;
        color: #8e44ad !important;
        font-weight: bold !important;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #f3e5f5 !important;
        border-color: #8e44ad !important;
        color: #8e44ad !important;
    }
    .stButton > button:disabled {
        opacity: 0.4 !important;
    }
    .page-option-link {
        color: #666666;
        text-decoration: none;
        font-size: 14px;
        margin-left: 10px;
        cursor: pointer;
    }
    .page-option-link:hover {
        color: #8e44ad;
        text-decoration: underline;
    }
    .page-option-selected {
        color: #8e44ad;
        font-weight: bold;
        font-size: 14px;
        margin-left: 10px;
    }

    /* ===== 페이지 이동 네비게이션 (모바일에서도 한 줄 유지) ===== */
    .page-nav-row {
        display: flex;
        flex-wrap: nowrap;
        align-items: center;
        justify-content: center;
        gap: 6px;
        width: 100%;
    }
    .page-nav-btn {
        flex: 0 0 auto;
        display: inline-block;
        padding: 6px 8px;
        border: 1.5px solid #8e44ad;
        border-radius: 8px;
        color: #8e44ad;
        font-size: 12px;
        font-weight: bold;
        text-decoration: none;
        text-align: center;
        white-space: nowrap;
        background-color: #ffffff;
    }
    .page-nav-btn:hover {
        background-color: #f3e5f5;
    }
    .page-nav-btn.page-nav-disabled {
        color: #cccccc;
        border-color: #e5e5e5;
        cursor: default;
        background-color: #fafafa;
    }
    .page-nav-info {
        flex: 0 0 auto;
        font-size: 13px;
        font-weight: bold;
        color: #2c3e50;
        white-space: nowrap;
        padding: 0 6px;
    }
    @media (max-width: 480px) {
        .page-nav-btn {
            padding: 6px 6px;
            font-size: 11px;
        }
        .page-nav-info {
            font-size: 12px;
            padding: 0 3px;
        }
    }

    /* ===== 북큐 카드 그리드 ===== */
    .book-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        margin: 10px 0 18px 0;
    }
    .book-card {
        background-color: #ffffff;
        border: 1px solid #ececec;
        border-radius: 10px;
        padding: 8px 8px 10px 8px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
    }
    .book-card .card-toggle {
        display: none;
    }
    .book-card .card-nickname {
        font-size: 11px;
        font-weight: bold;
        color: #8e44ad;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .book-card .card-title {
        font-size: 12.5px;
        font-weight: bold;
        color: #2c3e50;
        margin: 3px 0 6px 0;
        line-height: 1.3;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .book-card .card-cover {
        text-align: center;
        margin-bottom: 6px;
    }
    .book-card .card-cover img {
        width: 56px;
        height: 78px;
        object-fit: cover;
        border-radius: 4px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
    }
    .book-card .card-links {
        margin-bottom: 4px;
    }
    .book-card .card-links:empty {
        display: none;
    }
    .book-card a.book-link {
        display: inline-block;
        color: #8e44ad;
        text-decoration: underline;
        font-size: 11px;
    }
    .book-card .card-body-wrap {
        display: block;
        cursor: pointer;
    }
    .book-card .card-body-text {
        font-size: 11.5px;
        color: #555555;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        word-break: break-word;
        white-space: pre-wrap;
    }
    .book-card .more-toggle {
        display: block;
        text-align: center;
        font-size: 9.5px;
        color: #8e44ad;
        margin-top: 5px;
        opacity: 0.8;
    }
    .book-card .less-toggle {
        display: none;
        text-align: center;
        font-size: 9.5px;
        color: #8e44ad;
        margin-top: 8px;
        padding-top: 6px;
        border-top: 1px dashed #e2d3ec;
        cursor: pointer;
    }
    .book-card .card-toggle:checked ~ .card-body-wrap .card-body-text {
        -webkit-line-clamp: unset;
        display: block;
    }
    .book-card .card-toggle:checked ~ .card-body-wrap .more-toggle {
        display: none;
    }
    .book-card .card-toggle:checked ~ .less-toggle {
        display: block;
    }
    .book-card .card-date {
        font-size: 9.5px;
        color: #aaaaaa;
        margin-top: 5px;
    }
    .recommenders-box {
        background-color: #f8f0fc;
        padding: 12px 15px;
        border-radius: 8px;
        margin-bottom: 12px;
        border-left: 4px solid #8e44ad;
    }
    @media (max-width: 480px) {
        .book-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
        }
        .book-card .card-cover img {
            width: 50px;
            height: 70px;
        }
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

def parse_book_info(item):
    content = item.get("내용", "")
    if "]" in content:
        parts = content.split("]", 1)
        title_part = parts[0].strip() + "]"
        body_part = parts[1].strip()
    else:
        title_part = content[:25].strip() + "..." if len(content) > 25 else content
        body_part = content
    return title_part, body_part

def first_link(raw_link):
    if not raw_link:
        return ""
    for l in raw_link.split("\n"):
        l = l.strip()
        if l:
            return l
    return ""

@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_cover_image(link):
    """서점 링크 페이지의 og:image 메타태그에서 표지 이미지 URL을 가져옵니다."""
    if not link:
        return None
    try:
        resp = requests.get(link, headers=COVER_FETCH_HEADERS, timeout=4)
        if resp.status_code != 200:
            return None
        page_text = resp.text
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            page_text, re.IGNORECASE
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
                page_text, re.IGNORECASE
            )
        if match:
            return match.group(1)
    except Exception:
        return None
    return None

def preload_covers(items):
    """현재 페이지에 필요한 표지 이미지를 병렬로 미리 가져와 dict로 반환."""
    links = list({first_link(item.get("링크", "")) for item in items if first_link(item.get("링크", ""))})
    covers = {}
    if not links:
        return covers
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {executor.submit(fetch_cover_image, l): l for l in links}
        for future in concurrent.futures.as_completed(future_map):
            l = future_map[future]
            try:
                covers[l] = future.result()
            except Exception:
                covers[l] = None
    return covers

_card_id_counter = itertools.count()

def render_book_card(item, cover_url):
    card_id = f"card-toggle-{next(_card_id_counter)}"
    raw_sender = item.get("보낸사람", "익명")
    display_name = html.escape(clean_name(raw_sender))
    date_str = html.escape(item.get("작성일시", ""))
    title_p, body_part = parse_book_info(item)
    title_safe = html.escape(title_p)
    body_safe = html.escape(body_part)
    img_src = cover_url if cover_url else PLACEHOLDER_COVER

    link = item.get("링크", "")
    links_html = ""
    if link:
        for l in link.split("\n"):
            l = l.strip()
            if l:
                l_safe = html.escape(l, quote=True)
                links_html += (
                    f'<a href="{l_safe}" target="_blank" rel="noopener noreferrer" '
                    f'class="book-link" onclick="event.stopPropagation()">🔗 서점 링크 이동</a>'
                )

    # 주의: 마크다운 렌더러가 4칸 이상 들여쓰기된 줄을 "코드블록"으로 잘못 인식해
    # HTML이 깨지는 문제가 있어, 아래 HTML은 반드시 들여쓰기 없이 한 줄로 이어붙여야 합니다.
    return (
        '<div class="book-card">'
        f'<input type="checkbox" class="card-toggle" id="{card_id}">'
        f'<div class="card-nickname">👤 {display_name}</div>'
        f'<div class="card-title">{title_safe}</div>'
        f'<div class="card-cover"><img src="{img_src}" loading="lazy" alt="표지"/></div>'
        f'<div class="card-links">{links_html}</div>'
        f'<label for="{card_id}" class="card-body-wrap">'
        f'<div class="card-body-text">{body_safe}</div>'
        '<span class="more-toggle">▼ 더보기</span>'
        '</label>'
        f'<label for="{card_id}" class="less-toggle">▲ 접기</label>'
        f'<div class="card-date">{date_str}</div>'
        '</div>'
    )

def render_book_grid(items, covers):
    cards = "".join(render_book_card(item, covers.get(first_link(item.get("링크", "")))) for item in items)
    st.markdown(f'<div class="book-grid">{cards}</div>', unsafe_allow_html=True)

@st.cache_data(ttl=60)
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

st.title("📚 와글 북큐 검색기")
st.caption("모임원들이 공유한 추천 도서와 메시지를 모아모아!")

query_params = st.query_params
if "per_page" in query_params:
    try:
        val = int(query_params["per_page"])
        if val in [15, 18, 21, 24]:
            st.session_state.items_per_page = val
    except:
        pass
if "page" in query_params:
    try:
        pval = int(query_params["page"])
        if pval >= 1:
            st.session_state.page_num = pval
    except:
        pass

def clear_search():
    st.session_state.search_box = ""

try:
    items = load_data()

    search_query = st.text_input(
        "🔍 #북큐 통합 검색",
        placeholder="책 제목, 작성자, 내용 입력",
        label_visibility="collapsed",
        key="search_box"
    )

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

    if "items_per_page" not in st.session_state:
        st.session_state.items_per_page = 15
    if "page_num" not in st.session_state:
        st.session_state.page_num = 1

    st.write("")

    col_count_text, col_per_page = st.columns([2, 3])
    with col_count_text:
        st.markdown(f"<div style='padding-top: 12px;'><b>총 {total_count}건의 #북큐 메시지</b></div>", unsafe_allow_html=True)
    with col_per_page:
        current_per_page = st.session_state.items_per_page
        options_html = "<div style='text-align: right; padding-top: 4px;'><span style='font-size: 11px; color: #888888; margin-right: 4px;'>한 페이지에 표시할 카드 개수:</span>"
        for opt in [15, 18, 21, 24]:
            if current_per_page == opt:
                options_html += f"<span class='page-option-selected'>{opt}</span>"
            else:
                options_html += f"<a href='?per_page={opt}' target='_self' class='page-option-link'>{opt}</a>"
        options_html += "</div>"
        st.markdown(options_html, unsafe_allow_html=True)

    items_per_page = st.session_state.items_per_page

    if search_query and total_count == 0:
        encoded_query = urllib.parse.quote(search_query)
        yes24_url = f"https://www.yes24.com/Product/Search?domain=ALL&query={encoded_query}"
        st.markdown(
            '<div style="padding: 12px; background-color: #f8f0fc; border-radius: 8px; margin: 15px 0; font-size: 15px; border-left: 4px solid #8e44ad;">'
            '🔎 리스트에 없는 책입니다! '
            f'<a href="{yes24_url}" target="_blank" rel="noopener noreferrer" style="font-weight: bold; color: #8e44ad; text-decoration: underline;">'
            f"👉 YES24에서 '{search_query}' 검색하기"
            '</a>'
            '</div>',
            unsafe_allow_html=True
        )
        st.button("🏠 전체 목록으로 돌아가기", key="back_home_btn", on_click=clear_search)

    st.write("")

    if total_count > 0:
        if search_query:
            book_groups_dict = defaultdict(list)
            for item in filtered_items:
                title_p, _ = parse_book_info(item)
                book_groups_dict[title_p].append(item)

            book_groups = []
            for title_p, group_items in book_groups_dict.items():
                group_items_chrono = sorted(group_items, key=lambda x: x.get("작성일시", ""))
                latest_date_val = max(i.get("작성일시", "") for i in group_items)
                book_groups.append({
                    "title": title_p,
                    "items_chrono": group_items_chrono,
                    "latest_date": latest_date_val
                })
            book_groups.sort(key=lambda x: x["latest_date"], reverse=True)

            total_books = len(book_groups)
            total_pages = math.ceil(total_books / items_per_page)

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
            page_book_groups = book_groups[start_idx:end_idx]

            # 이 페이지에 필요한 표지 이미지를 한 번에 병렬로 준비
            page_items_flat = [item for group in page_book_groups for item in group["items_chrono"]]
            covers = preload_covers(page_items_flat)

            for group in page_book_groups:
                title_p = group["title"]
                items_chrono = group["items_chrono"]

                st.markdown(f"<h3 style='margin: 15px 0 10px 0; font-size: 1.25rem; color: #2c3e50;'>{html.escape(title_p)}</h3>", unsafe_allow_html=True)

                if len(items_chrono) >= 2:
                    recommenders_html = "<div class='recommenders-box'>"
                    recommenders_html += "<div style='font-weight: bold; margin-bottom: 6px; color: #8e44ad;'>📖 추천한 모임원</div>"
                    for idx, item in enumerate(items_chrono, 1):
                        raw_sender = item.get("보낸사람", "익명")
                        display_name = clean_name(raw_sender)
                        date_str = item.get("작성일시", "")
                        recommenders_html += f"<div style='margin-bottom: 3px;'>{idx}. <b>{html.escape(display_name)}</b> <span style='color: gray; font-size: 0.85em;'>({html.escape(date_str)})</span></div>"
                    recommenders_html += "</div>"
                    st.markdown(recommenders_html, unsafe_allow_html=True)

                render_book_grid(items_chrono, covers)
                st.markdown("---")

        else:
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

            covers = preload_covers(page_items)
            render_book_grid(page_items, covers)

        if total_pages > 1:
            st.write("")
            if current_page > 1:
                first_btn = '<a href="?page=1" target="_self" class="page-nav-btn">« 맨앞</a>'
                prev_btn = f'<a href="?page={current_page - 1}" target="_self" class="page-nav-btn">‹ 이전</a>'
            else:
                first_btn = '<span class="page-nav-btn page-nav-disabled">« 맨앞</span>'
                prev_btn = '<span class="page-nav-btn page-nav-disabled">‹ 이전</span>'
            if current_page < total_pages:
                next_btn = f'<a href="?page={current_page + 1}" target="_self" class="page-nav-btn">다음 ›</a>'
                last_btn = f'<a href="?page={total_pages}" target="_self" class="page-nav-btn">맨뒤 »</a>'
            else:
                next_btn = '<span class="page-nav-btn page-nav-disabled">다음 ›</span>'
                last_btn = '<span class="page-nav-btn page-nav-disabled">맨뒤 »</span>'
            page_info = f'<span class="page-nav-info">{current_page} / {total_pages}</span>'
            st.markdown(
                f'<div class="page-nav-row">{first_btn}{prev_btn}{page_info}{next_btn}{last_btn}</div>',
                unsafe_allow_html=True
            )

except Exception as e:
    st.error(f"구글 시트 데이터를 불러오는 중 오류가 발생했습니다: {e}")
