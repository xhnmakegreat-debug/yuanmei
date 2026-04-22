"""
搜韵网袁枚诗歌全量爬虫（慢速版，挂夜跑）
预计耗时：8-10小时（4500首 × 6-8秒/首）
运行：python3 scraper_souyun.py
断点续传：中途中断后直接重新运行，会自动跳过已完成部分
"""

import json
import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup

os.makedirs("data", exist_ok=True)

BASE_URL = "https://sou-yun.cn"
AUTHOR_ID = "69423"
TOTAL_PAGES = 229

META_FILE = "data/souyun_meta.json"       # 诗歌ID列表（第一阶段）
SOUYUN_FILE = "data/souyun_poems.json"    # 完整诗歌数据（第二阶段）

# 模拟真实浏览器的完整Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def warm_up():
    """先访问主页获取Cookie，模拟真实用户行为"""
    try:
        resp = SESSION.get(BASE_URL, timeout=15)
        print(f"  暖身请求: {resp.status_code}，获取Cookie: {dict(SESSION.cookies)}")
        time.sleep(random.uniform(2, 4))
    except Exception as e:
        print(f"  暖身失败（不影响主流程）: {e}")


def smart_sleep(base: float = 6.0):
    """随机延迟，避免固定间隔被识别"""
    delay = base + random.uniform(0, 3)
    time.sleep(delay)


def get_with_retry(url: str, referer: str = BASE_URL, max_retries: int = 6) -> requests.Response:
    """带指数退避的请求"""
    SESSION.headers.update({"Referer": referer})
    wait = 10
    for attempt in range(max_retries):
        try:
            resp = SESSION.get(url, timeout=20)
            if resp.status_code == 429:
                print(f"\n  [限速429] 等待{wait}s (第{attempt+1}次)...")
                time.sleep(wait + random.uniform(0, 5))
                wait = min(wait * 2, 300)
                continue
            if resp.status_code == 200:
                return resp
            print(f"  [HTTP {resp.status_code}] {url}")
            time.sleep(wait)
            wait *= 2
        except requests.exceptions.RequestException as e:
            print(f"  [网络错误] {e}，等待{wait}s...")
            time.sleep(wait)
            wait *= 2
    raise Exception(f"请求彻底失败({max_retries}次): {url}")


# ── 第一阶段：收集诗歌ID ──────────────────────────────────────

def load_meta() -> dict:
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_meta(meta: dict):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def fetch_poem_list(page: int) -> list[dict]:
    url = f"{BASE_URL}/PoemIndex.aspx?dynasty=Qing&author={AUTHOR_ID}&type=All&page={page}"
    referer = f"{BASE_URL}/PoemIndex.aspx?dynasty=Qing&author={AUTHOR_ID}&type=All&page={max(0,page-1)}"
    try:
        resp = get_with_retry(url, referer=referer)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        poems = []
        for a in soup.select("a[href*='Query.aspx?type=poem1&id=']"):
            m = re.search(r"id=(\d+)", a.get("href", ""))
            if m:
                poems.append({"id": m.group(1), "title": a.get_text(strip=True)})
        return poems
    except Exception as e:
        print(f"  [错误] 第{page}页失败: {e}")
        return []


def stage1_collect_ids():
    meta = load_meta()
    done_pages = {int(v.get("_page", -1)) for v in meta.values()}
    remaining = [p for p in range(TOTAL_PAGES) if p not in done_pages]

    if not remaining:
        print(f"  ID列表已完整，共 {len(meta)} 首\n")
        return meta

    print(f"=== 第一阶段：收集诗歌ID（已完成{len(done_pages)}页，剩余{len(remaining)}页）===")
    for i, page in enumerate(remaining):
        poems = fetch_poem_list(page)
        for p in poems:
            p["_page"] = page
            meta[p["id"]] = p
        save_meta(meta)

        elapsed_pages = i + 1
        est_remaining = (len(remaining) - elapsed_pages) * 6.5 / 60
        print(f"  第{page+1}/{TOTAL_PAGES}页 | 累计{len(meta)}首 | 预计剩余{est_remaining:.0f}分钟", end="\r")
        smart_sleep(5)

    print(f"\n第一阶段完成：共 {len(meta)} 首诗\n")
    return meta


