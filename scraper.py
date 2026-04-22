"""
从中华典藏爬取袁枚《小仓山房诗集》全文
运行：python scraper.py
"""

import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from config import POEMS_FILE, REQUEST_DELAY

os.makedirs("data", exist_ok=True)

BASE = "https://www.diancang.xyz"
TOC_URL = f"{BASE}/shicixiqu/17961/"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})


def get_chapter_urls() -> list[tuple[str, str]]:
    """从目录页获取所有章节URL，返回 [(title, url), ...]"""
    resp = SESSION.get(TOC_URL, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    seen = set()
    chapters = []
    for a in soup.find_all("a", href=re.compile(r"/17961/\d+\.html")):
        url = a["href"]
        if not url.startswith("http"):
            url = BASE + url
        if url not in seen:
            seen.add(url)
            chapters.append((a.get_text(strip=True), url))
    return chapters


def is_title(text: str) -> bool:
    """判断一个<p>是诗题还是正文"""
    # 正文特征：包含句读（，。！？）或超过30字
    if re.search(r"[，。！？；：]", text):
        return False
    if len(text) > 40:
        return False
    # 标注性内容（〈...〉括号注释）不算标题
    if text.startswith("〈") or text.startswith("（"):
        return False
    return True


def parse_poems_from_chapter(html: str, chapter_title: str) -> list[dict]:
    """从章节HTML中解析出所有诗歌，返回 [{title, content, chapter}, ...]"""
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.find(id="content")
    if not content_div:
        return []

    paragraphs = [p.get_text(strip=True) for p in content_div.find_all("p") if p.get_text(strip=True)]

    poems = []
    current_title = ""
    current_content_parts = []

    def flush():
        if current_title and current_content_parts:
            poems.append({
                "title": current_title,
                "content": "\n".join(current_content_parts),
                "chapter": chapter_title,
            })

    for para in paragraphs:
        if is_title(para):
            flush()
            current_title = para
            current_content_parts = []
        else:
            # 跳过纯注释段（全是括号内容）
            if para.startswith("〈") and para.endswith("〉"):
                continue
            if current_title:
                current_content_parts.append(para)

    flush()
    return poems


def load_existing() -> list[dict]:
    if os.path.exists(POEMS_FILE):
        with open(POEMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save(poems: list[dict]):
    with open(POEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(poems, f, ensure_ascii=False, indent=2)


def main():
    existing = load_existing()
    done_chapters = {p["chapter"] for p in existing}
    print(f"已有数据：{len(existing)} 首诗，已完成章节：{len(done_chapters)} 个\n")

    chapters = get_chapter_urls()
    print(f"目录共 {len(chapters)} 章节\n")

    all_poems = list(existing)

    for i, (title, url) in enumerate(chapters):
        if title in done_chapters:
            print(f"  [{i+1}/{len(chapters)}] 跳过（已完成）：{title}")
            continue

        try:
            resp = SESSION.get(url, timeout=15)
            resp.encoding = "utf-8"
            poems = parse_poems_from_chapter(resp.text, title)
            all_poems.extend(poems)
            save(all_poems)
            print(f"  [{i+1}/{len(chapters)}] {title}：解析 {len(poems)} 首，累计 {len(all_poems)} 首")
        except Exception as e:
            print(f"  [{i+1}/{len(chapters)}] {title} 失败: {e}")

        time.sleep(REQUEST_DELAY)

    print(f"\n完成！共 {len(all_poems)} 首诗，保存至 {POEMS_FILE}")

    # 为每首诗加上 id 字段（分类脚本需要）
    for idx, p in enumerate(all_poems):
        p["id"] = str(idx + 1)
    save(all_poems)
    print("已为所有诗歌添加 id 字段")


if __name__ == "__main__":
    main()
