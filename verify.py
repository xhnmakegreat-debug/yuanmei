"""
分类结果验证工具
用法：
  python3 verify.py --mode random --n 30     # 随机抽30首看分类是否正确
  python3 verify.py --mode review            # 专看C级存疑的诗
  python3 verify.py --mode false_pos --n 20  # 看被判为"山水诗"的样本（验证误判率）
  python3 verify.py --mode false_neg --n 20  # 看被判为"非山水诗"的样本（验证漏判率）
  python3 verify.py --mode export            # 导出人工标注表格
"""

import json
import random
import argparse
import csv
from config import POEMS_FILE, RESULTS_FILE

def load():
    with open(POEMS_FILE, "r", encoding="utf-8") as f:
        poems = {p["id"]: p for p in json.load(f)}
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)
    return poems, results

def show_poem(p, r):
    print("─" * 60)
    print(f"ID: {p['id']}  标题:【{p['title']}】  章节:{p.get('chapter','')}")
    print(f"正文：\n{p['content'][:200]}")
    print(f"\n▶ 是否山水诗：{'✓ 是' if r.get('is_shanshui') else '✗ 否'}  "
          f"置信度：{r.get('stage1_confidence','')}  "
          f"理由：{r.get('stage1_reason','')}")
    if r.get('is_shanshui'):
        print(f"▶ 景观主类：{r.get('primary_category','')}  "
              f"全部类别：{', '.join(r.get('categories',[]))}  "
              f"置信度：{r.get('confidence','')}")
        print(f"▶ 书写方式：{r.get('style','')}  "
              f"置信度：{r.get('style_confidence','')}")
    print()

def mode_random(poems, results, n):
    ids = list(results.keys())
    sample = random.sample(ids, min(n, len(ids)))
    print(f"\n=== 随机抽样 {len(sample)} 首 ===\n")
    correct = 0
    for pid in sample:
        p = poems.get(pid, {"id": pid, "title": "?", "content": "", "chapter": ""})
        r = results[pid]
        show_poem(p, r)
        ans = input("你认为判断正确吗？[y/n/s(跳过)] ").strip().lower()
        if ans == "y":
            correct += 1
        elif ans == "q":
            break
    total_answered = len([x for x in [input] if x in ["y","n"]])
    print(f"\n验证完成。如果你标记了y/n，可以统计准确率。")

def mode_review(poems, results):
    c_ids = [pid for pid, r in results.items() if
             r.get("stage1_confidence") == "C" or r.get("style_confidence") == "C"]
    print(f"\n=== C级存疑诗歌 共{len(c_ids)}首 ===\n")
    for pid in c_ids:
        p = poems.get(pid, {"id": pid, "title": "?", "content": "", "chapter": ""})
        show_poem(p, results[pid])
        input("回车继续...")

def mode_false_pos(poems, results, n):
    """看山水诗样本，验证是否真的是山水诗（精确率）"""
    pos_ids = [pid for pid, r in results.items() if r.get("is_shanshui")]
    sample = random.sample(pos_ids, min(n, len(pos_ids)))
    print(f"\n=== 山水诗样本 {len(sample)} 首（验证：是否真的是山水诗？）===\n")
    wrong = []
    for pid in sample:
        p = poems.get(pid, {"id": pid, "title": "?", "content": "", "chapter": ""})
        show_poem(p, results[pid])
        ans = input("这首是山水诗吗？[y=是/n=不是/s=跳过] ").strip().lower()
        if ans == "n":
            wrong.append(p["title"])
        elif ans == "q":
            break
    print(f"\n误判（不是山水诗却被判为是）：{len(wrong)} 首")
    for t in wrong:
        print(f"  【{t}】")

def mode_false_neg(poems, results, n):
    """看非山水诗样本，验证有没有漏掉的山水诗（召回率）"""
    neg_ids = [pid for pid, r in results.items() if not r.get("is_shanshui")]
    sample = random.sample(neg_ids, min(n, len(neg_ids)))
    print(f"\n=== 非山水诗样本 {len(sample)} 首（验证：有没有漏判？）===\n")
    missed = []
    for pid in sample:
        p = poems.get(pid, {"id": pid, "title": "?", "content": "", "chapter": ""})
        show_poem(p, results[pid])
        ans = input("这首其实是山水诗吗？[y=是(漏判了)/n=不是(判断正确)/s=跳过] ").strip().lower()
        if ans == "y":
            missed.append(p["title"])
        elif ans == "q":
            break
    print(f"\n漏判（是山水诗却被判为否）：{len(missed)} 首")
    for t in missed:
        print(f"  【{t}】")

def mode_export(poems, results):
    """导出人工标注表格"""
    out = "output/verify_sample.csv"
    shanshui_ids = [pid for pid, r in results.items() if r.get("is_shanshui")]
    non_ids = [pid for pid, r in results.items() if not r.get("is_shanshui")]

    # 山水诗抽50首，非山水诗抽50首
    sample = (random.sample(shanshui_ids, min(50, len(shanshui_ids))) +
              random.sample(non_ids, min(50, len(non_ids))))
    random.shuffle(sample)

    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ID", "标题", "正文（前150字）", "AI判断:山水诗", "AI置信度",
                    "AI理由", "AI景观主类", "AI书写方式", "人工复核:山水诗(填是/否)", "备注"])
        for pid in sample:
            p = poems.get(pid, {"id": pid, "title": "?", "content": "", "chapter": ""})
            r = results[pid]
            w.writerow([
                pid, p["title"], p["content"][:150],
                "是" if r.get("is_shanshui") else "否",
                r.get("stage1_confidence", ""),
                r.get("stage1_reason", ""),
                r.get("primary_category", ""),
                r.get("style", ""),
                "", ""
            ])
    print(f"已导出100首抽样至 {out}，用Excel打开填写「人工复核」列")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["random","review","false_pos","false_neg","export"],
                        default="export")
    parser.add_argument("--n", type=int, default=30)
    args = parser.parse_args()

    poems, results = load()
    print(f"共{len(results)}条分类结果，山水诗{sum(1 for r in results.values() if r.get('is_shanshui'))}首")

    if args.mode == "random":
        mode_random(poems, results, args.n)
    elif args.mode == "review":
        mode_review(poems, results)
    elif args.mode == "false_pos":
        mode_false_pos(poems, results, args.n)
    elif args.mode == "false_neg":
        mode_false_neg(poems, results, args.n)
    elif args.mode == "export":
        mode_export(poems, results)

if __name__ == "__main__":
    main()
