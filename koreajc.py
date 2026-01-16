from bs4 import BeautifulSoup
import html
import re
import requests
import json
from getpass import getpass


LOGIN_PAGE_URL = "https://koreajc.com/etc/sub_login.asp"
LOGIN_POST_URL = "https://koreajc.com/etc/login_ok.asp"
STUDY_ROOM_URL = "https://koreajc.com/study/studyroom.asp"


def extract_login_csrf(html_text: str) -> str | None:
    """
    var LOGIN_CSRF = '...'; 값 추출
    """
    pattern = r"var\s+LOGIN_CSRF\s*=\s*['\"]([^'\"]+)['\"]"
    match = re.search(pattern, html_text)
    return match.group(1) if match else None


def get_login_csrf(session: requests.Session) -> str:
    """
    로그인 페이지 접속 후 CSRF 토큰 획득
    """
    resp = session.get(LOGIN_PAGE_URL, timeout=10)
    resp.raise_for_status()

    csrf = extract_login_csrf(resp.text)
    if not csrf:
        raise RuntimeError("LOGIN_CSRF 토큰을 찾을 수 없습니다.")

    return csrf


def post_login(session: requests.Session, payload: dict) -> dict:
    """
    로그인 POST 공통 함수 (JSON 응답 반환)
    """
    headers = {
        "Referer": LOGIN_PAGE_URL,
        "X-Requested-With": "XMLHttpRequest",
    }

    resp = session.post(
        LOGIN_POST_URL,
        data=payload,
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()

    return resp.json()


def login(session: requests.Session, tid: str, tpwd: str) -> bool:
    csrf_token = get_login_csrf(session)

    payload = {
        "tid": tid,
        "tpwd": tpwd,
        "save_id": "",
        "captcha": "",
        "csrft": csrf_token,
        "ajax": "y",
    }

    # ---- 1차 로그인 시도 ----
    result = post_login(session, payload)
    code = result.get("code")
    okco = result.get("ok")

    # ---- CAPTCHA 요구 ----
    if code == "CAPTCHA_FAIL":
        print("CAPTCHA 로그인 필요")

        payload["captcha"] = result.get("captchaCode")

        # ---- CAPTCHA 포함 재시도 ----
        result = post_login(session, payload)
        code = result.get("code")
        okco = result.get("ok")

    # ---- 성공 여부 판단 ----
    return okco == True


def extract_csrf_token(html_text: str) -> str | None:
    """
    HTML/JS 텍스트에서 CSRF_TOKEN 값을 추출
    """
    pattern = r"var\s+CSRF_TOKEN\s*=\s*['\"]([^'\"]+)['\"]"
    match = re.search(pattern, html_text)
    return match.group(1) if match else None

def parse_course_cards(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    results = []

    for card in soup.select("div.course-card-item"):
        # ---- course title ----
        title_div = card.select_one("div.course-title")
        if not title_div:
            continue

        for span in title_div.select("span"):
            span.decompose()

        raw_title = title_div.get_text(strip=True)
        title = html.unescape(raw_title)

        # ---- auth token ----
        btn = card.select_one("button.btn-enter-room")
        auth_token = btn.get("data-auth-token") if btn else None

        # ---- progress ----
        progress = None
        progress_span = card.select_one(".progress-info span:last-child")
        if progress_span:
            progress_text = progress_span.get_text(strip=True)
            match = re.search(r"\d+", progress_text)
            if match:
                progress = int(match.group())

        results.append({
            "title": title,
            "auth_token": auth_token,
            "progress": progress
        })

    return results


def read_text_file(path: str) -> str:
    """HTML이 저장된 텍스트 파일을 읽어서 문자열로 반환"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def main():
    session = requests.Session()

    # ---- 사용자 입력 ----
    tid = input("아이디: ").strip()
    tpwd = getpass("비밀번호: ")

    # ---- 로그인 ----
    if not login(session, tid, tpwd):
        print("로그인 실패")
        return

    print("로그인 성공")

    # ---- 이후부터는 session 유지 ----
    # 예:
    # resp = session.get("https://koreajc.com/xxx")
    # html_text = resp.text
    # courses = parse_course_cards(html_text)
    resp = session.get("https://koreajc.com/study/studyroom.asp")
    html_text = resp.text
    csrf_token = extract_csrf_token(html_text)
    courses = parse_course_cards(html_text)

    print("CSRF TOKEN:", csrf_token)
    print("-" * 40)

    for course in courses:
        print(course)


def main_debug():
    file_path = "courses.html"

    html_text = read_text_file(file_path)

    csrf_token = extract_csrf_token(html_text)
    courses = parse_course_cards(html_text)

    print("CSRF TOKEN:", csrf_token)
    print("-" * 40)

    for course in courses:
        print(course)


if __name__ == "__main__":
    main()

