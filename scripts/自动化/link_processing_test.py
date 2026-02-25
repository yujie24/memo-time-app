#!/usr/bin/env python3
"""
链接处理技术验证脚本
测试Puppeteer（通过Playwright实现）+ HTML转PDF工具链
参考竞品分析报告中的技术选型方向建议
"""

import asyncio
import time
import os
import sys
import pdfkit
import requests
from pathlib import Path
from playwright.async_api import async_playwright
from readability import Document
from bs4 import BeautifulSoup
import json

# 测试网页URL列表（至少3个示例）
TEST_URLS = [
    {
        "url": "https://www.bbc.com/news/technology-68353330",
        "name": "BBC新闻-科技",
        "type": "新闻文章"
    },
    {
        "url": "https://medium.com/@alexdambra/five-essential-steps-for-data-science-projects-3e5d3c3a8c2a",
        "name": "Medium技术博客",
        "type": "技术文章"
    },
    {
        "url": "https://github.com/microsoft/playwright-python",
        "name": "GitHub仓库",
        "type": "代码仓库"
    }
]

# 输出目录
OUTPUT_DIR = Path("../../outputs/技术方案/测试结果")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def setup_pdfkit():
    """配置pdfkit，查找wkhtmltopdf路径"""
    try:
        # 尝试自动查找wkhtmltopdf
        import subprocess
        result = subprocess.run(['which', 'wkhtmltopdf'], capture_output=True, text=True)
        if result.returncode == 0:
            wkhtmltopdf_path = result.stdout.strip()
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            print(f"找到wkhtmltopdf: {wkhtmltopdf_path}")
            return config
    except Exception as e:
        print(f"查找wkhtmltopdf失败: {e}")
    
    # 使用默认配置
    return pdfkit.configuration()

