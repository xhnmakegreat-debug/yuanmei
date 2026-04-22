"""
三级分类主程序：山水诗判断 → 景观类别 → 书写方式
运行：python classifier.py
"""

import json
import os
import time
import re
from openai import OpenAI
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    API_DELAY, BATCH_SIZE, BATCH_SIZE_S2, BATCH_SIZE_S3,
    POEMS_FILE, RESULTS_FILE,
    PROMPT_IS_SHANSHUI, PROMPT_LANDSCAPE_CATEGORY, PROMPT_WRITING_STYLE,
)

os.makedirs("data", exist_ok=True)
os.makedirs("output", exist_ok=True)

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, timeout=120)


# ── 工具函数 ─────────────────────────────────────────────────

def load_poems() -> list[dict]:
    with open(POEMS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_results() -> dict:
    """加载已有分类结果（断点续传）"""
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_results(results: dict):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def call_llm(prompt: str) -> str:
    """调用DeepSeek API，返回文本"""
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=8192,
        timeout=60,
    )
    return response.choices[0].message.content


def parse_json_response(text: str) -> list[dict]:
    """从LLM输出中提取JSON列表，支持截断容错"""
    text = re.sub(r"```(?:json)?", "", text).strip()

    # 正常解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取完整 [...] 块
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass

    # 截断容错：逐个提取完整的 {...} 对象
    items = []
    for m in re.finditer(r"\{[^{}]*\}", text, re.DOTALL):
        try:
            obj = json.loads(m.group())
            if "id" in obj:
                items.append(obj)
        except Exception:
            pass
    if items:
        print(f"  [容错] 截断响应，抢救到 {len(items)} 条")
        return items

    print(f"  [警告] JSON解析失败，原始输出：{text[:200]}")
    return []


