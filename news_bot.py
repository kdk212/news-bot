"""
네이버 뉴스 TOP 10 텔레그램 봇
매시간 많이 본 뉴스 10개를 텔레그램으로 전송합니다.
"""

import re
import html
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ── 설정 (GitHub Actions에서는 환경변수, 로컬에서는 직접 입력) ──────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8662493054:AAF8H6VpCBgdDdVtqVkUqjeVnSRgH9mi8ZA")
CHAT_ID        = os.environ.get("TELEGRAM_CHAT_ID",   "694726450")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://news.naver.com",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


# ── 네이버 뉴스 TOP 10 수집 ────────────────────────────────────────
def get_top10_articles():
    """네이버 뉴스 '많이 본 뉴스' TOP 10 반환"""
    url = "https://news.naver.com/main/ranking/popularDay.naver"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    for item in soup.select(".rankingnews_list li"):
        if len(articles) >= 10:
            break
        rank_tag = item.select_one(".num")
        title_tag = item.select_one("a.list_title, a[class*='title']")
        if not title_tag:
            continue

        rank  = rank_tag.get_text(strip=True) if rank_tag else str(len(articles) + 1)
        title = title_tag.get_text(strip=True)
        link  = title_tag.get("href", "")
        if link and not link.startswith("http"):
            link = "https://news.naver.com" + link

        articles.append({"rank": rank, "title": title, "link": link})

    return articles


# ── 기사 본문 2줄 요약 ─────────────────────────────────────────────
def get_article_summary(url: str) -> str:
    """기사 URL에서 핵심 2문장 추출"""
    if not url:
        return "링크 없음"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        selectors = [
            "#newsct_article",
            "#articleBodyContents",
            ".newsct_article",
            "._article_content",
            "#articeBody",
        ]
        for sel in selectors:
            tag = soup.select_one(sel)
            if tag:
                for s in tag.select("script, style, .u_likeit_layer, .reporter_area"):
                    s.decompose()
                text = tag.get_text(" ", strip=True)
                text = " ".join(text.split())
                if len(text) > 10:
                    sentences = re.split(r'(?<=[다요임])\. ?', text)
                    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
                    if len(sentences) >= 2:
                        line1 = sentences[0][:95]
                        line2 = sentences[1][:95]
                        return f"{line1}.\n{line2}."
                    elif sentences:
                        return sentences[0][:150]

    except Exception:
        pass
    return "본문을 가져올 수 없습니다."


# ── 텔레그램 전송 ──────────────────────────────────────────────────
def send_telegram(text: str) -> bool:
    """텔레그램 메시지 전송"""
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(api_url, json=payload, timeout=15)
    return resp.ok


# ── 메인 ───────────────────────────────────────────────────────────
def main():
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M")
    print(f"[{now_str}] 뉴스 수집 시작")

    articles = get_top10_articles()
    if not articles:
        send_telegram("뉴스를 가져오지 못했습니다.")
        return

    header = (
        f"<b>네이버 많이 본 뉴스 TOP 10</b>\n"
        f"{now_str}\n"
        f"{'─' * 26}"
    )
    send_telegram(header)

    for art in articles:
        summary = get_article_summary(art["link"])

        # HTML 특수문자 이스케이프 (텔레그램 파싱 오류 방지)
        safe_title   = html.escape(art["title"])
        safe_summary = html.escape(summary)

        msg = (
            f"<b>[{art['rank']}위] {safe_title}</b>\n"
            f"\n"
            f"{safe_summary}\n"
            f"\n"
            f"<a href='{art['link']}'>기사 전문 보기</a>"
        )
        ok = send_telegram(msg)
        print(f"  {'OK' if ok else 'FAIL'} {art['rank']}위")

    send_telegram("TOP 10 전송 완료")
    print("전송 완료")


if __name__ == "__main__":
    main()
