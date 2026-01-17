from bs4 import BeautifulSoup
import html
import re
import requests
import json
import time
import uuid
import signal
import os
import sys
import subprocess
from getpass import getpass
from concurrent.futures import ThreadPoolExecutor, as_completed


LOGIN_PAGE_URL = "https://koreajc.com/etc/sub_login.asp"
LOGIN_POST_URL = "https://koreajc.com/etc/login_ok.asp"
NEW_STUDY_URL = "https://koreajc.com/study/new_study.asp"
UPDATE_URL = "https://koreajc.com/study/api/update_progress.asp"


def force_exit(sig, frame):
    print("Ctrl+C 가 감지되어 강제로 종료합니다.")
    os._exit(1)


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


def is_blocked_studyroom(html: str) -> bool:
    """
    본인인증 미완료 등으로 차단된 경우 감지
    """
    if "본인인증 후 학습진행이 가능합니다" in html:
        return True
    return False


def fetch_studyroom_html(
    session: requests.Session,
    auth_token: str,
    csrf_token: str,
) -> str:
    payload = {
        "auth_token": auth_token,
        "csrf_token": csrf_token,
    }

    resp = session.post(NEW_STUDY_URL, data=payload, timeout=10)
    resp.raise_for_status()

    html = resp.text

    # ---- 차단 응답 무시 ----
    if is_blocked_studyroom(html):
        print("❗ 본인인증 미완료로 수강 페이지가 차단되었습니다. (무시)")
        return None

    return html


def extract_server_data(html: str) -> dict:
    match = re.search(
        r'window\.SERVER_DATA\s*=\s*\{.*?\};',
        html,
        re.DOTALL
    )

    if not match:
        raise ValueError("window.SERVER_DATA를 찾을 수 없습니다.")

    js_code = match.group(0)

    json_text = subprocess.check_output(
        ["node"],
        input=f"global.window={{}};\n{js_code}\nconsole.log(JSON.stringify(window.SERVER_DATA));",
        text=True
    )
    return json.loads(json_text)


def analyze_curriculum_last_page(curriculum: list[dict]) -> list[dict]:
    """
    챕터별 마지막 페이지 1개만 추출
    """
    chapter_map = {}
    curriculum_list = curriculum.get("curriculum")

    for item in curriculum_list:
        chapter = item.get("chapter")
        page = item.get("page", 0)
    
        if chapter is None:
            continue

        # 처음 나오거나, page가 더 큰 경우만 갱신
        if chapter not in chapter_map or page > chapter_map[chapter]["page"]:
            total_time = item.get("totalTime", 0)
            study_seconds = item.get("chapterStudySeconds", 0)

            chapter_map[chapter] = {
                "chapter": chapter,
                "page": page,
                "chapterRate": item.get("chapterRate", 0),
                "totalTime": total_time,
                "chapterStudySeconds": study_seconds,
                "studyTimeExceeded": study_seconds >= total_time,
            }

    # chapter 번호 순서대로 정렬해서 리스트로 반환
    return sorted(chapter_map.values(), key=lambda x: x["chapter"])


def build_update_payload(
    lecturenum: str,
    lecturecode: str,
    chapter: int,
    page: int,
    csrf_token: str,
    auth_token: str,
    log_id: int,
    instance_id: str,
    totalTime: str,
    studyTime: str,
) -> dict:
    return {
        "auth_token": auth_token,
        "lecturenum": lecturenum,
        "lecturecode": lecturecode,
        "chapter": chapter,
        "page": page,
        "study_seconds": studyTime,
        "last_position": totalTime,
        "log_id": log_id,
        "instance_id": instance_id,
        "csrf_token": csrf_token,
    }


def select_first_unfinished_chapter(curriculum_summary: list[dict]) -> dict | None:
    for item in curriculum_summary:
        if item["chapterRate"] < 100:
            return item
    return None