async def fetch_with_playwright(url, timeout=30000):
    """使用Playwright获取网页内容"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print(f"正在访问: {url}")
            start_time = time.time()
            await page.goto(url, wait_until='networkidle', timeout=timeout)
            content = await page.content()
            load_time = time.time() - start_time
            
            # 获取页面标题
            title = await page.title()
            
            await browser.close()
            
            return {
                "success": True,
                "content": content,
                "title": title,
                "load_time": load_time
            }
        except Exception as e:
            print(f"Playwright获取失败: {e}")
            await browser.close()
            return {
                "success": False,
                "error": str(e)
            }

def extract_readable_content(html_content, url):
    """使用readability提取可读内容"""
    try:
        doc = Document(html_content, url=url)
        readable_html = doc.summary()
        title = doc.title()
        
        # 使用BeautifulSoup进一步清理
        soup = BeautifulSoup(readable_html, 'html.parser')
        # 移除脚本和样式标签
        for script in soup(["script", "style"]):
            script.decompose()
        
        readable_text = soup.get_text(separator='\n')
        # 清理多余的空行
        lines = [line.strip() for line in readable_text.splitlines() if line.strip()]
        cleaned_text = '\n'.join(lines)
        
        return {
            "success": True,
            "readable_html": str(soup),
            "title": title,
            "text_length": len(cleaned_text),
            "text_preview": cleaned_text[:500] + "..." if len(cleaned_text) > 500 else cleaned_text
        }
    except Exception as e:
        print(f"提取可读内容失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def convert_to_pdf_pdfkit(html_content, output_path, title):
    """使用pdfkit（wkhtmltopdf）将HTML转换为PDF"""
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
        
        # 检查文件大小
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        
        return {
            "success": True,
            "conversion_time": conversion_time,
            "file_size": file_size,
            "output_path": str(output_path)
        }
    except Exception as e:
        print(f"pdfkit转换失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def convert_to_pdf_playwright(html_content, output_path, title):
    """使用Playwright将HTML转换为PDF"""
    try:
        start_time = time.time()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # 设置HTML内容
            await page.set_content(html_content)
            
            # 生成PDF
            await page.pdf(path=output_path, format='A4')
            
            await browser.close()
        
        conversion_time = time.time() - start_time
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        
        return {
            "success": True,
            "conversion_time": conversion_time,
            "file_size": file_size,
            "output_path": str(output_path)
        }
    except Exception as e:
        print(f"Playwright PDF转换失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def evaluate_conversion_quality(original_info, pdf_info, method):
    """评估转换质量"""
    quality_score = 0
    feedback = []
    
    # 检查文件大小
    if pdf_info['file_size'] > 0:
        quality_score += 2
        feedback.append(f"{method}: PDF文件大小合理 ({pdf_info['file_size']} 字节)")
    else:
        feedback.append(f"{method}: PDF文件大小为0，可能转换失败")
    
    # 检查转换时间
    if pdf_info['conversion_time'] < 10:  # 10秒内完成
        quality_score += 2
        feedback.append(f"{method}: 转换速度快 ({pdf_info['conversion_time']:.2f} 秒)")
    elif pdf_info['conversion_time'] < 30:
        quality_score += 1
        feedback.append(f"{method}: 转换速度一般 ({pdf_info['conversion_time']:.2f} 秒)")
    else:
        feedback.append(f"{method}: 转换速度较慢 ({pdf_info['conversion_time']:.2f} 秒)")
    
    # 检查原始信息是否保留
    if original_info.get('text_length', 0) > 100:
        quality_score += 1
        feedback.append(f"{method}: 提取到有效文本内容 ({original_info['text_length']} 字符)")
    
    return {
        "quality_score": quality_score,
        "max_score": 5,
        "feedback": feedback
    }

async def test_url(url_info):
    """测试单个URL"""
    print(f"\n{'='*60}")
    print(f"测试: {url_info['name']} ({url_info['type']})")
    print(f"URL: {url_info['url']}")
    
    result = {
        "url_info": url_info,
        "playwright_fetch": None,
        "content_extraction": None,
        "pdfkit_conversion": None,
        "playwright_conversion": None,
        "evaluations": []
    }
    
    # 1. 使用Playwright获取网页
    fetch_result = await fetch_with_playwright(url_info['url'])
    result['playwright_fetch'] = fetch_result
    
    if not fetch_result['success']:
        print("网页获取失败，跳过后续测试")
        return result
    
    print(f"获取成功: 标题='{fetch_result['title']}', 加载时间={fetch_result['load_time']:.2f}秒")
    
    # 2. 提取可读内容
    extraction_result = extract_readable_content(fetch_result['content'], url_info['url'])
    result['content_extraction'] = extraction_result
    
    if extraction_result['success']:
        print(f"内容提取成功: 文本长度={extraction_result['text_length']}字符")
    else:
        print(f"内容提取失败: {extraction_result['error']}")
    
    # 3. PDF转换测试
    if extraction_result['success'] and extraction_result.get('readable_html'):
        html_content = extraction_result['readable_html']
        title = extraction_result['title'] or url_info['name']
        
        # 清理文件名中的非法字符
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        
        # 使用pdfkit转换
        pdfkit_output = OUTPUT_DIR / f"{safe_title}_pdfkit.pdf"
        pdfkit_result = convert_to_pdf_pdfkit(html_content, pdfkit_output, title)
        result['pdfkit_conversion'] = pdfkit_result
        
        if pdfkit_result['success']:
            print(f"pdfkit转换成功: 用时{pdfkit_result['conversion_time']:.2f}秒, 大小{pdfkit_result['file_size']}字节")
            
            # 评估质量
            pdfkit_eval = evaluate_conversion_quality(
                extraction_result, 
                pdfkit_result, 
                "pdfkit (wkhtmltopdf)"
            )
            result['evaluations'].append(pdfkit_eval)
            print(f"质量评估: {pdfkit_eval['quality_score']}/{pdfkit_eval['max_score']}")
        else:
            print(f"pdfkit转换失败: {pdfkit_result['error']}")
        
        # 使用Playwright转换
        playwright_output = OUTPUT_DIR / f"{safe_title}_playwright.pdf"
        playwright_pdf_result = await convert_to_pdf_playwright(html_content, playwright_output, title)
        result['playwright_conversion'] = playwright_pdf_result
        
        if playwright_pdf_result['success']:
            print(f"Playwright PDF转换成功: 用时{playwright_pdf_result['conversion_time']:.2f}秒, 大小{playwright_pdf_result['file_size']}字节")
            
            # 评估质量
            playwright_eval = evaluate_conversion_quality(
                extraction_result,
                playwright_pdf_result,
                "Playwright (Chromium)"
            )
            result['evaluations'].append(playwright_eval)
            print(f"质量评估: {playwright_eval['quality_score']}/{playwright_eval['max_score']}")
        else:
            print(f"Playwright PDF转换失败: {playwright_pdf_result['error']}")
    
    return result

async def main():
    """主测试函数"""
    print("开始链接处理技术验证")
    print(f"参考竞品分析报告中的技术选型方向建议: Puppeteer + HTML转PDF")
    print(f"测试网页数量: {len(TEST_URLS)}")
    print(f"输出目录: {OUTPUT_DIR.absolute()}")
    
    all_results = []
    
    # 测试每个URL
    for url_info in TEST_URLS:
        result = await test_url(url_info)
        all_results.append(result)
    
    # 生成测试报告
    report_path = OUTPUT_DIR.parent / "链接处理技术验证报告.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    
    # 生成摘要
    print(f"\n{'='*60}")
    print("测试摘要:")
    
    successful_fetches = sum(1 for r in all_results if r['playwright_fetch'] and r['playwright_fetch']['success'])
    successful_extractions = sum(1 for r in all_results if r['content_extraction'] and r['content_extraction']['success'])
    successful_pdfkit = sum(1 for r in all_results if r['pdfkit_conversion'] and r['pdfkit_conversion']['success'])
    successful_playwright_pdf = sum(1 for r in all_results if r['playwright_conversion'] and r['playwright_conversion']['success'])
    
    print(f"网页获取成功率: {successful_fetches}/{len(TEST_URLS)} ({successful_fetches/len(TEST_URLS)*100:.1f}%)")
    print(f"内容提取成功率: {successful_extractions}/{len(TEST_URLS)} ({successful_extractions/len(TEST_URLS)*100:.1f}%)")
    print(f"pdfkit转换成功率: {successful_pdfkit}/{len(TEST_URLS)} ({successful_pdfkit/len(TEST_URLS)*100:.1f}%)")
    print(f"Playwright PDF转换成功率: {successful_playwright_pdf}/{len(TEST_URLS)} ({successful_playwright_pdf/len(TEST_URLS)*100:.1f}%)")
    
    # 计算平均转换时间
    pdfkit_times = [r['pdfkit_conversion']['conversion_time'] for r in all_results if r['pdfkit_conversion'] and r['pdfkit_conversion']['success']]
    playwright_times = [r['playwright_conversion']['conversion_time'] for r in all_results if r['playwright_conversion'] and r['playwright_conversion']['success']]
    
    if pdfkit_times:
        print(f"pdfkit平均转换时间: {sum(pdfkit_times)/len(pdfkit_times):.2f}秒")
    if playwright_times:
        print(f"Playwright PDF平均转换时间: {sum(playwright_times)/len(playwright_times):.2f}秒")
    
    print(f"\n详细报告已保存到: {report_path}")
    
    return all_results

if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())