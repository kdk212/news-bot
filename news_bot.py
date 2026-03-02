"""
네이버 뉴스 텔레그램 봇
- 많이 본 뉴스 TOP 5
- 경제/주식 뉴스 TOP 3
- 세법 관련 뉴스 TOP 2 (Google News RSS)
"""

import re
import html
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ── 설정 ──────────────────────────────────────────────────────────
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


# ── 뉴스 수집 ──────────────────────────────────────────────────────
def get_ranking_articles(section_id=None, n=5):
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


def get_tax_articles(n=2):
    """세법 관련 뉴스 - Google News RSS"""
    url = "https://news.google.com/rss/search"
    params = {
        "q":    "세법 OR 과세 OR 세금 OR 절세",
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
        guid_tag  = item.find("guid")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link  = guid_tag.get_text(strip=True) if guid_tag else ""
        articles.append({"rank": str(len(articles) + 1), "title": title, "link": link})

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
                        return f"{sentences[0][:95]}.\n{sentences[1][:95]}."
                    elif sentences:
                        return sentences[0][:150]
    except Exception:
        pass
    return "본문을 가져올 수 없습니다."


# ── 텔레그램 전송 ──────────────────────────────────────────────────
def send_telegram(text: str) -> bool:
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(api_url, json=payload, timeout=15)
    return resp.ok


def send_article(art: dict, label: str = ""):
    """기사 1개를 텔레그램으로 전송"""
    summary      = get_article_summary(art["link"])
    safe_title   = html.escape(art["title"])
    safe_summary = html.escape(summary)

    msg = (
        f"<b>[{label}] {safe_title}</b>\n"
        f"\n"
        f"{safe_summary}\n"
        f"\n"
        f"<a href='{art['link']}'>기사 전문 보기</a>"
    )
    ok = send_telegram(msg)
    print(f"  {'OK' if ok else 'FAIL'} [{label}] {art['title'][:30]}")


# ── 메인 ───────────────────────────────────────────────────────────
def main():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{now_str}] 뉴스 수집 시작")

    popular = get_ranking_articles(section_id=None, n=5)   # 많이 본 뉴스 TOP 5
    economy = get_ranking_articles(section_id=101,  n=3)   # 경제 섹션 TOP 3
    tax     = get_tax_articles(n=2)                         # 세법 뉴스 TOP 2

    send_telegram(
        f"<b>뉴스 브리핑</b>  {now_str}\n"
        f"{'─' * 26}"
    )

    send_telegram("📰 <b>많이 본 뉴스 TOP 5</b>")
    for art in popular:
        send_article(art, label=f"{art['rank']}위")

    send_telegram("💹 <b>경제/주식 뉴스 TOP 3</b>")
    for i, art in enumerate(economy, 1):
        send_article(art, label=f"경제 {i}위")

    send_telegram("⚖️ <b>세법 관련 뉴스</b>")
    if tax:
        for i, art in enumerate(tax, 1):
            send_article(art, label=f"세법 {i}")
    else:
        send_telegram("오늘 세법 관련 뉴스가 없습니다.")

    send_telegram("✅ 뉴스 브리핑 완료")
    print("전송 완료")


if __name__ == "__main__":
    main()
