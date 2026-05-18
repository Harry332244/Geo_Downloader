# GEO Downloader

[![Python Version](https://img.shields.io/badge/python-3.6%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**GEO Downloader** 是一个用于从 NCBI GEO 数据库下载 Supplementary File 的 Python 工具包。它可以根据 GSM 或 GSE 编号自动爬取 FTP 链接，并使用 aria2c 实现多线程高速下载。

## ✨ 功能特性

- 🎯 **GSM 模式**：直接输入 GSM 编号，自动爬取其 suppl/ 目录下的所有文件链接
- 🔗 **GSE 模式**：输入 GSE 编号，通过 NCBI E-utilities API 自动获取其下所有 GSM 编号，再爬取每个 GSM 的 suppl 文件
- 📂 **多种输入方式**：命令行参数、文本文件、CSV 文件
- 🔍 **文件过滤**：支持正则表达式匹配/排除特定文件
- 📋 **仅列出模式**：只显示链接不下载，方便预览
- ⚡ **aria2c 多线程下载**：显示进度、速度，支持断点续传
- 📝 **日志记录**：自动记录详细日志到文件

## 📦 安装

### 前置依赖

- Python 3.6+
- [aria2c](https://aria2.github.io/)（推荐）或 wget

安装 aria2c：

```bash
# macOS
brew install aria2

# Ubuntu/Debian
sudo apt install aria2

# CentOS/RHEL
sudo yum install aria2
```

### 安装 geo-downloader

```bash
# 方式一：从源码安装
git clone https://github.com/yourusername/geo-downloader.git
cd geo-downloader
pip install -r requirements.txt
pip install -e .

# 方式二：直接使用（无需安装）
cd geo_downloader_pkg
pip install -r requirements.txt
python -m geo_downloader -h
```

## 🚀 快速开始

### 下载单个 GSM 的特定文件

```bash
# 下载 GSM9358871 的 features.tsv.gz 文件
python -m geo_downloader -g GSM9358871 --pattern ".*features.*tsv.*"
```

### 下载整个 GSE 数据集

```bash
# 自动获取 GSE313006 下所有 GSM，下载 transcripts.parquet.gz 文件
python -m geo_downloader -g GSE313006 --pattern ".*transcripts.*parquet.*"
```

### 只列出链接，不下载

```bash
python -m geo_downloader -g GSE313006 --list-only
```

### 从文件读取 ID 列表

```bash
# 文本文件（每行一个 ID）
python -m geo_downloader -f gsm_list.txt

# CSV 文件（需包含 GSM_ID 或 GSE_ID 列）
python -m geo_downloader --csv data.csv
```

### 排除大文件

```bash
# 下载所有文件，但排除 morphology tif 大文件
python -m geo_downloader -g GSE313006 --exclude ".*morphology.*tif.*"
```

### 指定输出目录和并发数

```bash
python -m geo_downloader -g GSE313006 -o ./geo_data -j 10 -x 16
```

## 📖 命令行参数

| 参数 | 说明 |
|------|------|
| `-g, --ids` | GSM 或 GSE 编号（支持多个，空格分隔） |
| `-f, --file` | 从文本文件读取 ID 列表 |
| `--csv` | 从 CSV 文件读取 ID 列表 |
| `-o, --out` | 输出目录（默认: `./geo_downloads`） |
| `-t, --tool` | 下载工具: `aria`（aria2c）或 `wget` |
| `-j, --concurrent` | aria2c 并发任务数（默认: 5） |
| `-x, --connections` | aria2c 每任务连接数（默认: 16） |
| `--pattern` | 文件匹配正则表达式 |
| `--exclude` | 文件排除正则表达式 |
| `--list-only` | 只列出 suppl 文件链接，不下载 |
| `--no-log` | 不输出日志文件（仅控制台） |

## 📁 输出结构

```
geo_downloads/
├── GSM9358871/
│   ├── GSM9358871_COPD_TMA1_features.tsv.gz
│   ├── GSM9358871_COPD_TMA1_matrix.mtx.gz
│   └── ...
├── GSM9358872/
│   └── ...
├── logs/
│   └── batch_1gse_20260518_110009.log
└── aria2_input_list.txt  (下载完成后自动删除)
```

## 🧩 Python API 使用

```python
from geo_downloader import (
    normalize_id,
    get_gsm_list_from_gse,
    get_gsm_suppl_files,
    filter_files,
    download_via_aria2c,
)

# 解析 GSE 获取 GSM 列表
gsm_list = get_gsm_list_from_gse("GSE313006")
print(f"Found {len(gsm_list)} GSM samples")

# 获取 suppl 文件列表
files = get_gsm_suppl_files("GSM9358871")
for f in files:
    print(f"{f['name']:60s} {f['size']:>10s}")

# 过滤文件
filtered = filter_files(files, pattern=".*features.*tsv.*")

# 下载
tasks = [(f['url'], f"./downloads/{f['gsm']}/{f['name']}") for f in filtered]
download_via_aria2c(tasks, out_dir="./downloads")
```

## 🛠 依赖

- `requests>=2.20` - HTTP 请求库
- `aria2c` 或 `wget` - 下载工具（系统级依赖）

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📬 联系方式

项目链接: [https://github.com/yourusername/geo-downloader](https://github.com/yourusername/geo-downloader)
