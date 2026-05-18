#!/usr/bin/env python3
"""
GEO Downloader - 安装配置
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="geo-downloader",
    version="1.0.0",
    author="GEO Downloader Team",
    author_email="downloader@example.com",
    description="GEO Supplementary File download tool with aria2c multi-threading support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/geo-downloader",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Intended Audience :: Science/Research",
    ],
    python_requires=">=3.6",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "geo-downloader=geo_downloader.suppl_downloader:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
