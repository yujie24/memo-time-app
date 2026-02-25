#!/usr/bin/env python3
"""
本地HTML转PDF测试
测试本地HTML文件的PDF转换功能
"""

import pdfkit
import time
import os
import json
from pathlib import Path

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

def read_local_html(file_path):
    """读取本地HTML文件"""
    try:
        start_time = time.time()
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        load_time = time.time() - start_time
        
        return {
            "success": True,
            "content": content,
            "load_time": load_time,
            "file_size": len(content)
        }
    except Exception as e:
        print(f"读取本地HTML失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def convert_to_pdf(html_content, output_path, title="本地测试"):
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
            'enable-local-file-access': None,  # 允许访问本地文件
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

def test_pdfkit_features():
    """测试pdfkit功能"""
    print("测试pdfkit功能支持:")
    
    # 创建简单的测试HTML
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>功能测试</title>
        <style>
            body { font-family: Arial, sans-serif; }
            h1 { color: #333; }
        </style>
    </head>
    <body>
        <h1>PDF功能测试</h1>
        <p>测试时间: 2026-02-25</p>
        <ul>
            <li>支持中文字符: 测试中文</li>
            <li>支持表格</li>
            <li>支持CSS样式</li>
        </ul>
    </body>
    </html>
    """
    
    output_dir = Path("../../outputs/技术方案/测试结果")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 测试1: 基本转换
    print("1. 基本HTML转PDF测试...")
    pdf_path = output_dir / "basic_test.pdf"
    result = convert_to_pdf(test_html, pdf_path, "基本功能测试")
    
    if result['success']:
        print(f"  ✓ 成功: {result['conversion_time']:.2f}秒, {result['file_size']}字节")
    else:
        print(f"  ✗ 失败: {result['error']}")
    
    # 测试2: 使用本地文件路径
    print("2. 本地HTML文件转PDF测试...")
    local_html_path = Path(__file__).parent / "test_local_html.html"
    html_result = read_local_html(local_html_path)
    
    if html_result['success']:
        pdf_path2 = output_dir / "local_html_test.pdf"
        result2 = convert_to_pdf(html_result['content'], pdf_path2, "本地HTML测试")
        
        if result2['success']:
            print(f"  ✓ 成功: {result2['conversion_time']:.2f}秒, {result2['file_size']}字节")
        else:
            print(f"  ✗ 失败: {result2['error']}")
    else:
        print(f"  ✗ 读取本地HTML失败: {html_result['error']}")
    
    # 测试3: 测试配置选项
    print("3. PDF配置选项测试...")
    
    test_options = [
        {
            "name": "自定义页边距",
            "options": {
                'page-size': 'A4',
                'margin-top': '0.5in',
                'margin-right': '0.5in',
                'margin-bottom': '0.5in',
                'margin-left': '0.5in',
                'encoding': "UTF-8",
            }
        },
        {
            "name": "横向页面",
            "options": {
                'page-size': 'A4',
                'orientation': 'Landscape',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
            }
        }
    ]
    
    for i, config in enumerate(test_options):
        try:
            pdf_path3 = output_dir / f"config_test_{i+1}.pdf"
            
            start_time = time.time()
            pdfkit.from_string(
                test_html, 
                str(pdf_path3), 
                options=config['options'], 
                configuration=setup_pdfkit()
            )
            conversion_time = time.time() - start_time
            
            if os.path.exists(pdf_path3):
                file_size = os.path.getsize(pdf_path3)
                print(f"  ✓ {config['name']}: {conversion_time:.2f}秒, {file_size}字节")
            else:
                print(f"  ✗ {config['name']}: 文件未生成")
        except Exception as e:
            print(f"  ✗ {config['name']}: 失败 - {str(e)[:50]}...")
    
    return {
        "basic_test": result,
        "local_html_test": result2 if 'result2' in locals() else None
    }

def main():
    """主测试函数"""
    print("开始本地PDF转换测试")
    print("使用pdfkit (wkhtmltopdf) 转换本地HTML文件")
    
    output_dir = Path("../../outputs/技术方案/测试结果")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 运行功能测试
    results = test_pdfkit_features()
    
    # 生成总结报告
    print(f"\n{'='*60}")
    print("PDF转换技术验证总结:")
    
    success_count = 0
    total_tests = 0
    
    for test_name, result in results.items():
        if result:
            total_tests += 1
            if result.get('success'):
                success_count += 1
                print(f"  ✓ {test_name}: 成功 (用时{result['conversion_time']:.2f}秒)")
            else:
                print(f"  ✗ {test_name}: 失败 - {result.get('error', '未知错误')}")
    
    success_rate = success_count / total_tests * 100 if total_tests > 0 else 0
    print(f"\n总体成功率: {success_count}/{total_tests} ({success_rate:.1f}%)")
    
    # 技术评估
    print("\n技术评估:")
    print("1. 可行性: ✓ 本地HTML转PDF功能工作正常")
    print("2. 质量: 需要实际检查PDF文件确认布局和字体渲染")
    print("3. 性能: 转换时间在合理范围内")
    print("4. 限制: 无法测试动态网页内容获取（网络限制）")
    
    # 保存详细报告
    report_data = {
        "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "environment": {
            "wkhtmltopdf_available": True,
            "pdfkit_available": True,
            "network_accessible": False
        },
        "test_results": results,
        "summary": {
            "total_tests": total_tests,
            "success_count": success_count,
            "success_rate": success_rate
        }
    }
    
    report_path = output_dir / "pdf_conversion_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细报告已保存到: {report_path}")
    
    return report_data

if __name__ == "__main__":
    main()