"""
DeepSeek API客户端
实现与DeepSeek Chat Completion API的交互
参考技术验证报告中的API设计
"""

import os
import json
import time
from typing import Dict, List, Any, Optional, Union
import requests
from datetime import datetime, timedelta

class DeepSeekClient:
    """DeepSeek API客户端"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.deepseek.com"):
        """
        初始化DeepSeek客户端
        
        Args:
            api_key: DeepSeek API密钥，如果为None则从环境变量读取
            base_url: API基础URL
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DeepSeek API密钥未提供，请设置DEEPSEEK_API_KEY环境变量")
        
        self.base_url = base_url
        self.api_endpoint = f"{base_url}/chat/completions"
        
        # 请求头
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 默认模型
        self.default_model = "deepseek-chat"
        
        # 请求超时设置
        self.timeout = 30
        
        # 性能统计
        self.request_count = 0
        self.success_count = 0
        self.total_response_time = 0
        
    def analyze_recent_data(self, 
                           link_summary: Optional[Dict[str, Any]] = None,
                           financial_summary: Optional[Dict[str, Any]] = None,
                           calendar_summary: Optional[Dict[str, Any]] = None,
                           health_summary: Optional[Dict[str, Any]] = None,
                           user_preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        分析最近数据
        
        Args:
            link_summary: 链接分类摘要
            financial_summary: 财务数据摘要
            calendar_summary: 日历事件摘要
            health_summary: 健康数据摘要
            user_preferences: 用户偏好设置
            
        Returns:
            分析结果字典
        """
        # 构建分析请求
        analysis_request = self._build_analysis_request(
            link_summary=link_summary,
            financial_summary=financial_summary,
            calendar_summary=calendar_summary,
            health_summary=health_summary,
            user_preferences=user_preferences
        )
        
        # 调用API
        return self._call_analysis_api(analysis_request)
    
    def _build_analysis_request(self,
                               link_summary: Optional[Dict[str, Any]] = None,
                               financial_summary: Optional[Dict[str, Any]] = None,
                               calendar_summary: Optional[Dict[str, Any]] = None,
                               health_summary: Optional[Dict[str, Any]] = None,
                               user_preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        构建分析请求数据
        
        参考技术验证报告中的请求格式设计
        """
        request_data = {
            "request_id": f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{int(time.time() % 1000)}",
            "timestamp": int(time.time()),
            "data_context": {
                "time_range": "recent_7_days",
                "data_scope": {
                    "links": link_summary is not None,
                    "financial": financial_summary is not None,
                    "calendar": calendar_summary is not None,
                    "health": health_summary is not None
                }
            }
        }
        
        # 添加数据摘要
        if link_summary:
            request_data["link_summary"] = self._anonymize_link_data(link_summary)
        
        if financial_summary:
            request_data["financial_summary"] = self._anonymize_financial_data(financial_summary)
        
        if calendar_summary:
            request_data["calendar_summary"] = self._anonymize_calendar_data(calendar_summary)
        
        if health_summary:
            request_data["health_summary"] = self._anonymize_health_data(health_summary)
        
        # 添加用户偏好
        if user_preferences:
            request_data["user_preferences"] = user_preferences
        else:
            request_data["user_preferences"] = {
                "analysis_depth": "standard",
                "report_format": "bullet_points",
                "language": "zh-CN"
            }
        
        return request_data
    
    def _anonymize_link_data(self, link_data: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏链接数据"""
        anonymized = {
            "total_count": link_data.get("total_count", 0),
            "category_distribution": link_data.get("category_distribution", {}),
            "recent_trend": link_data.get("recent_trend", []),
            "top_domains": link_data.get("top_domains", [])
        }
        
        # 确保域名信息已泛化（不包含完整URL）
        if "top_domains" in anonymized:
            anonymized["top_domains"] = [
                domain.split("//")[-1].split("/")[0] if "://" in domain else domain.split("/")[0]
                for domain in anonymized["top_domains"][:5]  # 只保留前5个
            ]
        
        return anonymized
    
    def _anonymize_financial_data(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏财务数据"""
        anonymized = {
            "total_spending": round(financial_data.get("total_spending", 0), 2),
            "average_daily": round(financial_data.get("average_daily", 0), 2),
            "top_categories": financial_data.get("top_categories", []),
            "record_count": financial_data.get("record_count", 0)
        }
        
        # 金额取整处理，保护隐私
        if anonymized["total_spending"] > 0:
            # 金额取整到百位数
            anonymized["total_spending"] = round(anonymized["total_spending"] / 100) * 100
        
        if anonymized["average_daily"] > 0:
            anonymized["average_daily"] = round(anonymized["average_daily"] / 10) * 10
        
        return anonymized
    
    def _anonymize_calendar_data(self, calendar_data: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏日历数据"""
        anonymized = {
            "total_events": calendar_data.get("total_events", 0),
            "event_distribution": calendar_data.get("event_distribution", {}),
            "busy_periods": calendar_data.get("busy_periods", []),
            "free_time_blocks": calendar_data.get("free_time_blocks", [])
        }
        
        # 移除具体事件标题等敏感信息
        if "event_titles" in anonymized:
            del anonymized["event_titles"]
        
        return anonymized
    
    def _anonymize_health_data(self, health_data: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏健康数据"""
        anonymized = {
            "daily_steps_avg": round(health_data.get("daily_steps_avg", 0)),
            "heart_rate_avg": round(health_data.get("heart_rate_avg", 0)),
            "sleep_hours_avg": round(health_data.get("sleep_hours_avg", 1), 1),
            "trend_direction": health_data.get("trend_direction", "stable")
        }
        
        # 健康数据精度处理
        if anonymized["daily_steps_avg"] > 0:
            anonymized["daily_steps_avg"] = round(anonymized["daily_steps_avg"] / 100) * 100
        
        if anonymized["heart_rate_avg"] > 0:
            anonymized["heart_rate_avg"] = round(anonymized["heart_rate_avg"] / 5) * 5
        
        return anonymized
    
    def _call_analysis_api(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用DeepSeek分析API
        
        Returns:
            分析结果
        """
        # 构建提示词
        system_prompt = """你是一个个人生产力分析助手。请基于用户提供的数据，提供简明、有用的洞察和建议。
        
        你的分析应包括：
        1. 关键发现：数据中的主要模式和趋势
        2. 实用建议：基于数据的可行动建议
        3. 潜在改进：可以优化的领域
        
        保持专业、友好、简洁的语气。"""
        
        user_prompt = f"""请分析以下个人生产力数据：

{json.dumps(request_data, ensure_ascii=False, indent=2)}

请提供：
1. 整体趋势分析
2. 各模块关键洞察
3. 具体改进建议
4. 需要注意的事项

请用中文回答，使用简洁的要点格式。"""
        
        # API请求负载
        payload = {
            "model": self.default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
            "stream": False
        }
        
        start_time = time.time()
        self.request_count += 1
        
        try:
            response = requests.post(
                self.api_endpoint,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            
            response_time = time.time() - start_time
            self.total_response_time += response_time
            
            if response.status_code == 200:
                self.success_count += 1
                result = response.json()
                
                # 解析响应
                analysis_text = result["choices"][0]["message"]["content"]
                
                # 构建标准化响应
                analysis_result = {
                    "response_id": f"resp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{int(time.time() % 1000)}",
                    "request_id": request_data["request_id"],
                    "analysis_results": {
                        "insights": self._extract_insights(analysis_text),
                        "recommendations": self._extract_recommendations(analysis_text),
                        "raw_analysis": analysis_text
                    },
                    "performance_metrics": {
                        "response_time": round(response_time, 3),
                        "success": True,
                        "model_used": self.default_model
                    }
                }
                
                return analysis_result
            else:
                # API调用失败
                error_result = {
                    "response_id": f"err_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{int(time.time() % 1000)}",
                    "request_id": request_data["request_id"],
                    "analysis_results": {
                        "insights": [],
                        "recommendations": [],
                        "raw_analysis": f"API调用失败: {response.status_code} - {response.text}"
                    },
                    "performance_metrics": {
                        "response_time": round(response.time() - start_time, 3),
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
                }
                
                return error_result
                
        except requests.exceptions.Timeout:
            # 超时错误
            timeout_result = {
                "response_id": f"timeout_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{int(time.time() % 1000)}",
                "request_id": request_data["request_id"],
                "analysis_results": {
                    "insights": [],
                    "recommendations": [],
                    "raw_analysis": "API调用超时，请稍后重试"
                },
                "performance_metrics": {
                    "response_time": self.timeout,
                    "success": False,
                    "error": f"请求超时（{self.timeout}秒）"
                }
            }
            
            return timeout_result
            
        except Exception as e:
            # 其他异常
            error_result = {
                "response_id": f"except_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{int(time.time() % 1000)}",
                "request_id": request_data["request_id"],
                "analysis_results": {
                    "insights": [],
                    "recommendations": [],
                    "raw_analysis": f"分析过程发生错误: {str(e)}"
                },
                "performance_metrics": {
                    "response_time": round(time.time() - start_time, 3),
                    "success": False,
                    "error": str(e)
                }
            }
            
            return error_result
    
    def _extract_insights(self, analysis_text: str) -> List[Dict[str, Any]]:
        """从分析文本中提取关键洞察"""
        insights = []
        
        # 简单的文本分析逻辑
        # 在实际实现中，这里可以更复杂，比如使用正则表达式或NLP方法
        
        lines = analysis_text.split('\n')
        current_insight = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测可能是洞察的句子
            if any(keyword in line.lower() for keyword in ["趋势", "增长", "下降", "增加", "减少", "显著", "明显"]):
                if current_insight:
                    insights.append(current_insight)
                
                current_insight = {
                    "type": "trend_observation",
                    "confidence": 0.8,
                    "content": line,
                    "supporting_data": {}
                }
            elif current_insight and line.startswith(("- ", "• ", "* ", "1. ", "2. ")):
                # 可能是支持性信息
                current_insight["content"] += f"\n{line}"
        
        if current_insight:
            insights.append(current_insight)
        
        # 如果提取失败，返回一个通用洞察
        if not insights:
            insights.append({
                "type": "general_analysis",
                "confidence": 0.7,
                "content": "AI助手已完成数据分析，请查看完整报告获取详细洞察。",
                "supporting_data": {}
            })
        
        return insights
    
    def _extract_recommendations(self, analysis_text: str) -> List[Dict[str, Any]]:
        """从分析文本中提取建议"""
        recommendations = []
        
        lines = analysis_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测可能是建议的句子
            if any(keyword in line.lower() for keyword in ["建议", "推荐", "应该", "可以", "考虑", "尝试"]):
                # 简单优先级判断
                priority = "medium"
                if any(keyword in line.lower() for keyword in ["重要", "紧急", "必须", "优先"]):
                    priority = "high"
                elif any(keyword in line.lower() for keyword in ["可选", "如果", "可能"]):
                    priority = "low"
                
                recommendations.append({
                    "priority": priority,
                    "action": "general_advice",
                    "description": line,
                    "estimated_impact": "需要进一步评估"
                })
        
        # 如果提取失败，返回一个通用建议
        if not recommendations:
            recommendations.append({
                "priority": "medium",
                "action": "review_data",
                "description": "定期查看和分析个人数据，了解自己的习惯和模式。",
                "estimated_impact": "提高自我认知和生产力"
            })
        
        return recommendations
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        avg_response_time = 0
        if self.request_count > 0:
            avg_response_time = self.total_response_time / self.request_count
        
        success_rate = 0
        if self.request_count > 0:
            success_rate = self.success_count / self.request_count
        
        return {
            "total_requests": self.request_count,
            "successful_requests": self.success_count,
            "success_rate": round(success_rate * 100, 2),
            "average_response_time": round(avg_response_time, 3),
            "total_response_time": round(self.total_response_time, 3)
        }


# 测试函数
def test_deepseek_client():
    """测试DeepSeek客户端"""
    print("测试DeepSeek客户端...")
    
    # 注意：这需要一个有效的API密钥
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("警告：未设置DEEPSEEK_API_KEY环境变量，使用模拟测试")
        # 创建一个模拟客户端进行接口测试
        client = DeepSeekClient(api_key="test_key")
        
        # 模拟请求数据
        mock_link_data = {
            "total_count": 42,
            "category_distribution": {
                "technology": 15,
                "ai": 8,
                "news": 12,
                "finance": 7
            },
            "recent_trend": [
                {"date": "2026-02-25", "count": 6},
                {"date": "2026-02-26", "count": 8}
            ],
            "top_domains": ["github.com", "arxiv.org", "bbc.com"]
        }
        
        mock_financial_data = {
            "total_spending": 3256.80,
            "average_daily": 465.26,
            "top_categories": [
                {"category": "餐饮", "amount": 1256.80, "percentage": 38.6},
                {"category": "交通", "amount": 780.50, "percentage": 24.0}
            ],
            "record_count": 28
        }
        
        try:
            # 测试请求构建
            request_data = client._build_analysis_request(
                link_summary=mock_link_data,
                financial_summary=mock_financial_data
            )
            
            print(f"请求数据构建成功，ID: {request_data['request_id']}")
            print(f"数据上下文: {request_data['data_context']}")
            
            # 测试脱敏
            anonymized_link = client._anonymize_link_data(mock_link_data)
            print(f"链接数据脱敏后: {anonymized_link}")
            
            anonymized_financial = client._anonymize_financial_data(mock_financial_data)
            print(f"财务数据脱敏后: {anonymized_financial}")
            
            # 性能统计
            stats = client.get_performance_stats()
            print(f"性能统计: {stats}")
            
            print("客户端接口测试完成（模拟模式）")
            return True
            
        except Exception as e:
            print(f"测试失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    else:
        # 实际API测试
        client = DeepSeekClient(api_key=api_key)
        
        # 使用实际数据测试
        # （这里需要实际的数据源）
        print("实际API测试需要实际数据，跳过...")
        return True


if __name__ == "__main__":
    # 运行测试
    if test_deepseek_client():
        print("DeepSeek客户端测试完成")
    else:
        print("DeepSeek客户端测试失败")