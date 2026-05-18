"""
GEO 工具模块
=============
GEO 编号处理、FTP 页面解析、NCBI E-utilities API 调用
"""

import re
import time
import logging
from typing import List, Tuple, Optional, Dict
from urllib.parse import quote

try:
    import requests
except ImportError:
    print("[!] 缺少 requests 库，请执行: pip install requests")
    raise


# ============================================================
#  常量配置
# ============================================================

# NCBI E-utilities API
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL = "downloader@example.com"  # NCBI 要求提供邮箱


# ============================================================
#  ID 编号处理
# ============================================================

def normalize_id(code: str) -> Optional[Tuple[str, str]]:
    """
    规范化编号，返回 (类型, 规范化编号)
    类型: 'GSM', 'GSE', 或 None
    """
    code = str(code).strip().strip('"').strip("'")
    if not code:
        return None
    upper = code.upper()
    if upper.startswith('GSM'):
        return ('GSM', upper)
    elif upper.startswith('GSE'):
        return ('GSE', upper)
    elif code.isdigit():
        # 纯数字，默认当作 GSM
        return ('GSM', f'GSM{code}')
    return None


def get_gsm_series_dir(gsm_code: str) -> str:
    """
    根据 GSM 编号计算 GEO FTP 上的 samples 目录名
    GEO FTP 目录结构: GSM 编号的数字部分取前 4 位 + 'nnn'
    例如: GSM9358871 -> GSM9358nnn
    """
    number = gsm_code[3:]  # 去掉 'GSM' 前缀
    prefix = number[:4]
    return f'GSM{prefix}nnn'


def get_gse_series_dir(gse_code: str) -> str:
    """
    根据 GSE 编号计算 GEO FTP 上的 series 目录名
    GSE 编号的数字部分取前 3 位 + 'nnn'
    例如: GSE313006 -> GSE313nnn
    """
    number = gse_code[3:]
    prefix = number[:3]
    return f'GSE{prefix}nnn'


# ============================================================
#  NCBI E-utilities API 调用
# ============================================================

def entrez_search(db: str, term: str, retmax: int = 100) -> List[str]:
    """执行 ESearch 查询，返回 ID 列表"""
    params = {
        "db": db,
        "term": term,
        "retmax": retmax,
        "email": EMAIL,
        "retmode": "json",
    }
    url = f"{EUTILS_BASE}/esearch.fcgi"
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"[!] ESearch 请求失败: {e}")
        return []


def entrez_summary(db: str, ids: List[str]) -> dict:
    """执行 ESummary 获取详细信息"""
    if not ids:
        return {}
    params = {
        "db": db,
        "id": ",".join(ids),
        "email": EMAIL,
        "retmode": "json",
    }
    url = f"{EUTILS_BASE}/esummary.fcgi"
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[!] ESummary 请求失败: {e}")
        return {}


def get_gsm_list_from_gse(gse_code: str, logger: logging.Logger = None) -> List[str]:
    """
    根据 GSE 编号获取其下所有 GSM 编号
    返回 GSM 编号列表
    """
    if logger is None:
        logger = logging.getLogger("geo_downloader")

    logger.info(f"[*] 正在查询 GSE {gse_code} 的 GSM 列表...")

    # 1. 搜索 GSE 的 ID
    ids = entrez_search("gds", f"{gse_code}[Accession]")
    if not ids:
        logger.error(f"[!] 未找到 GSE {gse_code} 的记录")
        return []

    logger.info(f"  GSE ID: {ids}")

    # 2. 获取详细信息
    summary = entrez_summary("gds", ids)
    if not summary:
        logger.error(f"[!] 无法获取 GSE {gse_code} 的详细信息")
        return []

    result = summary.get("result", {})
    gsm_list = []

    for uid in result.get("uids", []):
        entry = result.get(uid, {})
        samples = entry.get("samples", [])
        for sample in samples:
            accession = sample.get("accession", "")
            if accession.startswith("GSM"):
                gsm_list.append(accession)

    # 去重并排序
    gsm_list = sorted(set(gsm_list))
    logger.info(f"  ✓ 找到 {len(gsm_list)} 个 GSM 样本: {', '.join(gsm_list[:5])}{'...' if len(gsm_list) > 5 else ''}")

    return gsm_list


