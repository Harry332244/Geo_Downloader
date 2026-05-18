"""
GEO Downloader - GEO Supplementary File 下载工具包
=================================================

根据 GSM/GSE 编号爬取 GEO supplementary file 的 FTP 链接，
并使用 aria2c 实现多线程下载。

主要模块:
    - suppl_downloader: 主下载逻辑
    - geo_utils: GEO 编号处理、FTP 页面解析、NCBI API 调用
    - downloader: 下载核心 (aria2c/wget)
"""

from .suppl_downloader import main as cli_main
from .geo_utils import (
    normalize_id,
    get_gsm_series_dir,
    get_gse_series_dir,
    get_gsm_list_from_gse,
    get_gsm_suppl_files,
    filter_files,
)
from .downloader import download_via_aria2c, download_via_wget, check_tool

__version__ = "1.0.0"
__author__ = "GEO Downloader Team"
__description__ = "GEO Supplementary File download tool with aria2c multi-threading support"
