# 古典诗歌山水诗分析工具

基于 DeepSeek API 对中国古典诗集进行山水诗自动分类统计，支持网络爬取与 TXT 文件两种数据输入方式。

## 功能

- **三级分类**：山水诗判断 → 景观类别 → 书写方式
- **置信度标注**：A/B/C 三级，C 级自动标记供人工复核
- **断点续传**：中途中断后重新运行自动跳过已完成部分
- **验证工具**：随机抽样、存疑项审查、导出人工标注表格
- **TXT 输入**：支持本地文本文件直接导入分析

## 快速开始

### 1. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install requests beautifulsoup4 openai
```

### 2. 配置 API Key

```bash
cp config.example.py config.py
# 编辑 config.py，填入 DeepSeek API Key
```

### 3. 准备数据（二选一）

**方式A：从 TXT 文件导入**
```bash
python3 txt_parser.py --input 你的诗集.txt --preview   # 先预览
python3 txt_parser.py --input 你的诗集.txt             # 确认后保存
```

**方式B：从网络爬取（袁枚小仓山房诗集）**
```bash
python3 scraper.py          # 中华典藏版（约900首，快）
python3 scraper_souyun.py   # 搜韵网版（约4500首，需8-10小时）
```

### 4. 运行分类

```bash
python3 classifier.py
```

### 5. 验证结果

```bash
python3 verify.py --mode export          # 导出100首抽样表格
python3 verify.py --mode false_pos --n 30  # 验证精确率
python3 verify.py --mode false_neg --n 30  # 验证召回率
python3 verify.py --mode review            # 查看存疑项
```

## 输出文件

| 文件 | 内容 |
|------|------|
| `output/summary.txt` | 统计分析报告 |
| `output/results.csv` | 完整分类结果（含置信度） |
| `output/verify_sample.csv` | 人工验证抽样表格 |

## 分类体系

### 山水诗判断
以自然山水为主要审美对象，融情于景、情景交融。

### 景观类别（五类）
- 山岳峰峦类
- 江河湖溪类
- 瀑布泉流类
- 岩石洞穴类
- 云雾气象类

### 书写方式（三类）
| 类型 | 身体状态 | 感知方式 |
|------|----------|----------|
| 静观 | 静止 | 视觉主导 |
| 静听 | 静止 | 听觉主导 |
| 游观 | 移动 | 综合感知 |

## License

MIT
