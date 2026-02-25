#!/usr/bin/env python3
"""测试必要的Python包是否可用"""

import sys
import subprocess

# 需要检查的包列表
required_packages = [
    'pdfkit',
    'weasyprint',
    'selenium',
    'playwright',
    'pdf2image',
    'requests',
    'beautifulsoup4',
    'readability',
]

print("检查Python包可用性:")
available = {}
for package in required_packages:
    try:
        if package == 'readability':
            # readability可能有不同的导入名
            import readability
            available[package] = True
        else:
            __import__(package)
            available[package] = True
    except ImportError:
        available[package] = False

for package, status in available.items():
    print(f"  {package}: {'✓' if status else '✗'}")

# 检查Node.js和puppeteer
print("\n检查Node.js环境:")
try:
    node_version = subprocess.run(['node', '--version'], capture_output=True, text=True)
    print(f"  Node.js: {node_version.stdout.strip() if node_version.returncode == 0 else '未安装'}")
except FileNotFoundError:
    print("  Node.js: 未安装")

print("\n检查wkhtmltopdf:")
try:
    wkhtmltopdf_version = subprocess.run(['wkhtmltopdf', '--version'], capture_output=True, text=True)
    if wkhtmltopdf_version.returncode == 0:
        print(f"  wkhtmltopdf: 已安装 (版本信息: {wkhtmltopdf_version.stdout.strip()[:50]}...)")
    else:
        print("  wkhtmltopdf: 未安装或不可用")
except FileNotFoundError:
    print("  wkhtmltopdf: 未安装")