# ── 第二阶段：获取诗歌正文 ────────────────────────────────────

def load_souyun() -> dict:
    if os.path.exists(SOUYUN_FILE):
        with open(SOUYUN_FILE, "r", encoding="utf-8") as f:
            return {p["id"]: p for p in json.load(f)}
    return {}


def save_souyun(poems: dict):
    with open(SOUYUN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(poems.values()), f, ensure_ascii=False, indent=2)


def fetch_poem_content(poem_id: str, title: str) -> dict:
    url = f"{BASE_URL}/Query.aspx?type=poem1&id={poem_id}"
    referer = f"{BASE_URL}/PoemIndex.aspx?dynasty=Qing&author={AUTHOR_ID}"
    try:
        resp = get_with_retry(url, referer=referer)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 正文：尝试多个可能的容器
        content = ""
        for selector in ["#poemcontent", ".poemBody", "#poem", ".content", "div.panel-body"]:
            tag = soup.select_one(selector)
            if tag:
                content = tag.get_text("\n", strip=True)
                if len(content) > 10:
                    break

        # 兜底：抓<p>里像诗句的段落
        if not content or len(content) < 10:
            lines = []
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if 4 <= len(text) <= 50 and re.search(r"[一-鿿]{3,}", text):
                    lines.append(text)
            content = "\n".join(lines)

        # 出处
        source = ""
        for tag in soup.find_all(string=re.compile(r"小倉山房|小仓山房")):
            source = str(tag).strip()
            break

        # 完善标题
        if not title:
            h = soup.select_one("h1, .poemTitle, .poem-title")
            title = h.get_text(strip=True) if h else ""

        return {"id": poem_id, "title": title, "content": content, "source": source}
    except Exception as e:
        print(f"\n  [错误] 诗歌{poem_id}失败: {e}")
        return {"id": poem_id, "title": title, "content": "", "source": ""}


def stage2_fetch_content(meta: dict):
    existing = load_souyun()
    to_fetch = [pid for pid in meta if pid not in existing or not existing[pid].get("content")]
    total = len(to_fetch)

    if not to_fetch:
        print(f"  正文已全部获取，共 {len(existing)} 首\n")
        return existing

    print(f"=== 第二阶段：获取正文（待处理{total}首，预计{total*6.5/3600:.1f}小时）===\n")

    start_time = time.time()
    for i, poem_id in enumerate(to_fetch):
        poem = fetch_poem_content(poem_id, meta[poem_id].get("title", ""))
        existing[poem_id] = poem

        if (i + 1) % 20 == 0:
            save_souyun(existing)
            elapsed = (time.time() - start_time) / 3600
            speed = (i + 1) / elapsed / 3600  # 首/秒
            est = (total - i - 1) * 6.5 / 3600
            print(f"  进度 {i+1}/{total} | 已耗时{elapsed:.1f}h | 预计剩余{est:.1f}h")

        smart_sleep(6)

    save_souyun(existing)
    print(f"\n第二阶段完成：共 {len(existing)} 首诗")
    return existing


# ── 主流程 ───────────────────────────────────────────────────

def main():
    print("=== 搜韵网袁枚诗歌全量爬虫（慢速版）===\n")
    warm_up()
    meta = stage1_collect_ids()
    poems = stage2_fetch_content(meta)

    # 为classifier.py生成统一格式（与diancang版本兼容）
    unified = []
    for i, (pid, p) in enumerate(poems.items()):
        unified.append({
            "id": str(i + 1),
            "souyun_id": pid,
            "title": p.get("title", ""),
            "content": p.get("content", ""),
            "source": p.get("source", ""),
            "chapter": "",
        })
    with open("data/poems.json", "w", encoding="utf-8") as f:
        json.dump(unified, f, ensure_ascii=False, indent=2)
    print(f"\n已合并输出至 data/poems.json（{len(unified)}首），可直接运行 classifier.py")


if __name__ == "__main__":
    main()