def run_update_process(
    session: requests.Session,
    name: str,
    curriculum_summary: list[dict],
    lecturenum: str,
    lecturecode: str,
    csrf_token: str,
    auth_token: str,
):
    current = select_first_unfinished_chapter(curriculum_summary)

    if not current:
        print(f"🆗 {name} | 모든 챕터가 이미 100% 완료 상태입니다.")
        return

    chapter_index = curriculum_summary.index(current)

    while chapter_index < len(curriculum_summary):
        chapter_info = curriculum_summary[chapter_index]

        chapter = chapter_info["chapter"]
        page = chapter_info["page"]

        print(f"▶ 챕터 시작: {name} / Chapter {chapter} / Page {page}")

        log_id = 0
        instance_id = str(uuid.uuid4())
        totalTime = chapter_info["totalTime"]
        studyTime = 0

        while True:
            payload = build_update_payload(
                lecturenum=lecturenum,
                lecturecode=lecturecode,
                chapter=chapter,
                page=page,
                csrf_token=csrf_token,
                auth_token=auth_token,
                log_id=log_id,
                instance_id=instance_id,
                totalTime=totalTime,
                studyTime=studyTime,
            )

            resp = session.post(UPDATE_URL, data=payload, timeout=10)

            try:
                result = resp.json()
            except Exception:
                if (
                    "/etc/sub_login.asp" in resp.text or
                    "먼저 로그인을 진행해주세요." in resp.text
                ):
                    print(f"❌ {name} | 로그인 해제로 인해 종료")
                    return
                else:
                    print(f"❌ {name} | JSON 응답 파싱 실패, 30초 후 재시도")
                    time.sleep(30)
                    continue

            success = result.get("success", False)
            if success == False:
                message = result.get("message", False)
                print(f"❌ 실패 → {name} | {message}")
                return
            chapter_rate = result.get("chapter_rate", 0)
            log_id = result.get("log_id", log_id)
            total_my_seconds = result.get("total_my_seconds", 0)
            tdateing = result.get("tdateing", 0)
            studyTime += 30

            print(
                f"UPDATE → {name} | Chapter {chapter} | "
                f"Rate={chapter_rate}% | log_id={log_id} | "
                f"tdateing={tdateing} | totalTime={totalTime}"
            )

            # ✅ 챕터 완료 조건
            if chapter_rate >= 100:
                print(f"✔  {name} | Chapter {chapter} 완료, 다음 챕터로 이동")
                break

            time.sleep(30)

        chapter_index += 1

    print(f"🎉 {name} | 모든 챕터 업데이트 완료")


def run_course_worker(
    session: requests.Session,
    name: str,
    curriculum_result: list[dict],
    lecturenum: str,
    lecturecode: str,
    csrf_token: str,
    auth_token: str,
):
    #session = requests.Session()

    try:
        run_update_process(
            session,
            name,
            curriculum_result,
            lecturenum,
            lecturecode,
            csrf_token,
            auth_token,
        )
    finally:
        session.close()


def run_multi_courses(course_jobs: list[dict], max_workers: int = 3):
    """
    course_jobs = [
        {
            "curriculum": ...,
            "lecturenum": "...",
            "lecturecode": "...",
            "csrf_token": "...",
            "auth_token": "...",
        },
        ...
    ]
    """

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []

        for course in course_jobs:
            futures.append(
                executor.submit(
                    run_course_worker,
                    course["session"],
                    course["name"],
                    course["curriculum"],
                    course["lecturenum"],
                    course["lecturecode"],
                    course["csrf_token"],
                    course["auth_token"],
                )
            )

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print("스레드 실행 중 오류:", e)


def main():
    # 아이디는 이렇게 받도록 진행 
    if len(sys.argv) < 3:
        if os.getenv("RUN_DOCKER") == "1":
            print("Usage: docker run -it --rm koreajc <ID> <PW>")
        else:
            print(f"Usage: python3 {sys.argv[0]} <ID> <PW>")
        sys.exit(1)

    tid = sys.argv[1]
    tpwd = sys.argv[2]

    signal.signal(signal.SIGINT, force_exit)
    session = requests.Session()

    # 전역변수 설정
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    })

    # ---- 사용자 입력 ----
    #tid = input("아이디: ").strip()
    #tpwd = getpass("비밀번호: ")

    # ---- 로그인 ----
    if not login(session, tid, tpwd):
        print("❌ 로그인 실패")
        return

    print("✔ 로그인 성공")

    # ---- 이후부터는 session 유지 ----
    # 예:
    # resp = session.get("https://koreajc.com/xxx")
    # html_text = resp.text
    # courses = parse_course_cards(html_text)
    resp = session.get("https://koreajc.com/study/studyroom.asp")
    html_text = resp.text
    csrf_token = extract_csrf_token(html_text)
    courses = parse_course_cards(html_text)
    course_jobs = []

    print("CSRF TOKEN:", csrf_token)
    print("-" * 40)

    #for course in courses:
    #    print(course)
    for course in courses:
        print(f"ℹ️ 체크: {course['title']}")
        html = fetch_studyroom_html(session, course["auth_token"], csrf_token)
        if not html:
            continue
        
        server_data = extract_server_data(html)
        curriculum_result = analyze_curriculum_last_page(server_data)

        course_jobs.append({
            "session": session,
            "name": course["title"],
            "curriculum": curriculum_result,
            "lecturenum": server_data.get("lecturenum"),
            "lecturecode": server_data.get("lecturecode"),
            "csrf_token": csrf_token,
            "auth_token": course["auth_token"],
        })

    run_multi_courses(course_jobs, max_workers=10)


if __name__ == "__main__":
    main()


