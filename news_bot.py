"""
네이버 뉴스 텔레그램 봇
- 많이 본 뉴스 TOP 7
- 경제/주식 뉴스 TOP 5
- 미국 주식 관련 뉴스 TOP 3 (Google News RSS)
- 국제경제/통상정책 뉴스 TOP 5 (Google News RSS)
→ 네 섹션을 하나의 메시지로 전송 (개인 + 그룹 채팅)
"""

import html
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ── 설정 ──────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8662493054:AAF8H6VpCBgdDdVtqVkUqjeVnSRgH9mi8ZA")
CHAT_IDS = [
    os.environ.get("TELEGRAM_CHAT_ID", "694726450"),   # 개인
    "-5118782534",                                      # 뉴스 그룹
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://news.naver.com",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


# ── 뉴스 수집 ──────────────────────────────────────────────────────
def get_ranking_articles(section_id=None, n=7):
    """네이버 뉴스 랭킹 페이지에서 상위 N개 수집"""
    url = "https://news.naver.com/main/ranking/popularDay.naver"
    if section_id:
        url += f"?sectionId={section_id}"

    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    articles = []
    for item in soup.select(".rankingnews_list li"):
        if len(articles) >= n:
            break
        rank_tag  = item.select_one(".num")
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


def resolve_url(url: str) -> str:
    """Google News 리다이렉트 URL → 실제 기사 URL 변환"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        return r.url
    except Exception:
        return url


def get_google_news_articles(query: str, n: int):
    """Google News RSS에서 키워드 검색 후 상위 N개 수집"""
    url = "https://news.google.com/rss/search"
    params = {
        "q":    query,
        "hl":   "ko",
        "gl":   "KR",
        "ceid": "KR:ko",
    }
    headers = {**HEADERS, "Referer": "https://news.google.com"}
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "xml")

    articles = []
    for item in soup.find_all("item"):
        if len(articles) >= n:
            break
        title_tag = item.find("title")
        desc_tag  = item.find("description")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)

        link = ""
        if desc_tag:
            desc_soup = BeautifulSoup(desc_tag.get_text(), "html.parser")
            a_tag = desc_soup.find("a")
            if a_tag:
                link = a_tag.get("href", "")

        if link:
            link = resolve_url(link)

        articles.append({"rank": str(len(articles) + 1), "title": title, "link": link})

    return articles


# ── 텔레그램 전송 ──────────────────────────────────────────────────
def send_telegram(text: str, chat_id: str) -> bool:
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(api_url, json=payload, timeout=15)
    return resp.ok


# ── 메인 ───────────────────────────────────────────────────────────
def main():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{now_str}] 뉴스 수집 시작")

    popular    = get_ranking_articles(section_id=None, n=7)   # 많이 본 뉴스 TOP 7
    economy    = get_ranking_articles(section_id=101,  n=5)   # 경제 섹션 TOP 5
    us_stock   = get_google_news_articles(                     # 미국 주식 뉴스 TOP 3
        "미국 주식 OR 나스닥 OR S&P500 OR 다우존스 OR 뉴욕증시", n=3
    )
    intl_econ  = get_google_news_articles(                     # 국제경제/통상정책 TOP 5
        "국제경제 OR 글로벌경제 OR 통상정책 OR 무역협정 OR 경제협력 OR 관세 OR FTA site:kr", n=5
    )

    lines = []
    lines.append(f"<b>📢 뉴스 브리핑</b>  {now_str}")
    lines.append("─" * 26)

    # 많이 본 뉴스 TOP 7
    lines.append("")
    lines.append("📰 <b>많이 본 뉴스 TOP 7</b>")
    for art in popular:
        safe_title = html.escape(art["title"])
        lines.append(f"{art['rank']}위. <a href='{art['link']}'>{safe_title}</a>")

    # 경제/주식 뉴스 TOP 5
    lines.append("")
    lines.append("💹 <b>경제/주식 뉴스 TOP 5</b>")
    for i, art in enumerate(economy, 1):
        safe_title = html.escape(art["title"])
        lines.append(f"{i}위. <a href='{art['link']}'>{safe_title}</a>")

    # 미국 주식 뉴스 TOP 3
    lines.append("")
    lines.append("🇺🇸 <b>미국 주식 뉴스 TOP 3</b>")
    if us_stock:
        for i, art in enumerate(us_stock, 1):
            safe_title = html.escape(art["title"])
            lines.append(f"{i}위. <a href='{art['link']}'>{safe_title}</a>")
    else:
        lines.append("미국 주식 관련 뉴스가 없습니다.")

    # 국제경제/통상정책 뉴스 TOP 5
    lines.append("")
    lines.append("🌐 <b>국제경제/통상정책 뉴스 TOP 5</b>")
    if intl_econ:
        for i, art in enumerate(intl_econ, 1):
            safe_title = html.escape(art["title"])
            lines.append(f"{i}위. <a href='{art['link']}'>{safe_title}</a>")
    else:
        lines.append("국제경제/통상정책 관련 뉴스가 없습니다.")

    message = "\n".join(lines)

    for chat_id in CHAT_IDS:
        ok = send_telegram(message, chat_id)
        print(f"전송 {'완료' if ok else '실패'} → chat_id={chat_id}")


if __name__ == "__main__":
    main()
