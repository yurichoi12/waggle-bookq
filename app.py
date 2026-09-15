import json
import html
import itertools
import urllib.parse
import concurrent.futures
import streamlit as st
import gspread
import requests
from google.oauth2.service_account import Credentials
import math
import re
from datetime import datetime, timezone, timedelta

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    # 일부 서점 사이트가 리퍼러 없는 요청(=봇으로 의심)을 차단하는 경우가 있어
    # 검색엔진에서 유입된 것처럼 보이도록 리퍼러를 함께 보냅니다.
    "Referer": "https://www.google.com/",
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
    .st-key-home_btn_wrap {
        display: flex;
        justify-content: flex-end;
        margin-top: 4px;
    }
    .st-key-home_btn_wrap .stButton > button {
        height: auto !important;
        min-height: unset !important;
        width: auto !important;
        padding: 3px 10px !important;
        font-size: 11px !important;
        border-width: 1px !important;
        border-radius: 6px !important;
    }
    /* ===== 같은 책 제목으로 여러 명이 올렸을 때의 그룹 표시 ===== */
    .title-group-block {
        margin-bottom: 4px;
    }
    .title-group-header {
        font-size: 15px;
        font-weight: bold;
        color: #2c3e50;
        margin: 18px 0 8px 0;
    }
    .recommenders-box {
        background-color: #f3e5f5;
        border-left: 4px solid #8e44ad;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 10px;
        font-size: 13px;
        color: #2c3e50;
    }
    .recommenders-box .recommenders-title {
        font-weight: bold;
        color: #8e44ad;
        margin-bottom: 4px;
        display: block;
    }
    .recommenders-box ol {
        margin: 0;
        padding-left: 18px;
    }
    .recommenders-box li {
        margin-bottom: 2px;
    }
    .recommenders-box .rec-date {
        color: #999999;
        font-size: 11px;
        margin-left: 4px;
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

def format_sheet_updated_time(iso_str):
    """구글 시트 파일의 마지막 수정 시각(Drive API의 modifiedTime, UTC)을
    한국 시간(KST) 기준 'yyyy.mm.dd. HH:MM' 형태로 변환합니다."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        kst = dt.astimezone(timezone(timedelta(hours=9)))
        return kst.strftime("%Y.%m.%d. %H:%M")
    except Exception:
        return ""

def parse_book_info(item):
    content = item.get("내용", "")

    # '#북큐' 태그가 있으면서, 태그 앞부분에 대괄호 제목이 없는 경우에만
    # (즉 "[제목] #북큐 내용"처럼 제목이 태그보다 앞에 오는 정상 형식이 아닌 경우)
    # 태그 앞에 적힌 개인적인 소감/코멘트는 버리고 태그 뒤의 실제 내용만 사용합니다.
    # (예: "넹그 작가 안읽어봤지만... #북큐 내용" -> "내용"만 사용)
    effective = content
    if "#북큐" in content:
        tag_idx = content.index("#북큐")
        before_tag = content[:tag_idx]
        after_tag = content[tag_idx + len("#북큐"):].strip()
        if "]" not in before_tag and after_tag:
            effective = after_tag

    if "]" in effective:
        parts = effective.split("]", 1)
        title_part = parts[0].strip() + "]"
        body_part = parts[1].strip()
        is_real_title = True
    else:
        # 대괄호 제목이 없는 메시지: 줄바꿈/중복 공백을 정리한 뒤
        # 앞부분을 임시 제목으로 사용합니다 (실제 책 제목이 아닐 수 있습니다).
        cleaned = " ".join(effective.split())
        if cleaned:
            title_part = cleaned[:25].strip() + "..." if len(cleaned) > 25 else cleaned
        else:
            title_part = "(제목 없음)"
        body_part = effective
        is_real_title = False
    return title_part, body_part, is_real_title

def first_link(raw_link):
    if not raw_link:
        return ""
    for l in raw_link.split("\n"):
        l = l.strip()
        if l:
            return l
    return ""

def yes24_direct_cover(link):
    """예스24는 스트림릿 클라우드 서버에서의 접속 자체가 막혀있어(og:image
    스크래핑 불가) 표지를 못 가져옵니다. 대신 예스24 이미지 CDN 주소가
    'https://image.yes24.com/goods/{상품ID}/xl' 형태로 예측 가능하다는 점을
    이용해, 링크 속 상품ID로 이미지 주소를 직접 만들어 사용합니다.
    이 경우 이미지 요청은 서버가 아니라 각 방문자의 브라우저가 직접 보내므로
    서버-예스24 간 연결 차단과 무관하게 정상적으로 표지가 보입니다."""
    if not link or "yes24.com" not in link.lower():
        return None
    matches = re.findall(r"\d{6,}", link)
    if not matches:
        return None
    product_id = max(matches, key=len)
    return f"https://image.yes24.com/goods/{product_id}/xl"

def _extract_og_image(page_text):
    match = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
        page_text, re.IGNORECASE
    )
    if not match:
        match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
            page_text, re.IGNORECASE
        )
    return match.group(1) if match else None

@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_cover_image(link):
    """서점 링크 페이지의 og:image 메타태그에서 표지 이미지 URL을 가져옵니다.
    스트림릿 클라우드 서버에서 직접 접속이 막힌 사이트는 공개 프록시를 통해
    한 번 더 시도합니다."""
    if not link:
        return None
    try:
        with requests.Session() as session:
            resp = session.get(link, headers=COVER_FETCH_HEADERS, timeout=6, allow_redirects=True)
        if resp.status_code == 200:
            image = _extract_og_image(resp.text)
            if image:
                return image
    except Exception:
        pass

    proxy_urls = [
        "https://api.allorigins.win/raw?url=" + urllib.parse.quote(link, safe=""),
        "https://api.codetabs.com/v1/proxy?quest=" + urllib.parse.quote(link, safe=""),
    ]
    for proxy_url in proxy_urls:
        try:
            with requests.Session() as session:
                resp = session.get(proxy_url, headers=COVER_FETCH_HEADERS, timeout=8)
            if resp.status_code == 200:
                image = _extract_og_image(resp.text)
                if image:
                    return image
        except Exception:
            continue
    return None

def _extract_og_title(page_text):
    match = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']',
        page_text, re.IGNORECASE
    )
    if not match:
        match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:title["\']',
            page_text, re.IGNORECASE
        )
    if match:
        title = html.unescape(match.group(1)).strip()
        return title if title else None
    return None

@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_link_title(link):
    """서점 링크 페이지의 og:title(실제 책 제목)을 가져옵니다.
    메시지에 '[책 제목]' 형식이 없는 경우, 카톡에서 보이던 링크 미리보기처럼
    링크 자체에서 실제 제목을 가져오기 위해 사용합니다.
    (스트림릿 클라우드 서버에서 접속 자체가 막힌 사이트, 예: 예스24는 여기서 실패하며,
    그 경우 render_book_card에서 방문자의 브라우저가 직접 가져오도록 처리합니다.)"""
    if not link:
        return None
    try:
        with requests.Session() as session:
            resp = session.get(link, headers=COVER_FETCH_HEADERS, timeout=6, allow_redirects=True)
        if resp.status_code == 200:
            title = _extract_og_title(resp.text)
            if title:
                return title
    except Exception:
        pass
    return None

def preload_titles(items):
    """대괄호 제목이 없는 메시지 중 링크가 있는 항목만, 링크의 실제 책 제목을
    병렬로 미리 가져와 dict로 반환합니다."""
    links = list({
        first_link(item.get("링크", ""))
        for item in items
        if first_link(item.get("링크", "")) and not parse_book_info(item)[2]
    })
    titles = {}
    if not links:
        return titles
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {executor.submit(fetch_link_title, l): l for l in links}
        for future in concurrent.futures.as_completed(future_map):
            l = future_map[future]
            try:
                titles[l] = future.result()
            except Exception:
                titles[l] = None
    return titles

def preload_covers(items):
    """현재 페이지에 필요한 표지 이미지를 병렬로 미리 가져와 dict로 반환."""
    links = list({first_link(item.get("링크", "")) for item in items if first_link(item.get("링크", ""))})
    covers = {}
    if not links:
        return covers

    # 예스24 링크는 서버에서 스크래핑을 시도하지 않고(=접속 자체가 막혀있어
    # 어차피 실패), 이미지 CDN 주소를 바로 구성해서 사용합니다.
    links_to_fetch = []
    for l in links:
        direct = yes24_direct_cover(l)
        if direct:
            covers[l] = direct
        else:
            links_to_fetch.append(l)

    if links_to_fetch:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_map = {executor.submit(fetch_cover_image, l): l for l in links_to_fetch}
            for future in concurrent.futures.as_completed(future_map):
                l = future_map[future]
                try:
                    covers[l] = future.result()
                except Exception:
                    covers[l] = None
    return covers

_card_id_counter = itertools.count()

def build_client_title_fetch_html(title_id, link):
    """예스24처럼 스트림릿 클라우드 서버 접속 자체가 막힌 사이트는 서버가 og:title을
    못 가져오므로, 방문자의 브라우저가 CORS 프록시(allorigins.win)를 통해 직접
    가져오게 합니다. 표지 이미지 때와 같은 이유로 서버 차단과 무관하게 동작합니다.
    st.markdown은 <script> 태그를 실행하지 않기 때문에, 존재하지 않는 이미지 주소를
    넣어 반드시 실패하는 숨겨진 <img>의 onerror 이벤트를 스크립트 실행 트리거로
    이용하는 흔한 우회 방법을 사용합니다."""
    fetch_call = (
        "fetch('https://api.allorigins.win/get?url=' + encodeURIComponent(" + json.dumps(link) + "))"
    )
    js_code = (
        "this.remove();"
        + fetch_call +
        ".then(function(r){return r.json();})"
        ".then(function(d){"
        "var t=d&&d.contents;if(!t)return;"
        "var m=t.match(/<meta[^>]+property=['\"]og:title['\"][^>]*content=['\"]([^'\"]+)['\"]/i);"
        "if(!m){m=t.match(/<meta[^>]+content=['\"]([^'\"]+)['\"][^>]*property=['\"]og:title['\"]/i);}"
        "if(m&&m[1]){"
        "var el=document.getElementById(" + json.dumps(title_id) + ");"
        "if(el){var ta=document.createElement('textarea');ta.innerHTML=m[1];el.textContent=ta.value;}"
        "}"
        "}).catch(function(){});"
    )
    js_safe = html.escape(js_code, quote=True)
    return f'<img src="data:," alt="" style="display:none;width:0;height:0;" onerror="{js_safe}">'

def render_book_card(item, cover_url, preview_title=None):
    card_id = f"card-toggle-{next(_card_id_counter)}"
    title_id = f"card-title-{card_id}"
    raw_sender = item.get("보낸사람", "익명")
    display_name = html.escape(clean_name(raw_sender))
    date_str = html.escape(item.get("작성일시", ""))
    title_p, body_part, is_real_title = parse_book_info(item)
    client_fetch_html = ""
    if not is_real_title and preview_title:
        # 메시지 자체에 '[책 제목]' 형식이 없으면, 링크 미리보기에서 가져온
        # 실제 책 제목으로 대체합니다 (카톡에서 보이던 링크 미리보기와 동일한 역할).
        title_p = preview_title
    elif not is_real_title and not preview_title:
        # 서버에서 직접 접속이 막힌 사이트(예: 예스24)는 서버가 제목을 못 가져오므로,
        # 대신 카드가 화면에 뜬 뒤 방문자의 브라우저가 직접(CORS 프록시 경유) og:title을
        # 가져와 채워넣도록 합니다. st.markdown은 <script> 태그를 실행하지 않기 때문에,
        # 숨겨진 <img>의 onerror 이벤트를 스크립트 실행 트리거로 이용합니다.
        link_for_fetch = first_link(item.get("링크", ""))
        if link_for_fetch:
            client_fetch_html = build_client_title_fetch_html(title_id, link_for_fetch)
    title_safe = html.escape(title_p)
    body_safe = html.escape(body_part)
    img_src = cover_url if cover_url else PLACEHOLDER_COVER
    placeholder_safe = html.escape(PLACEHOLDER_COVER, quote=True)

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
        f'<div class="card-title" id="{title_id}">{title_safe}</div>'
        f'{client_fetch_html}'
        f'<div class="card-cover"><img src="{img_src}" loading="lazy" alt="표지" '
        f'onerror="this.onerror=null;this.src=&quot;{placeholder_safe}&quot;;"/></div>'
        f'<div class="card-links">{links_html}</div>'
        f'<label for="{card_id}" class="card-body-wrap">'
        f'<div class="card-body-text">{body_safe}</div>'
        '<span class="more-toggle">▼ 더보기</span>'
        '</label>'
        f'<label for="{card_id}" class="less-toggle">▲ 접기</label>'
        f'<div class="card-date">{date_str}</div>'
        '</div>'
    )

def render_book_grid(items, covers, titles=None):
    titles = titles or {}
    cards = "".join(
        render_book_card(
            item,
            covers.get(first_link(item.get("링크", ""))),
            titles.get(first_link(item.get("링크", "")))
        )
        for item in items
    )
    st.markdown(f'<div class="book-grid">{cards}</div>', unsafe_allow_html=True)

def render_title_group(title, group_items, covers):
    """제목이 대괄호로 정확히 일치하는 항목이 2건 이상일 때, 헤더 + 추천한 모임원
    박스를 보여준 뒤 해당 항목들을 카드 그리드로 표시합니다."""
    group_items_sorted = sorted(group_items, key=lambda x: x.get("작성일시", ""))
    rec_rows = ""
    for item in group_items_sorted:
        name_safe = html.escape(clean_name(item.get("보낸사람", "익명")))
        date_safe = html.escape(item.get("작성일시", ""))
        rec_rows += f'<li><b>{name_safe}</b><span class="rec-date">({date_safe})</span></li>'
    title_safe = html.escape(title)
    header_html = (
        '<div class="title-group-block">'
        f'<div class="title-group-header">📚 {title_safe}</div>'
        '<div class="recommenders-box">'
        '<span class="recommenders-title">🗒️ 추천한 모임원</span>'
        f'<ol>{rec_rows}</ol>'
        '</div>'
        '</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)
    render_book_grid(group_items_sorted, covers)

@st.cache_data(ttl=60)
def load_data():
    client = get_gspread_client()
    SPREADSHEET_ID = "1wKZnnf1MuI2K0efAYZhUsq3938rjzLjOZhgnNvbz5-A"
    doc = client.open_by_key(SPREADSHEET_ID)
    sheet = doc.worksheets()[0]
    data = sheet.get_all_values()

    # 구글 시트 "파일" 자체의 마지막 수정 시각(Drive API modifiedTime)을 함께 가져옵니다.
    # 이는 메시지 내용의 작성일시가 아니라, 시트가 실제로 마지막으로 갱신 처리된 시각입니다.
    sheet_updated_raw = ""
    try:
        drive_resp = client.http_client.session.get(
            f"https://www.googleapis.com/drive/v3/files/{SPREADSHEET_ID}",
            params={"fields": "modifiedTime"},
            timeout=5,
        )
        if drive_resp.status_code == 200:
            sheet_updated_raw = drive_resp.json().get("modifiedTime", "")
    except Exception:
        sheet_updated_raw = ""

    if not data:
        return [], sheet_updated_raw
    headers = data[0]
    rows = data[1:]
    parsed_data = []
    for row in rows:
        item = {}
        for i, h in enumerate(headers):
            item[h] = row[i] if i < len(row) else ""
        parsed_data.append(item)
    parsed_data.sort(key=lambda x: x.get("작성일시", ""), reverse=True)
    return parsed_data, sheet_updated_raw

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
    items, sheet_updated_raw = load_data()

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

    latest_update_str = format_sheet_updated_time(sheet_updated_raw)

    col_count_text, col_per_page = st.columns([2, 3])
    with col_count_text:
        count_html = f"<div style='padding-top: 12px;'><b>총 {total_count}건의 #북큐 메시지</b>"
        if latest_update_str:
            count_html += f'<div style="font-size: 11px; color: #999999; margin-top: 2px;">최근 업데이트: {html.escape(latest_update_str)}</div>'
        count_html += "</div>"
        st.markdown(count_html, unsafe_allow_html=True)
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
        if search_query:
            with st.container(key="home_btn_wrap"):
                st.button("🏠 전체 목록으로", key="back_home_btn", on_click=clear_search)

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

    st.write("")

    if total_count > 0:
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
        titles = preload_titles(page_items)

        # 검색 중일 때, 대괄호로 표시된 정식 책 제목이 완전히 똑같은 항목이
        # 2건 이상이면 "추천한 모임원" 그룹으로 묶어서 보여줍니다.
        # (제목이 없어 앞 25자로 대체 표시되는 항목은 절대 서로 그룹으로 묶지 않습니다 -
        #  서로 다른 사람의 무관한 메시지가 우연히 같은 제목으로 섞여 보이는 오류를 방지하기 위함)
        title_counts = {}
        if search_query:
            for item in page_items:
                title_p, _, is_real = parse_book_info(item)
                if is_real:
                    title_counts[title_p] = title_counts.get(title_p, 0) + 1
        grouped_titles = {k for k, v in title_counts.items() if v >= 2}

        if grouped_titles:
            buffer = []
            rendered_groups = set()

            def flush_buffer():
                if buffer:
                    render_book_grid(buffer, covers, titles)
                    buffer.clear()

            group_items_map = {}
            for item in page_items:
                title_p, _, is_real = parse_book_info(item)
                if is_real and title_p in grouped_titles:
                    group_items_map.setdefault(title_p, []).append(item)

            for item in page_items:
                title_p, _, is_real = parse_book_info(item)
                if is_real and title_p in grouped_titles:
                    if title_p in rendered_groups:
                        continue
                    rendered_groups.add(title_p)
                    flush_buffer()
                    render_title_group(title_p, group_items_map[title_p], covers)
                else:
                    buffer.append(item)
            flush_buffer()
        else:
            render_book_grid(page_items, covers, titles)

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
