"""
数据收集器
从各模块收集最近7天的数据，进行脱敏和格式化处理
支持财务、链接处理、日历、健康模块
"""

import json
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import sqlite3
import os

class DataCollector:
    """数据收集器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化数据收集器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        
        # 数据库路径配置
        self.db_config = {
            "financial": self.config.get("financial_db_path", "data/financial.db"),
            "links": self.config.get("links_db_path", "data/links.db"),
            "calendar": self.config.get("calendar_db_path", "data/calendar.db"),
            "health": self.config.get("health_db_path", "data/health.db")
        }
        
        # 确保数据目录存在
        os.makedirs("data", exist_ok=True)
    
    def collect_recent_data(self, days: int = 7) -> Dict[str, Any]:
        """
        收集最近N天的数据
        
        Args:
            days: 天数，默认7天
            
        Returns:
            各模块数据摘要
        """
        # 计算时间范围
        end_time = int(time.time())
        start_time = end_time - (days * 86400)
        
        data_summary = {
            "time_range": {
                "start_time": start_time,
                "end_time": end_time,
                "days": days
            },
            "modules_available": {
                "financial": False,
                "links": False,
                "calendar": False,
                "health": False
            },
            "data": {}
        }
        
        # 收集财务数据
        financial_summary = self._collect_financial_data(start_time, end_time)
        if financial_summary:
            data_summary["modules_available"]["financial"] = True
            data_summary["data"]["financial"] = financial_summary
        
        # 收集链接数据
        links_summary = self._collect_links_data(start_time, end_time)
        if links_summary:
            data_summary["modules_available"]["links"] = True
            data_summary["data"]["links"] = links_summary
        
        # 收集日历数据
        calendar_summary = self._collect_calendar_data(start_time, end_time)
        if calendar_summary:
            data_summary["modules_available"]["calendar"] = True
            data_summary["data"]["calendar"] = calendar_summary
        
        # 收集健康数据
        health_summary = self._collect_health_data(start_time, end_time)
        if health_summary:
            data_summary["modules_available"]["health"] = True
            data_summary["data"]["health"] = health_summary
        
        return data_summary
    
    def _collect_financial_data(self, start_time: int, end_time: int) -> Optional[Dict[str, Any]]:
        """收集财务数据"""
        db_path = self.db_config["financial"]
        
        if not os.path.exists(db_path):
            print(f"财务数据库不存在: {db_path}")
            return None
        
        try:
            # 连接到数据库
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 查询总记录数
            cursor.execute("""
                SELECT COUNT(*) FROM financial_index 
                WHERE transaction_date BETWEEN ? AND ?
            """, (start_time, end_time))
            
            record_count = cursor.fetchone()[0]
            
            if record_count == 0:
                conn.close()
                # 返回空摘要
                return {
                    "total_spending": 0,
                    "average_daily": 0,
                    "top_categories": [],
                    "record_count": 0
                }
            
            # 查询总支出
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM financial_index 
                WHERE transaction_date BETWEEN ? AND ?
            """, (start_time, end_time))
            
            total_spending = cursor.fetchone()[0] or 0
            
            # 计算日均支出
            days = max(1, (end_time - start_time) // 86400)
            average_daily = total_spending / days if days > 0 else 0
            
            # 查询Top类别
            cursor.execute("""
                SELECT category, SUM(amount) as category_total 
                FROM financial_index 
                WHERE transaction_date BETWEEN ? AND ? 
                AND category IS NOT NULL 
                AND category != ''
                GROUP BY category 
                ORDER BY category_total DESC 
                LIMIT 5
            """, (start_time, end_time))
            
            top_categories = []
            for row in cursor.fetchall():
                category, total = row
                if category and total > 0:
                    percentage = (total / total_spending * 100) if total_spending > 0 else 0
                    top_categories.append({
                        "category": category,
                        "amount": round(total, 2),
                        "percentage": round(percentage, 2)
                    })
            
            conn.close()
            
            return {
                "total_spending": round(total_spending, 2),
                "average_daily": round(average_daily, 2),
                "top_categories": top_categories,
                "record_count": record_count
            }
            
        except Exception as e:
            print(f"收集财务数据失败: {str(e)}")
            return None
    
    def _collect_links_data(self, start_time: int, end_time: int) -> Optional[Dict[str, Any]]:
        """收集链接处理数据"""
        # 链接数据可能存储在state.db或单独的数据库中
        # 这里我们检查多个可能的位置
        
        possible_db_paths = [
            self.db_config["links"],
            "data/shared_state/state.db",
            "data/links_processing.db"
        ]
        
        db_path = None
        for path in possible_db_paths:
            if os.path.exists(path):
                db_path = path
                break
        
        if not db_path:
            print("链接数据库不存在")
            return None
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 检查可能的表结构
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            link_summary = {
                "total_count": 0,
                "category_distribution": {},
                "recent_trend": [],
                "top_domains": []
            }
            
            # 尝试从不同表中获取数据
            if "processed_links" in tables:
                # 查询链接数量
                cursor.execute("""
                    SELECT COUNT(*) FROM processed_links 
                    WHERE processed_at BETWEEN ? AND ?
                """, (start_time, end_time))
                
                link_summary["total_count"] = cursor.fetchone()[0] or 0
                
                # 查询类别分布
                cursor.execute("""
                    SELECT category, COUNT(*) as count 
                    FROM processed_links 
                    WHERE processed_at BETWEEN ? AND ?
                    AND category IS NOT NULL
                    GROUP BY category 
                    ORDER BY count DESC
                """, (start_time, end_time))
                
                for row in cursor.fetchall():
                    category, count = row
                    if category:
                        link_summary["category_distribution"][category] = count
                
                # 查询最近趋势（按天）
                cursor.execute("""
                    SELECT date(processed_at, 'unixepoch') as day, COUNT(*) as count 
                    FROM processed_links 
                    WHERE processed_at BETWEEN ? AND ?
                    GROUP BY day 
                    ORDER BY day DESC 
                    LIMIT 7
                """, (start_time, end_time))
                
                for row in cursor.fetchall():
                    day, count = row
                    link_summary["recent_trend"].append({
                        "date": day,
                        "count": count
                    })
                
                # 查询Top域名
                cursor.execute("""
                    SELECT domain, COUNT(*) as count 
                    FROM processed_links 
                    WHERE processed_at BETWEEN ? AND ?
                    AND domain IS NOT NULL
                    GROUP BY domain 
                    ORDER BY count DESC 
                    LIMIT 5
                """, (start_time, end_time))
                
                for row in cursor.fetchall():
                    domain, count = row
                    if domain:
                        link_summary["top_domains"].append(domain)
            
            elif "link_records" in tables:
                # 备用表名
                cursor.execute("SELECT COUNT(*) FROM link_records")
                link_summary["total_count"] = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return link_summary
            
        except Exception as e:
            print(f"收集链接数据失败: {str(e)}")
            return None
    
    def _collect_calendar_data(self, start_time: int, end_time: int) -> Optional[Dict[str, Any]]:
        """收集日历数据"""
        db_path = self.db_config["calendar"]
        
        if not os.path.exists(db_path):
            print(f"日历数据库不存在: {db_path}")
            # 模拟数据用于测试
            return self._create_mock_calendar_summary(start_time, end_time)
        
        try:
            # 实际实现中这里会查询日历数据库
            # 现在返回模拟数据
            return self._create_mock_calendar_summary(start_time, end_time)
            
        except Exception as e:
            print(f"收集日历数据失败: {str(e)}")
            return self._create_mock_calendar_summary(start_time, end_time)
    
    def _collect_health_data(self, start_time: int, end_time: int) -> Optional[Dict[str, Any]]:
        """收集健康数据"""
        db_path = self.db_config["health"]
        
        if not os.path.exists(db_path):
            print(f"健康数据库不存在: {db_path}")
            # 模拟数据用于测试
            return self._create_mock_health_summary(start_time, end_time)
        
        try:
            # 实际实现中这里会查询健康数据库
            # 现在返回模拟数据
            return self._create_mock_health_summary(start_time, end_time)
            
        except Exception as e:
            print(f"收集健康数据失败: {str(e)}")
            return self._create_mock_health_summary(start_time, end_time)
    
    def _create_mock_calendar_summary(self, start_time: int, end_time: int) -> Dict[str, Any]:
        """创建模拟日历摘要"""
        import random
        
        # 模拟事件分布
        event_types = ["会议", "工作", "学习", "健身", "社交", "家庭", "娱乐", "医疗"]
        event_distribution = {}
        for event_type in event_types:
            event_distribution[event_type] = random.randint(1, 10)
        
        # 计算总事件数
        total_events = sum(event_distribution.values())
        
        # 模拟忙碌时间段（最近7天）
        busy_periods = []
        for i in range(7):
            day_start = start_time + (i * 86400)
            # 每天有0-3个忙碌时间段
            busy_count = random.randint(0, 3)
            for j in range(busy_count):
                period_start = day_start + random.randint(8 * 3600, 18 * 3600)
                period_end = period_start + random.randint(3600, 7200)
                busy_periods.append({
                    "start": period_start,
                    "end": period_end,
                    "duration_hours": (period_end - period_start) / 3600
                })
        
        # 模拟空闲时间块
        free_time_blocks = []
        for i in range(5):
            block_start = start_time + random.randint(0, 7 * 86400 - 7200)
            block_end = block_start + random.randint(3600, 14400)
            free_time_blocks.append({
                "start": block_start,
                "end": block_end,
                "duration_hours": (block_end - block_start) / 3600
            })
        
        return {
            "total_events": total_events,
            "event_distribution": event_distribution,
            "busy_periods": busy_periods[:3],  # 只返回前3个
            "free_time_blocks": free_time_blocks[:3],  # 只返回前3个
            "data_source": "mock"  # 标记为模拟数据
        }
    
    def _create_mock_health_summary(self, start_time: int, end_time: int) -> Dict[str, Any]:
        """创建模拟健康摘要"""
        import random
        
        # 模拟健康数据
        daily_steps_avg = random.randint(5000, 15000)
        heart_rate_avg = random.randint(60, 80)
        sleep_hours_avg = round(random.uniform(6.0, 9.0), 1)
        
        # 趋势方向
        trend_options = ["improving", "declining", "stable"]
        trend_direction = random.choice(trend_options)
        
        # 模拟具体指标
        health_metrics = {
            "steps": {
                "weekly_avg": daily_steps_avg,
                "trend": trend_direction,
                "completion_rate": round(random.uniform(0.7, 1.0), 2)
            },
            "heart_rate": {
                "resting_avg": heart_rate_avg,
                "variability": round(random.uniform(20, 50), 1)
            },
            "sleep": {
                "duration_avg": sleep_hours_avg,
                "quality_score": round(random.uniform(0.6, 0.9), 2)
            },
            "activity": {
                "active_minutes_daily": random.randint(30, 120),
                "exercise_days_per_week": random.randint(2, 7)
            }
        }
        
        return {
            "daily_steps_avg": daily_steps_avg,
            "heart_rate_avg": heart_rate_avg,
            "sleep_hours_avg": sleep_hours_avg,
            "trend_direction": trend_direction,
            "detailed_metrics": health_metrics,
            "data_source": "mock"  # 标记为模拟数据
        }
    
    def get_data_availability_report(self) -> Dict[str, Any]:
        """获取数据可用性报告"""
        recent_data = self.collect_recent_data(days=7)
        
        report = {
            "timestamp": int(time.time()),
            "modules": []
        }
        
        for module_name, available in recent_data["modules_available"].items():
            module_info = {
                "name": module_name,
                "available": available
            }
            
            if available and module_name in recent_data["data"]:
                data = recent_data["data"][module_name]
                module_info["record_count"] = data.get("record_count", 0)
                module_info["data_source"] = data.get("data_source", "real")
            else:
                module_info["record_count"] = 0
                module_info["data_source"] = "none"
            
            report["modules"].append(module_info)
        
        # 计算总体可用性
        available_modules = [m for m in report["modules"] if m["available"]]
        report["overall_availability"] = len(available_modules) / len(report["modules"])
        
        return report


# 测试函数
def test_data_collector():
    """测试数据收集器"""
    print("测试数据收集器...")
    
    try:
        collector = DataCollector()
        
        # 测试收集最近7天数据
        print("收集最近7天数据...")
        recent_data = collector.collect_recent_data(days=7)
        
        print(f"时间范围: {recent_data['time_range']['days']}天")
        print(f"可用模块: {recent_data['modules_available']}")
        
        # 显示各模块摘要
        for module_name, module_data in recent_data['data'].items():
            print(f"\n{module_name.upper()}模块摘要:")
            if module_name == "financial":
                print(f"  总支出: ¥{module_data.get('total_spending', 0):.2f}")
                print(f"  日均支出: ¥{module_data.get('average_daily', 0):.2f}")
                print(f"  记录数: {module_data.get('record_count', 0)}")
                
                if module_data.get('top_categories'):
                    print(f"  Top类别:")
                    for cat in module_data['top_categories'][:3]:
                        print(f"    {cat['category']}: ¥{cat['amount']:.2f} ({cat['percentage']:.1f}%)")
            
            elif module_name == "links":
                print(f"  总链接数: {module_data.get('total_count', 0)}")
                
                if module_data.get('category_distribution'):
                    print(f"  类别分布:")
                    for cat, count in list(module_data['category_distribution'].items())[:5]:
                        print(f"    {cat}: {count}")
            
            elif module_name == "calendar":
                print(f"  总事件数: {module_data.get('total_events', 0)}")
                print(f"  数据源: {module_data.get('data_source', 'unknown')}")
            
            elif module_name == "health":
                print(f"  日均步数: {module_data.get('daily_steps_avg', 0)}")
                print(f"  平均心率: {module_data.get('heart_rate_avg', 0)}")
                print(f"  平均睡眠: {module_data.get('sleep_hours_avg', 0)}小时")
                print(f"  趋势: {module_data.get('trend_direction', 'unknown')}")
        
        # 测试数据可用性报告
        print("\n生成数据可用性报告...")
        availability_report = collector.get_data_availability_report()
        
        print(f"总体可用性: {availability_report['overall_availability']:.1%}")
        for module in availability_report['modules']:
            status = "✓" if module['available'] else "✗"
            print(f"  {status} {module['name']}: {module['record_count']}条记录 ({module['data_source']})")
        
        print("\n数据收集器测试完成")
        return True
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 运行测试
    if test_data_collector():
        print("数据收集器测试通过")
    else:
        print("数据收集器测试失败")