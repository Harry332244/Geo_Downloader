"""
GEO Supplementary File 下载主模块
=================================
主流程控制、日志配置、输入解析、CLI 入口
"""

import os
import sys
import csv
import time
import logging
import argparse
from datetime import datetime
from typing import List, Tuple

from .geo_utils import (
    normalize_id,
    get_gsm_list_from_gse,
    get_gsm_suppl_files,
    filter_files,
)
from .downloader import (
    download_via_aria2c,
    download_via_wget,
    check_tool,
)


# ============================================================
#  日志配置
# ============================================================

def setup_logger(out_dir: str, tag: str = "geo_suppl") -> logging.Logger:
    """配置日志: 同时输出到文件和控制台"""
    logger = logging.getLogger("geo_downloader")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    log_dir = os.path.join(out_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


# ============================================================
#  输入解析
# ============================================================

def parse_id_input(inputs: List[str]) -> List[Tuple[str, str]]:
    """
    解析输入的 ID 列表，返回 [(类型, 编号), ...]
    支持空格/逗号/分号分隔
    """
    result = []
    for item in inputs:
        for part in item.replace(',', ' ').replace(';', ' ').split():
            part = part.strip()
            if part:
                normalized = normalize_id(part)
                if normalized:
                    result.append(normalized)
                else:
                    print(f"[!] 无法识别的编号: {part}")
    return result


def read_ids_from_file(file_path: str) -> List[Tuple[str, str]]:
    """
    从文本文件读取 ID 列表 (每行一个)
    """
    result = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            normalized = normalize_id(line)
            if normalized:
                result.append(normalized)
    return result


def read_ids_from_csv(csv_path: str) -> List[Tuple[str, str]]:
    """
    从 CSV 文件读取 ID 列表 (需包含 GSM_ID 或 GSE_ID 列)
    """
    result = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        # 确定列名
        gsm_col = None
        gse_col = None
        for h in reader.fieldnames:
            h_upper = h.upper()
            if 'GSM' in h_upper and ('ID' in h_upper or 'ACCESSION' in h_upper):
                gsm_col = h
            if 'GSE' in h_upper and ('ID' in h_upper or 'ACCESSION' in h_upper):
                gse_col = h

        if not gsm_col and not gse_col:
            print(f"[!] CSV 文件中未找到 GSM_ID 或 GSE_ID 列")
            print(f"    可用列: {reader.fieldnames}")
            return []

        for row in reader:
            # 先尝试 GSM 列
            if gsm_col:
                val = row.get(gsm_col, '').strip()
                if val:
                    for part in val.replace(';', ',').split(','):
                        part = part.strip()
                        if part:
                            normalized = normalize_id(part)
                            if normalized:
                                result.append(normalized)

            # 再尝试 GSE 列
            if gse_col:
                val = row.get(gse_col, '').strip()
                if val:
                    for part in val.replace(';', ',').split(','):
                        part = part.strip()
                        if part:
                            normalized = normalize_id(part)
                            if normalized:
                                result.append(normalized)

    return result


# ============================================================
#  主流程
# ============================================================

def process_gsm_list(gsm_list: List[str],
                     out_dir: str,
                     logger: logging.Logger,
                     tool: str = "aria",
                     max_concurrent: int = 5,
                     max_connections: int = 16,
                     file_pattern: str = None,
                     exclude_pattern: str = None,
                     list_only: bool = False) -> bool:
    """
    处理 GSM 列表：获取 suppl 文件链接并下载
    """
    all_files = []

    # 1. 获取所有 GSM 的 suppl 文件列表
    logger.info(f"{'='*60}")
    logger.info(f"[*] 开始处理 {len(gsm_list)} 个 GSM 样本")
    logger.info(f"{'='*60}")

    for i, gsm in enumerate(gsm_list, 1):
        logger.info(f"\n[{i}/{len(gsm_list)}] 处理 GSM: {gsm}")
        files = get_gsm_suppl_files(gsm, logger)
        all_files.extend(files)
        time.sleep(0.5)  # 避免请求过快

    if not all_files:
        logger.error("[!] 未找到任何 supplementary file")
        return False

    # 2. 文件过滤
    all_files = filter_files(all_files, pattern=file_pattern, exclude_pattern=exclude_pattern)

    if not all_files:
        logger.error("[!] 过滤后没有需要下载的文件")
        return False

    # 3. 如果只是列出链接
    if list_only:
        logger.info(f"\n{'='*60}")
        logger.info(f"[*] Supplementary File 链接列表 ({len(all_files)} 个文件):")
        logger.info(f"{'='*60}")
        for f in all_files:
            logger.info(f"  {f['url']}")
            logger.info(f"    -> GSM: {f['gsm']}, Size: {f['size']}, Name: {f['name']}")
        return True

    # 4. 构建下载任务
    download_tasks = []
    for f in all_files:
        # 保存路径: out_dir/GSMxxxxx/filename
        save_path = os.path.join(out_dir, f['gsm'], f['name'])
        download_tasks.append((f['url'], save_path))

    # 5. 统计文件大小
    total_size = 0
    for url, save_path in download_tasks:
        if os.path.exists(save_path):
            total_size += os.path.getsize(save_path)

    logger.info(f"\n{'='*60}")
    logger.info(f"[*] 下载准备就绪:")
    logger.info(f"    文件总数: {len(download_tasks)}")
    logger.info(f"    输出目录: {out_dir}")
    logger.info(f"    下载工具: {tool}")
    logger.info(f"{'='*60}")

    # 6. 执行下载
    if tool == "aria":
        return download_via_aria2c(
            download_tasks,
            out_dir,
            logger,
            max_concurrent=max_concurrent,
            max_connections=max_connections
        )
    else:
        return download_via_wget(
            download_tasks,
            out_dir,
            logger,
            retries=5
        )


# ============================================================
#  CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="GEO Supplementary File 下载工具 (支持 GSM/GSE，使用 aria2c 多线程下载)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 单个 GSM
  python -m geo_downloader -g GSM9358871

  # 多个 GSM
  python -m geo_downloader -g GSM9358871 GSM9358872 GSM9358873

  # 单个 GSE (自动获取其下所有 GSM)
  python -m geo_downloader -g GSE313006

  # 多个 GSE
  python -m geo_downloader -g GSE313006 GSE123456

  # 从文件读取
  python -m geo_downloader -f gsm_list.txt

  # 从 CSV 读取
  python -m geo_downloader --csv data.csv

  # 只列出链接不下载
  python -m geo_downloader -g GSE313006 --list-only

  # 下载特定文件 (如只下载 transcripts.parquet.gz)
  python -m geo_downloader -g GSE313006 --pattern ".*transcripts.*parquet.*"

  # 排除大文件 (如 morphology tif)
  python -m geo_downloader -g GSE313006 --exclude ".*morphology.*tif.*"

  # 指定输出目录和并发数
  python -m geo_downloader -g GSE313006 -o ./geo_data -j 10

  # 使用 wget 下载
  python -m geo_downloader -g GSM9358871 -t wget
        """
    )

    # 输入方式 (互斥)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument('-g', '--ids', nargs='+',
                             help='GSM 或 GSE 编号 (支持多个，空格分隔)')
    input_group.add_argument('-f', '--file',
                             help='从文本文件读取 ID 列表 (每行一个)')
    input_group.add_argument('--csv',
                             help='从 CSV 文件读取 ID 列表 (需包含 GSM_ID 或 GSE_ID 列)')

    # 其他选项
    parser.add_argument('-o', '--out', default='./geo_downloads',
                        help='输出目录 (默认: ./geo_downloads)')
    parser.add_argument('-t', '--tool', choices=['aria', 'wget'], default='aria',
                        help='下载工具: aria (aria2c, 默认) 或 wget')
    parser.add_argument('-j', '--concurrent', type=int, default=5,
                        help='aria2c 并发任务数 (默认: 5)')
    parser.add_argument('-x', '--connections', type=int, default=16,
                        help='aria2c 每任务连接数 (默认: 16)')
    parser.add_argument('--pattern',
                        help='文件匹配正则表达式 (如 ".*transcripts.*parquet.*")')
    parser.add_argument('--exclude',
                        help='文件排除正则表达式 (如 ".*morphology.*tif.*")')
    parser.add_argument('--list-only', action='store_true',
                        help='只列出 suppl 文件链接，不下载')
    parser.add_argument('--no-log', action='store_true',
                        help='不输出日志文件 (仅控制台)')

    args = parser.parse_args()

    # ---- 收集 ID 列表 ----
    raw_ids = []

    if args.file:
        if not os.path.exists(args.file):
            print(f"[!] 文件不存在: {args.file}")
            sys.exit(1)
        raw_ids = read_ids_from_file(args.file)
        source_desc = f"文件 {args.file}"
    elif args.csv:
        if not os.path.exists(args.csv):
            print(f"[!] 文件不存在: {args.csv}")
            sys.exit(1)
        raw_ids = read_ids_from_csv(args.csv)
        source_desc = f"CSV 文件 {args.csv}"
    elif args.ids:
        raw_ids = parse_id_input(args.ids)
        source_desc = "命令行参数"
    else:
        parser.print_help()
        sys.exit(0)

    if not raw_ids:
        print("[!] 未找到有效的 GSM/GSE 编号")
        sys.exit(1)

    # ---- 分离 GSM 和 GSE ----
    gsm_direct = []
    gse_list = []

    for id_type, id_code in raw_ids:
        if id_type == 'GSM':
            gsm_direct.append(id_code)
        elif id_type == 'GSE':
            gse_list.append(id_code)

    # ---- 创建输出目录 ----
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    # ---- 设置日志 ----
    if args.no_log:
        logger = logging.getLogger("geo_downloader")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)
    else:
        total_items = len(gsm_direct) + len(gse_list)
        logger = setup_logger(out_dir, f"batch_{total_items}items")

    logger.info(f"[*] 从 {source_desc} 读取到 {len(raw_ids)} 个编号")
    logger.info(f"    直接 GSM: {len(gsm_direct)} 个")
    logger.info(f"    GSE (需解析): {len(gse_list)} 个")

    # ---- 解析 GSE 获取 GSM 列表 ----
    all_gsm = list(gsm_direct)  # 直接指定的 GSM

    for gse in gse_list:
        logger.info(f"\n{'='*60}")
        gsm_from_gse = get_gsm_list_from_gse(gse, logger)
        all_gsm.extend(gsm_from_gse)
        time.sleep(0.5)  # API 限速

    # 去重并排序
    all_gsm = sorted(set(all_gsm))

    if not all_gsm:
        logger.error("[!] 没有有效的 GSM 编号需要处理")
        sys.exit(1)

    logger.info(f"\n[*] 总共 {len(all_gsm)} 个唯一的 GSM 样本需要处理")

    # ---- 检查下载工具 ----
    if not args.list_only:
        if args.tool == "aria":
            if not check_tool("aria2c"):
                logger.warning("[!] aria2c 未安装，尝试使用 wget 作为备选")
                if check_tool("wget"):
                    args.tool = "wget"
                    logger.info("[*] 已切换至 wget")
                else:
                    logger.error("[!] wget 也未安装，请先安装下载工具:")
                    logger.error("    macOS: brew install aria2")
                    logger.error("    Ubuntu: sudo apt install aria2")
                    sys.exit(1)
        else:
            if not check_tool("wget"):
                logger.warning("[!] wget 未安装，尝试使用 aria2c 作为备选")
                if check_tool("aria2c"):
                    args.tool = "aria"
                    logger.info("[*] 已切换至 aria2c")
                else:
                    logger.error("[!] aria2c 也未安装")
                    sys.exit(1)

    # ---- 记录启动信息 ----
    logger.info(f"\n{'='*60}")
    logger.info(f"GEO Supplementary File 下载脚本启动")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"输出目录: {out_dir}")
    logger.info(f"下载工具: {args.tool}")
    logger.info(f"GSM 总数: {len(all_gsm)}")
    if args.pattern:
        logger.info(f"文件匹配: {args.pattern}")
    if args.exclude:
        logger.info(f"文件排除: {args.exclude}")
    if args.list_only:
        logger.info(f"模式: 仅列出链接")
    logger.info(f"{'='*60}")

    # ---- 执行主流程 ----
    success = process_gsm_list(
        gsm_list=all_gsm,
        out_dir=out_dir,
        logger=logger,
        tool=args.tool,
        max_concurrent=args.concurrent,
        max_connections=args.connections,
        file_pattern=args.pattern,
        exclude_pattern=args.exclude,
        list_only=args.list_only,
    )

    # ---- 最终统计 ----
    logger.info(f"\n{'='*60}")
    if args.list_only:
        logger.info(f"[*] 链接列表已输出完毕")
    elif success:
        logger.info(f"[+] ✓ 全部任务完成!")
    else:
        logger.info(f"[!] 部分任务失败，请检查日志")
    logger.info(f"  输出目录: {out_dir}")
    if not args.no_log:
        logger.info(f"  日志文件: {os.path.join(out_dir, 'logs')}")
    logger.info(f"{'='*60}")

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