def batch(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ── 三轮分类 ─────────────────────────────────────────────────

def stage1_is_shanshui(poems: list[dict], results: dict) -> dict:
    """第一轮：判断是否为山水诗"""
    pending = [p for p in poems if p["id"] not in results or "is_shanshui" not in results[p["id"]]]
    print(f"\n=== 第一轮：山水诗判断，待处理 {len(pending)} 首 ===")

    for i, chunk in enumerate(batch(pending, BATCH_SIZE)):
        poems_json = json.dumps(
            [{"id": p["id"], "title": p["title"], "content": p["content"]} for p in chunk],
            ensure_ascii=False
        )
        prompt = PROMPT_IS_SHANSHUI.format(poems_json=poems_json)
        try:
            raw = call_llm(prompt)
            items = parse_json_response(raw)
            for item in items:
                pid = str(item.get("id", ""))
                if pid:
                    if pid not in results:
                        results[pid] = {}
                    results[pid]["is_shanshui"] = item.get("is_shanshui", False)
                    results[pid]["stage1_confidence"] = item.get("confidence", "")
                    results[pid]["stage1_reason"] = item.get("reason", "")
        except Exception as e:
            print(f"  [错误] 批次{i}失败: {e}")

        if (i + 1) % 10 == 0:
            save_results(results)
            shanshui_count = sum(1 for v in results.values() if v.get("is_shanshui"))
            print(f"  进度 {(i+1)*BATCH_SIZE}/{len(pending)}，当前山水诗 {shanshui_count} 首")

        time.sleep(API_DELAY)

    save_results(results)
    return results


def stage2_landscape(poems: list[dict], results: dict) -> dict:
    """第二轮：景观类别分类（仅对山水诗）"""
    shanshui_ids = {p["id"] for p in poems if results.get(p["id"], {}).get("is_shanshui")}
    pending = [p for p in poems if p["id"] in shanshui_ids and "categories" not in results.get(p["id"], {})]
    print(f"\n=== 第二轮：景观类别，待处理 {len(pending)} 首 ===")

    for i, chunk in enumerate(batch(pending, BATCH_SIZE_S2)):
        poems_json = json.dumps(
            [{"id": p["id"], "title": p["title"], "content": p["content"]} for p in chunk],
            ensure_ascii=False
        )
        prompt = PROMPT_LANDSCAPE_CATEGORY.format(poems_json=poems_json)
        try:
            raw = call_llm(prompt)
            items = parse_json_response(raw)
            for item in items:
                pid = str(item.get("id", ""))
                if pid and pid in results:
                    results[pid]["categories"] = item.get("categories", [])
                    results[pid]["primary_category"] = item.get("primary", "")
                    results[pid]["stage2_reason"] = item.get("reason", "")
        except Exception as e:
            print(f"  [错误] 批次{i}失败: {e}")

        if (i + 1) % 10 == 0:
            save_results(results)
            print(f"  进度 {(i+1)*BATCH_SIZE}/{len(pending)}")

        time.sleep(API_DELAY)

    save_results(results)
    return results


def stage3_writing_style(poems: list[dict], results: dict) -> dict:
    """第三轮：书写方式分类（仅对山水诗）"""
    shanshui_ids = {p["id"] for p in poems if results.get(p["id"], {}).get("is_shanshui")}
    pending = [p for p in poems if p["id"] in shanshui_ids and "style" not in results.get(p["id"], {})]
    print(f"\n=== 第三轮：书写方式，待处理 {len(pending)} 首 ===")

    for i, chunk in enumerate(batch(pending, BATCH_SIZE_S3)):
        poems_json = json.dumps(
            [{"id": p["id"], "title": p["title"], "content": p["content"]} for p in chunk],
            ensure_ascii=False
        )
        prompt = PROMPT_WRITING_STYLE.format(poems_json=poems_json)
        try:
            raw = call_llm(prompt)
            items = parse_json_response(raw)
            for item in items:
                pid = str(item.get("id", ""))
                if pid and pid in results:
                    results[pid]["style"] = item.get("style", "")
                    results[pid]["style_confidence"] = item.get("confidence", "")
                    results[pid]["stage3_reason"] = item.get("reason", "")
        except Exception as e:
            print(f"  [错误] 批次{i}失败: {e}")

        if (i + 1) % 10 == 0:
            save_results(results)
            print(f"  进度 {(i+1)*BATCH_SIZE}/{len(pending)}")

        time.sleep(API_DELAY)

    save_results(results)
    return results


# ── 统计报告 ─────────────────────────────────────────────────

def generate_report(poems: list[dict], results: dict):
    from collections import Counter
    from config import SUMMARY_FILE, CSV_FILE

    total = len(poems)
    shanshui = [p for p in poems if results.get(p["id"], {}).get("is_shanshui")]
    shanshui_count = len(shanshui)

    # 景观类别统计（以primary_category为准）
    primary_counter = Counter()
    all_categories_counter = Counter()
    for p in shanshui:
        r = results.get(p["id"], {})
        if r.get("primary_category"):
            primary_counter[r["primary_category"]] += 1
        for cat in r.get("categories", []):
            all_categories_counter[cat] += 1

    # 书写方式统计
    style_counter = Counter()
    for p in shanshui:
        r = results.get(p["id"], {})
        if r.get("style"):
            style_counter[r["style"]] += 1

    # 输出文本报告
    lines = [
        "=" * 60,
        "袁枚《小仓山房诗集》山水诗统计分析报告",
        "=" * 60,
        f"\n【总诗数】{total} 首",
        f"【山水诗数量】{shanshui_count} 首（占比 {shanshui_count/total*100:.1f}%）",
        "\n【景观类别分布（主类）】",
    ]
    for cat, cnt in primary_counter.most_common():
        lines.append(f"  {cat}：{cnt} 首（{cnt/shanshui_count*100:.1f}%）")

    lines.append("\n【景观类别分布（含兼类）】")
    for cat, cnt in all_categories_counter.most_common():
        lines.append(f"  {cat}：{cnt} 首")

    lines.append("\n【书写方式分布】")
    for style, cnt in style_counter.most_common():
        lines.append(f"  {style}：{cnt} 首（{cnt/shanshui_count*100:.1f}%）")

    # 存疑项统计（供论文写作时标注）
    review_stage1 = [p for p in shanshui if results.get(p["id"], {}).get("stage1_confidence") == "C"]
    review_stage2 = [p for p in shanshui if results.get(p["id"], {}).get("categories") and
                     results.get(p["id"], {}).get("confidence") == "C"]
    review_stage3 = [p for p in shanshui if results.get(p["id"], {}).get("style_confidence") == "C"]
    lines.append(f"\n【需人工复核的存疑项】")
    lines.append(f"  山水诗判断存疑（C级）：{len(review_stage1)} 首")
    lines.append(f"  景观类别存疑（C级）：{len(review_stage2)} 首")
    lines.append(f"  书写方式存疑（C级）：{len(review_stage3)} 首")

    report = "\n".join(lines)
    print("\n" + report)

    os.makedirs("output", exist_ok=True)
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n报告已保存至 {SUMMARY_FILE}")

    # 输出CSV
    import csv
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "标题", "是否山水诗", "判断置信度", "判断依据", "主景观类别", "景观置信度", "全部景观类别", "书写方式", "书写方式置信度", "需复核"])
        for p in poems:
            r = results.get(p["id"], {})
            needs_review = any([
                r.get("stage1_confidence") == "C",
                r.get("confidence") == "C",
                r.get("style_confidence") == "C",
            ])
            writer.writerow([
                p["id"], p["title"],
                "是" if r.get("is_shanshui") else "否",
                r.get("stage1_confidence", ""),
                r.get("stage1_reason", ""),
                r.get("primary_category", ""),
                r.get("confidence", ""),
                "、".join(r.get("categories", [])),
                r.get("style", ""),
                r.get("style_confidence", ""),
                "★需复核" if needs_review else "",
            ])
    print(f"CSV已保存至 {CSV_FILE}")


# ── 主流程 ───────────────────────────────────────────────────

def main():
    poems = load_poems()
    print(f"载入 {len(poems)} 首诗")

    results = load_results()
    print(f"已有分类结果：{len(results)} 条")

    results = stage1_is_shanshui(poems, results)
    results = stage2_landscape(poems, results)
    results = stage3_writing_style(poems, results)

    generate_report(poems, results)


if __name__ == "__main__":
    main()
