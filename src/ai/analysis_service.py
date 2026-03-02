"""
AI分析服务
整合数据收集和AI分析功能，提供完整的个人生产力分析服务
"""

import json
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import os
import sys

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from ai.data_collector import DataCollector
from ai.deepseek_client import DeepSeekClient

class AnalysisService:
    """AI分析服务"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化分析服务
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        
        # 初始化组件
        self.data_collector = DataCollector(self.config.get("data_collector", {}))
        self.ai_client = DeepSeekClient(api_key=self.config.get("api_key"))
        
        # 缓存设置
        self.cache_enabled = self.config.get("cache_enabled", True)
        self.cache_duration = self.config.get("cache_duration", 3600)  # 1小时
        self.analysis_cache = {}
        
        # 性能统计
        self.analysis_count = 0
        self.total_analysis_time = 0
        
    def analyze_recent_activity(self, 
                               days: int = 7,
                               force_refresh: bool = False) -> Dict[str, Any]:
        """
        分析最近活动
        
        Args:
            days: 分析的天数
            force_refresh: 是否强制刷新缓存
            
        Returns:
            完整分析结果
        """
        start_time = time.time()
        self.analysis_count += 1
        
        # 检查缓存
        cache_key = f"recent_{days}d"
        if self.cache_enabled and not force_refresh:
            cached_result = self._get_cached_analysis(cache_key)
            if cached_result:
                print(f"使用缓存的分析结果（{cache_key}）")
                return cached_result
        
        try:
            print(f"开始分析最近{days}天活动...")
            
            # 1. 收集数据
            print("收集各模块数据...")
            data_summary = self.data_collector.collect_recent_data(days=days)
            
            # 2. 构建分析请求
            print("准备AI分析请求...")
            link_summary = data_summary["data"].get("links")
            financial_summary = data_summary["data"].get("financial")
            calendar_summary = data_summary["data"].get("calendar")
            health_summary = data_summary["data"].get("health")
            
            # 3. 调用AI分析
            print("调用DeepSeek API进行分析...")
            ai_result = self.ai_client.analyze_recent_data(
                link_summary=link_summary,
                financial_summary=financial_summary,
                calendar_summary=calendar_summary,
                health_summary=health_summary,
                user_preferences=self.config.get("user_preferences")
            )
            
            # 4. 构建完整结果
            analysis_result = {
                "analysis_id": f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{int(time.time() % 1000)}",
                "timestamp": int(time.time()),
                "time_range": {
                    "days": days,
                    "start_timestamp": data_summary["time_range"]["start_time"],
                    "end_timestamp": data_summary["time_range"]["end_time"]
                },
                "data_availability": data_summary["modules_available"],
                "data_summary": {
                    "links": link_summary,
                    "financial": financial_summary,
                    "calendar": calendar_summary,
                    "health": health_summary
                },
                "ai_analysis": ai_result,
                "performance": {
                    "data_collection_time": round(time.time() - start_time, 3),
                    "total_records": self._calculate_total_records(data_summary)
                }
            }
            
            # 5. 更新缓存
            if self.cache_enabled:
                self._cache_analysis(cache_key, analysis_result)
            
            # 6. 更新统计
            analysis_duration = time.time() - start_time
            self.total_analysis_time += analysis_duration
            analysis_result["performance"]["total_analysis_time"] = round(analysis_duration, 3)
            
            print(f"分析完成，用时{analysis_duration:.2f}秒")
            
            return analysis_result
            
        except Exception as e:
            error_result = self._create_error_result(
                error=e,
                days=days,
                start_time=start_time
            )
            
            return error_result
    
    def _calculate_total_records(self, data_summary: Dict[str, Any]) -> int:
        """计算总记录数"""
        total = 0
        
        for module_name, module_data in data_summary["data"].items():
            if module_name == "financial":
                total += module_data.get("record_count", 0)
            elif module_name == "links":
                total += module_data.get("total_count", 0)
            elif module_name == "calendar":
                total += module_data.get("total_events", 0)
            elif module_name == "health":
                # 健康数据通常按天数计算
                total += 1
        
        return total
    
    def _get_cached_analysis(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存的分析结果"""
        if cache_key in self.analysis_cache:
            cached_item = self.analysis_cache[cache_key]
            cache_age = time.time() - cached_item["timestamp"]
            
            if cache_age < self.cache_duration:
                return cached_item["result"]
            else:
                # 缓存过期，删除
                del self.analysis_cache[cache_key]
        
        return None
    
    def _cache_analysis(self, cache_key: str, result: Dict[str, Any]):
        """缓存分析结果"""
        self.analysis_cache[cache_key] = {
            "timestamp": time.time(),
            "result": result
        }
        
        # 清理过期缓存（如果缓存太多）
        if len(self.analysis_cache) > 10:
            self._clean_expired_cache()
    
    def _clean_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []
        
        for key, item in self.analysis_cache.items():
            cache_age = current_time - item["timestamp"]
            if cache_age > self.cache_duration:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.analysis_cache[key]
    
    def _create_error_result(self, 
                            error: Exception,
                            days: int,
                            start_time: float) -> Dict[str, Any]:
        """创建错误结果"""
        error_result = {
            "analysis_id": f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{int(time.time() % 1000)}",
            "timestamp": int(time.time()),
            "time_range": {
                "days": days,
                "start_timestamp": int(time.time() - (days * 86400)),
                "end_timestamp": int(time.time())
            },
            "data_availability": {
                "financial": False,
                "links": False,
                "calendar": False,
                "health": False
            },
            "data_summary": {},
            "ai_analysis": {
                "response_id": f"error_resp_{int(time.time())}",
                "request_id": f"error_req_{int(time.time())}",
                "analysis_results": {
                    "insights": [],
                    "recommendations": [],
                    "raw_analysis": f"分析过程中发生错误: {str(error)}"
                },
                "performance_metrics": {
                    "response_time": round(time.time() - start_time, 3),
                    "success": False,
                    "error": str(error)
                }
            },
            "performance": {
                "data_collection_time": round(time.time() - start_time, 3),
                "total_records": 0,
                "total_analysis_time": round(time.time() - start_time, 3)
            }
        }
        
        return error_result
    
    def get_detailed_insights(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """获取详细洞察"""
        ai_analysis = analysis_result.get("ai_analysis", {})
        analysis_results = ai_analysis.get("analysis_results", {})
        
        insights = {
            "summary": analysis_results.get("raw_analysis", "无分析结果"),
            "structured_insights": analysis_results.get("insights", []),
            "recommendations": analysis_results.get("recommendations", []),
            "data_context": {
                "modules_available": analysis_result.get("data_availability", {}),
                "record_counts": self._extract_record_counts(analysis_result)
            }
        }
        
        return insights
    
    def _extract_record_counts(self, analysis_result: Dict[str, Any]) -> Dict[str, int]:
        """提取各模块记录数"""
        counts = {}
        data_summary = analysis_result.get("data_summary", {})
        
        for module_name, module_data in data_summary.items():
            if module_name == "financial":
                counts[module_name] = module_data.get("record_count", 0)
            elif module_name == "links":
                counts[module_name] = module_data.get("total_count", 0)
            elif module_name == "calendar":
                counts[module_name] = module_data.get("total_events", 0)
            elif module_name == "health":
                # 健康数据通常存在时返回1
                counts[module_name] = 1 if module_data else 0
        
        return counts
    
    def generate_analysis_report(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """生成分析报告"""
        insights = self.get_detailed_insights(analysis_result)
        ai_analysis = analysis_result.get("ai_analysis", {})
        
        report = {
            "report_id": f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now().isoformat(),
            "analysis_period": f"{analysis_result['time_range']['days']}天",
            "key_insights": [
                insight["content"] 
                for insight in insights["structured_insights"][:3]
            ],
            "top_recommendations": [
                rec["description"]
                for rec in insights["recommendations"][:3]
            ],
            "data_quality": {
                "modules_available": sum(1 for v in analysis_result["data_availability"].values() if v),
                "total_modules": len(analysis_result["data_availability"])
            },
            "performance_summary": analysis_result.get("performance", {}),
            "ai_analysis_metadata": {
                "success": ai_analysis.get("performance_metrics", {}).get("success", False),
                "response_time": ai_analysis.get("performance_metrics", {}).get("response_time", 0),
                "model_used": ai_analysis.get("performance_metrics", {}).get("model_used", "unknown")
            }
        }
        
        return report
    
    def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计"""
        ai_stats = self.ai_client.get_performance_stats()
        data_report = self.data_collector.get_data_availability_report()
        
        avg_analysis_time = 0
        if self.analysis_count > 0:
            avg_analysis_time = self.total_analysis_time / self.analysis_count
        
        return {
            "analysis_count": self.analysis_count,
            "average_analysis_time": round(avg_analysis_time, 3),
            "total_analysis_time": round(self.total_analysis_time, 3),
            "ai_client_stats": ai_stats,
            "data_availability": data_report,
            "cache_status": {
                "enabled": self.cache_enabled,
                "cache_size": len(self.analysis_cache),
                "cache_duration": self.cache_duration
            }
        }
    
    def clear_cache(self):
        """清除缓存"""
        self.analysis_cache.clear()
        print("分析缓存已清除")


# 测试函数
def test_analysis_service():
    """测试分析服务"""
    print("测试分析服务...")
    
    try:
        # 配置服务
        config = {
            "cache_enabled": True,
            "cache_duration": 1800,  # 30分钟
            "user_preferences": {
                "analysis_depth": "standard",
                "report_format": "detailed",
                "language": "zh-CN"
            }
        }
        
        service = AnalysisService(config)
        
        # 测试分析最近7天活动
        print("分析最近7天活动...")
        analysis_result = service.analyze_recent_activity(days=7)
        
        print(f"分析ID: {analysis_result['analysis_id']}")
        print(f"时间范围: {analysis_result['time_range']['days']}天")
        print(f"数据可用性: {analysis_result['data_availability']}")
        
        # 获取详细洞察
        print("\n获取详细洞察...")
        insights = service.get_detailed_insights(analysis_result)
        
        print(f"分析摘要: {insights['summary'][:200]}...")
        print(f"结构化洞察数: {len(insights['structured_insights'])}")
        print(f"建议数: {len(insights['recommendations'])}")
        
        # 生成报告
        print("\n生成分析报告...")
        report = service.generate_analysis_report(analysis_result)
        
        print(f"报告ID: {report['report_id']}")
        print(f"关键洞察:")
        for i, insight in enumerate(report['key_insights'][:2], 1):
            print(f"  {i}. {insight[:100]}...")
        
        print(f"Top建议:")
        for i, rec in enumerate(report['top_recommendations'][:2], 1):
            print(f"  {i}. {rec[:100]}...")
        
        # 获取服务统计
        print("\n获取服务统计...")
        stats = service.get_service_stats()
        
        print(f"分析次数: {stats['analysis_count']}")
        print(f"平均分析时间: {stats['average_analysis_time']:.3f}秒")
        print(f"AI客户端成功率: {stats['ai_client_stats']['success_rate']}%")
        
        # 测试缓存功能
        print("\n测试缓存功能...")
        print("第一次分析（将缓存）...")
        result1 = service.analyze_recent_activity(days=3)
        
        print("第二次分析（应使用缓存）...")
        result2 = service.analyze_recent_activity(days=3)
        
        if result1['analysis_id'] == result2['analysis_id']:
            print("✓ 缓存功能正常")
        else:
            print("✗ 缓存功能可能有问题")
        
        # 清除缓存
        service.clear_cache()
        
        print("\n分析服务测试完成")
        return True
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 运行测试
    if test_analysis_service():
        print("分析服务测试通过")
    else:
        print("分析服务测试失败")