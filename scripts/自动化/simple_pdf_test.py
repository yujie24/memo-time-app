#!/usr/bin/env python3
"""
简单的PDF转换测试
使用requests获取网页内容，然后转换为PDF
"""

import requests
import pdfkit
import time
import os
from pathlib import Path

# 测试简单的静态网页
SIMPLE_URLS = [
    {
        "url": "https://example.com",
        "name": "Example网站",
        "type": "简单静态页"
    },
    {
        "url": "https://httpbin.org/html",
        "name": "HTTPBin测试页",
        "type": "测试页面"
    },
    {
        "url": "https://www.w3.org/TR/html52/",
        "name": "W3C HTML规范",
        "type": "技术文档"
    }
]

def setup_pdfkit():
    """配置pdfkit"""
    try:
        import subprocess
        result = subprocess.run(['which', 'wkhtmltopdf'], capture_output=True, text=True)
        if result.returncode == 0:
            wkhtmltopdf_path = result.stdout.strip()
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            print(f"使用wkhtmltopdf: {wkhtmltopdf_path}")
            return config
    except Exception as e:
        print(f"查找wkhtmltopdf失败: {e}")
    
    return pdfkit.configuration()

def fetch_with_requests(url):
    """使用requests获取网页"""
    try:
        start_time = time.time()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        load_time = time.time() - start_time
        
        return {
            "success": True,
            "content": response.text,
            "status_code": response.status_code,
            "load_time": load_time
        }
    except Exception as e:
        print(f"requests获取失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def convert_to_pdf(html_content, output_path, title):
    """转换为PDF"""
    try:
        start_time = time.time()
        
        options = {
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'no-outline': None,
            'title': title,
        }
        
        pdfkit.from_string(html_content, output_path, options=options, configuration=setup_pdfkit())
        
        conversion_time = time.time() - start_time
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        
        return {
            "success": True,
            "conversion_time": conversion_time,
            "file_size": file_size,
            "output_path": str(output_path)
        }
    except Exception as e:
        print(f"PDF转换失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def main():
    """主测试函数"""
    print("开始简单PDF转换测试")
    print("使用requests + pdfkit (wkhtmltopdf)")
    
    output_dir = Path("../../outputs/技术方案/测试结果")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    for url_info in SIMPLE_URLS:
        print(f"\n{'='*60}")
        print(f"测试: {url_info['name']} ({url_info['type']})")
        print(f"URL: {url_info['url']}")
        
        # 获取网页
        fetch_result = fetch_with_requests(url_info['url'])
        if not fetch_result['success']:
            print(f"获取失败: {fetch_result['error']}")
            continue
            
        print(f"获取成功: 状态码={fetch_result['status_code']}, 用时={fetch_result['load_time']:.2f}秒")
        
        # 转换为PDF
        safe_title = "".join(c for c in url_info['name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        pdf_output = output_dir / f"{safe_title}.pdf"
        
        pdf_result = convert_to_pdf(fetch_result['content'], pdf_output, url_info['name'])
        
        if pdf_result['success']:
            print(f"PDF转换成功: 用时{pdf_result['conversion_time']:.2f}秒, 大小{pdf_result['file_size']}字节")
            results.append({
                "url": url_info['url'],
                "fetch_success": True,
                "pdf_success": True,
                "conversion_time": pdf_result['conversion_time'],
                "file_size": pdf_result['file_size']
            })
        else:
            print(f"PDF转换失败: {pdf_result['error']}")
            results.append({
                "url": url_info['url'],
                "fetch_success": True,
                "pdf_success": False,
                "error": pdf_result['error']
            })
    
    # 总结
    print(f"\n{'='*60}")
    print("测试总结:")
    
    successful_fetches = sum(1 for r in results if r['fetch_success'])
    successful_pdfs = sum(1 for r in results if r.get('pdf_success', False))
    
    print(f"网页获取成功率: {successful_fetches}/{len(SIMPLE_URLS)} ({successful_fetches/len(SIMPLE_URLS)*100:.1f}%)")
    print(f"PDF转换成功率: {successful_pdfs}/{len(SIMPLE_URLS)} ({successful_pdfs/len(SIMPLE_URLS)*100:.1f}%)")
    
    if successful_pdfs > 0:
        avg_time = sum(r['conversion_time'] for r in results if r.get('pdf_success', False)) / successful_pdfs
        avg_size = sum(r['file_size'] for r in results if r.get('pdf_success', False)) / successful_pdfs
        print(f"平均转换时间: {avg_time:.2f}秒")
        print(f"平均文件大小: {avg_size:.0f}字节")
    
    return results

if __name__ == "__main__":
    main()