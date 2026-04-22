"""
从TXT文件解析诗歌，替代爬虫作为数据源
支持格式：
  1. 标准格式：标题单独一行，正文紧跟其后
  2. 卷次格式：含"卷X"章节标题
  3. 简单格式：每首诗之间用空行分隔，第一行为标题

用法：
  python3 txt_parser.py --input 你的文件.txt
  python3 txt_parser.py --input 你的文件.txt --preview   # 只预览不保存
"""

import json
import re
import argparse
import os
from config import POEMS_FILE

os.makedirs("data", exist_ok=True)


def detect_format(lines: list[str]) -> str:
    """自动检测TXT格式"""
    has_volume = any(re.match(r"^(卷|第)[一二三四五六七八九十百\d]", l) for l in lines[:50])
    blank_count = sum(1 for l in lines if not l.strip())
    if blank_count > len(lines) * 0.1:
        return "blank_separated"
    if has_volume:
        return "volume"
    return "title_content"


def is_poem_title(line: str) -> bool:
    """判断一行是否为诗题"""
    line = line.strip()
    if not line:
        return False
    # 章节标题（卷次）不算诗题
    if re.match(r"^(卷|第|补遗)[一二三四五六七八九十百\d]", line):
        return False
    # 正文特征：有标点或过长
    if re.search(r"[，。！？；：、]", line):
        return False
    if len(line) > 40:
        return False
    # 注释行
    if line.startswith(("〈", "【", "（", "[")):
        return False
    # 至少含一个汉字
    if not re.search(r"[一-鿿]", line):
        return False
    return True


def parse_title_content(lines: list[str]) -> list[dict]:
    """解析：标题行+正文行交替"""
    poems = []
    current_title = ""
    current_chapter = ""
    content_lines = []

    def flush():
        if current_title and content_lines:
            poems.append({
                "title": current_title,
                "content": "\n".join(content_lines),
                "chapter": current_chapter,
            })

    for line in lines:
        line = line.rstrip()
        if not line:
            continue
        # 章节标题
        if re.match(r"^(卷|第|补遗)[一二三四五六七八九十百\d]", line):
            current_chapter = line.strip()
            continue
        if is_poem_title(line) and not current_title:
            current_title = line.strip()
            content_lines = []
        elif is_poem_title(line) and current_title and not content_lines:
            # 连续两个标题，第一个可能是子标题
            current_title = current_title + "·" + line.strip()
        elif is_poem_title(line) and content_lines:
            flush()
            current_title = line.strip()
            content_lines = []
        else:
            if current_title:
                content_lines.append(line.strip())

    flush()
    return poems


def parse_blank_separated(lines: list[str]) -> list[dict]:
    """解析：空行分隔的诗歌块，每块第一行为标题"""
    poems = []
    current_chapter = ""
    blocks = []
    current_block = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_block:
                blocks.append(current_block)
                current_block = []
        else:
            current_block.append(stripped)
    if current_block:
        blocks.append(current_block)

    for block in blocks:
        if not block:
            continue
        # 章节标题块
        if len(block) == 1 and re.match(r"^(卷|第|补遗)[一二三四五六七八九十百\d]", block[0]):
            current_chapter = block[0]
            continue
        title = block[0]
        content = "\n".join(block[1:])
        if content.strip():
            poems.append({"title": title, "content": content, "chapter": current_chapter})

    return poems


def parse_txt(filepath: str) -> list[dict]:
    # 自动检测编码
    for encoding in ["utf-8", "utf-8-sig", "gbk", "gb2312", "big5"]:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                text = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        raise ValueError("无法识别文件编码，请转换为UTF-8后重试")

    lines = text.splitlines()
    fmt = detect_format(lines)
    print(f"检测到格式：{fmt}，共 {len(lines)} 行")

    if fmt == "blank_separated":
        poems = parse_blank_separated(lines)
    else:
        poems = parse_title_content(lines)

    # 添加ID
    for i, p in enumerate(poems):
        p["id"] = str(i + 1)

    return poems


def main():
    parser = argparse.ArgumentParser(description="从TXT文件解析诗歌")
    parser.add_argument("--input", required=True, help="输入TXT文件路径")
    parser.add_argument("--preview", action="store_true", help="只预览前10首，不保存")
    parser.add_argument("--output", default=POEMS_FILE, help=f"输出JSON路径（默认{POEMS_FILE}）")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"文件不存在：{args.input}")
        return

    poems = parse_txt(args.input)
    print(f"解析完成：共 {len(poems)} 首诗")

    # 统计章节
    from collections import Counter
    chapters = Counter(p["chapter"] for p in poems)
    print(f"章节数：{len(chapters)}")
    for ch, cnt in sorted(chapters.items())[:10]:
        print(f"  {ch or '(无章节)'}: {cnt}首")

    if args.preview:
        print("\n--- 前10首预览 ---")
        for p in poems[:10]:
            print(f"\n【{p['title']}】{p['chapter']}")
            print(p["content"][:80])
        return

    # 确认保存
    confirm = input(f"\n保存到 {args.output}？将覆盖现有数据 [y/n] ").strip().lower()
    if confirm == "y":
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(poems, f, ensure_ascii=False, indent=2)
        print(f"已保存，可运行 python3 classifier.py 开始分类")
    else:
        print("已取消")


if __name__ == "__main__":
    main()
