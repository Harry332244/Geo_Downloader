"""
下载核心模块
=============
aria2c / wget 下载实现
"""

import os
import sys
import logging
import subprocess
from typing import List, Tuple


def check_tool(tool_name: str) -> bool:
    """检查系统是否安装了指定工具"""
    try:
        subprocess.run([tool_name, "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def download_via_aria2c(download_tasks: List[Tuple[str, str]],
                        out_dir: str,
                        logger: logging.Logger = None,
                        max_concurrent: int = 5,
                        max_connections: int = 16) -> bool:
    """
    使用 aria2c 批量下载，显示进度和速度
    """
    if logger is None:
        logger = logging.getLogger("geo_downloader")

    if not download_tasks:
        logger.warning("[!] 没有需要下载的文件")
        return True

    os.makedirs(out_dir, exist_ok=True)

    # 创建 aria2 任务列表文件
    input_file = os.path.join(out_dir, "aria2_input_list.txt")
    with open(input_file, 'w', encoding='utf-8') as f:
        for url, save_path in download_tasks:
            save_dir = os.path.dirname(save_path)
            os.makedirs(save_dir, exist_ok=True)
            f.write(f"{url}\n")
            f.write(f"  dir={os.path.abspath(save_dir)}\n")
            f.write(f"  out={os.path.basename(save_path)}\n")

    total_size = sum(os.path.getsize(p) for _, p in download_tasks if os.path.exists(p))
    logger.info(f"[*] aria2c 启动: {len(download_tasks)} 个任务, 并发={max_concurrent}, 连接数={max_connections}")
    if total_size > 0:
        logger.info(f"    已有 {total_size / 1024 / 1024:.1f} MB 已下载 (断点续传)")

    cmd = [
        "aria2c",
        "-i", input_file,
        "-j", str(max_concurrent),
        "-x", str(max_connections),
        "-s", str(max_connections),
        "--summary-interval=2",       # 每 2 秒显示一次进度摘要
        "--console-log-level=notice",
        "--download-result=full",     # 显示每个文件的下载结果
        "--human-readable=true",      # 人类可读的文件大小
        "--connect-timeout=30",
        "--timeout=120",
        "--max-tries=5",
        "--retry-wait=10",
        "--continue=true",            # 断点续传
        "--allow-overwrite=false",
        "--auto-file-renaming=false",
    ]

    try:
        logger.info(f"[*] 执行: {' '.join(cmd)}")
        # 使用 subprocess 实时输出
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            line = line.rstrip()
            if line:
                # aria2c 的进度行通常包含 [ 或 # 或 % 等字符
                if any(c in line for c in ['%', '#', 'DL:', 'Download']):
                    logger.info(f"  {line}")
                else:
                    logger.debug(line)

        process.wait()

        if process.returncode == 0:
            logger.info("[+] ✓ aria2c 下载全部完成")
            if os.path.exists(input_file):
                os.remove(input_file)
            return True
        else:
            logger.error(f"[!] aria2c 返回错误码: {process.returncode}")
            logger.info(f"  任务列表保留在: {input_file}")
            return False

    except FileNotFoundError:
        logger.error("[!] 未找到 aria2c，请先安装: brew install aria2")
        return False
    except Exception as e:
        logger.error(f"[!] aria2c 执行异常: {e}")
        return False


def download_via_wget(download_tasks: List[Tuple[str, str]],
                      out_dir: str,
                      logger: logging.Logger = None,
                      retries: int = 5) -> bool:
    """
    使用 wget 逐个下载文件 (aria2c 不可用时的备选)
    """
    if logger is None:
        logger = logging.getLogger("geo_downloader")

    if not download_tasks:
        logger.warning("[!] 没有需要下载的文件")
        return True

    success_count = 0
    fail_count = 0
    total = len(download_tasks)

    for idx, (url, save_path) in enumerate(download_tasks, 1):
        save_dir = os.path.dirname(save_path)
        os.makedirs(save_dir, exist_ok=True)

        filename = os.path.basename(save_path)
        logger.info(f"  [{idx}/{total}] 下载: {filename}")

        cmd = [
            "wget",
            "--continue",
            "--tries", str(retries),
            "--timeout", "60",
            "--dns-timeout", "15",
            "--connect-timeout", "30",
            "--read-timeout", "120",
            "--waitretry", "10",
            "--retry-connrefused",
            "--no-dns-cache",
            "--show-progress",        # 显示进度条
            "-O", save_path,
            url
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                success_count += 1
                file_size = os.path.getsize(save_path) if os.path.exists(save_path) else 0
                logger.info(f"    ✓ 完成 ({file_size / 1024 / 1024:.1f} MB) ({success_count}/{total})")
            else:
                fail_count += 1
                logger.warning(f"    ✗ 失败 (错误码: {result.returncode})")
                for line in result.stderr.strip().split('\n')[-3:]:
                    logger.warning(f"      {line}")
        except FileNotFoundError:
            logger.error("[!] 未找到 wget")
            return False
        except Exception as e:
            fail_count += 1
            logger.error(f"    ✗ 异常: {e}")

    logger.info(f"[+] wget 下载完成: 成功 {success_count}/{total}, 失败 {fail_count}/{total}")
    return fail_count == 0