# ============================================================
#  GEO FTP 页面解析
# ============================================================

def read_ftp_html(url: str, logger: logging.Logger = None, retries: int = 3, timeout: int = 60) -> List[dict]:
    """
    读取 GEO FTP 页面，解析出文件列表
    返回 [{'name': str, 'size': str, 'url': str}, ...]
    """
    if logger is None:
        logger = logging.getLogger("geo_downloader")

    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                files = []
                for line in r.text.split('\n'):
                    # 匹配 <a href="filename">filename</a> 格式
                    match = re.search(r'<a\s+href="([^"]+)"[^>]*>', line)
                    if match:
                        name = match.group(1)
                        # 跳过父目录链接和子目录
                        if name in ('../', '../', 'Parent Directory'):
                            continue
                        if name.endswith('/'):
                            continue
                        # 只保留以 GSM/GSE 开头的 GEO 数据文件
                        if not name.startswith('GSM') and not name.startswith('GSE'):
                            continue
                        # 提取文件大小 (在 <a> 标签之前)
                        before_a = line.split('<a')[0]
                        size_match = re.search(r'(\d+(?:\.\d+)?)\s*([KMG]?)', before_a)
                        size = (size_match.group(1) + size_match.group(2)) if size_match else ''
                        files.append({
                            'name': name,
                            'size': size,
                            'url': url + quote(name),
                        })
                return files
            else:
                logger.warning(f"  HTTP {r.status_code}，尝试 {attempt}/{retries}")
        except requests.exceptions.Timeout:
            logger.warning(f"  请求超时 ({timeout}s)，尝试 {attempt}/{retries}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"  连接错误: {e}，尝试 {attempt}/{retries}")
        except Exception as e:
            logger.warning(f"  请求异常: {e}，尝试 {attempt}/{retries}")

        if attempt < retries:
            time.sleep(3 * attempt)

    logger.error(f"  多次重试后仍无法访问: {url}")
    return []


def get_gsm_suppl_files(gsm_code: str, logger: logging.Logger = None) -> List[dict]:
    """
    获取指定 GSM 编号的 supplementary file 列表
    返回 [{'name': str, 'size': str, 'url': str, 'gsm': str}, ...]
    """
    if logger is None:
        logger = logging.getLogger("geo_downloader")

    series_dir = get_gsm_series_dir(gsm_code)
    suppl_url = f"https://ftp.ncbi.nlm.nih.gov/geo/samples/{series_dir}/{gsm_code}/suppl/"

    logger.info(f"  [{gsm_code}] 正在解析 suppl 目录: {suppl_url}")

    files = read_ftp_html(suppl_url, logger)
    if not files:
        logger.warning(f"  [GSM {gsm_code}] 未找到 supplementary file 或目录不可访问")
        return []

    # 添加 GSM 信息
    for f in files:
        f['gsm'] = gsm_code

    logger.info(f"  [GSM {gsm_code}] 找到 {len(files)} 个 suppl 文件")
    for f in files:
        logger.info(f"    {f['name']:60s} {f['size']:>10s}")

    return files


# ============================================================
#  文件过滤
# ============================================================

def filter_files(files: List[dict], pattern: str = None, exclude_pattern: str = None) -> List[dict]:
    """根据正则表达式过滤文件列表"""
    if not pattern and not exclude_pattern:
        return files

    result = files

    if pattern:
        regex = re.compile(pattern, re.IGNORECASE)
        result = [f for f in result if regex.search(f['name'])]
        if pattern:
            print(f"  [过滤] 匹配模式 '{pattern}': {len(result)}/{len(files)} 个文件")

    if exclude_pattern:
        exclude_regex = re.compile(exclude_pattern, re.IGNORECASE)
        result = [f for f in result if not exclude_regex.search(f['name'])]
        if exclude_pattern:
            print(f"  [排除] 排除模式 '{exclude_pattern}': {len(result)}/{len(files)} 个文件")

    return result
