"""
分类规则引擎
负责智能分类链接内容，采用规则引擎优先、AI补充的双层分类策略
支持技术、学术、新闻、健康、财务等多个领域
"""

import logging
import re
from typing import Dict, List, Any, Optional, Set, Tuple
import json
from pathlib import Path

# 设置日志
logger = logging.getLogger(__name__)

class RuleEngine:
    """规则引擎：基于关键词和规则进行分类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化规则引擎
        
        Args:
            config: 配置字典，包含关键词规则等
        """
        self.config = config or {}
        
        # 默认关键词规则库
        self.default_keyword_rules = {
            "technology": ["python", "javascript", "github", "programming", "code", 
                          "software", "api", "database", "algorithm", "framework",
                          "devops", "cloud", "container", "kubernetes", "docker"],
            "ai": ["ai", "artificial intelligence", "machine learning", "neural network",
                  "deep learning", "llm", "gpt", "transformer", "generative", "chatbot",
                  "computer vision", "nlp", "reinforcement learning"],
            "academic": ["arxiv", "paper", "research", "survey", "journal", "conference",
                        "peer-reviewed", "citation", "methodology", "experiment",
                        "hypothesis", "thesis", "dissertation", "publication"],
            "news": ["bbc", "cnn", "news", "report", "article", "breaking", "update",
                    "coverage", "headline", "journalist", "media", "press", "wire"],
            "business": ["product", "management", "strategy", "roadmap", "market",
                        "startup", "venture", "investment", "funding", "revenue",
                        "profit", "customer", "competitor", "industry", "growth"],
            "finance": ["investing", "stocks", "analysis", "financial", "trading",
                       "portfolio", "crypto", "blockchain", "investment", "wealth",
                       "banking", "insurance", "mortgage", "loan", "interest"],
            "science": ["nature", "science", "physics", "quantum", "experiment",
                       "discovery", "biology", "chemistry", "astronomy", "geology",
                       "theory", "evidence", "scientific", "research"],
            "education": ["tutorial", "guide", "introduction", "learn", "course",
                         "lecture", "lesson", "training", "education", "university",
                         "college", "school", "student", "teacher", "curriculum"],
            "web_development": ["html", "css", "javascript", "web", "browser",
                               "frontend", "backend", "responsive", "ux", "ui",
                               "design", "website", "webpage", "domain", "hosting"],
            "health": ["fitness", "nutrition", "exercise", "health", "wellness",
                      "medical", "disease", "treatment", "medicine", "doctor",
                      "hospital", "patient", "symptom", "diagnosis", "recovery"]
        }
        
        # 合并配置
        self.keyword_rules = self.default_keyword_rules.copy()
        if "keyword_rules" in self.config:
            # 更新但不覆盖默认规则
            for category, keywords in self.config["keyword_rules"].items():
                if category in self.keyword_rules:
                    # 合并关键词列表
                    self.keyword_rules[category] = list(set(self.keyword_rules[category] + keywords))
                else:
                    self.keyword_rules[category] = keywords
        
        # 匹配阈值
        self.matching_threshold = self.config.get("matching_threshold", 1)
        self.scoring_method = self.config.get("scoring_method", "binary")
        
        # 域名规则权重
        self.domain_rule_weight = self.config.get("domain_rule_weight", 3)
        logger.info(f"域名规则权重设置为: {self.domain_rule_weight}")
        
        # 构建反向索引以提高匹配速度
        # 默认域名规则库
        self.default_domain_rules = {
            "bbc.com": ["news"],
            "bbc.co.uk": ["news"],
            "medium.com": ["technology"],
            "github.com": ["technology", "web_development"],
            "arxiv.org": ["academic"],
            "python.org": ["technology", "education"],
            "investopedia.com": ["finance", "education"],
            "nature.com": ["science", "academic"],
            "stackoverflow.com": ["technology", "education", "programming"],
            "w3schools.com": ["web_development", "education"],
            "towardsdatascience.com": ["ai", "technology"],
            "cnn.com": ["news"],
            "reuters.com": ["news"],
            "techcrunch.com": ["technology", "business"],
            "forbes.com": ["business", "finance"],
            "wsj.com": ["business", "finance"],
            "bloomberg.com": ["finance", "business"],
            "youtube.com": ["education"],
            "ted.com": ["education"],
            "wikipedia.org": ["education"],
            "apple.com": ["technology", "business"],
            "microsoft.com": ["technology", "business"],
            "google.com": ["technology", "business"]
        }
        
        # 合并域名规则配置
        self.domain_rules = self.default_domain_rules.copy()
        if "domain_rules" in self.config:
            for domain, categories in self.config["domain_rules"].items():
                self.domain_rules[domain] = categories
        
        self._build_reverse_index()
        
        logger.info(f"RuleEngine initialized with {len(self.keyword_rules)} categories")
    
    @staticmethod
    def extract_domain(url: str) -> str:
        """从URL中提取域名（简化版本）"""
        import re
        # 移除协议部分
        original_url = url
        url = re.sub(r'^https?://', '', url)
        # 移除路径部分
        url = re.sub(r'/.*$', '', url)
        # 移除端口号
        url = re.sub(r':\d+$', '', url)
        # 移除www前缀
        if url.startswith('www.'):
            url = url[4:]
        extracted = url.lower()
        logger.debug(f"域名提取: '{original_url}' -> '{extracted}'")
        return extracted
    
    def _build_reverse_index(self):
        """构建关键词到类别的反向索引"""
        self.reverse_index = {}
        for category, keywords in self.keyword_rules.items():
            for keyword in keywords:
                if keyword not in self.reverse_index:
                    self.reverse_index[keyword] = []
                self.reverse_index[keyword].append(category)
    
    def classify(self, text: str, url: Optional[str] = None) -> Dict[str, Any]:
        """
        基于规则进行分类
        
        Args:
            text: 待分类文本
            url: 可选URL，用于域名规则匹配
            
        Returns:
            分类结果字典
        """
        try:
            logger.debug("开始规则分类，文本长度: %d", len(text))
            text_lower = text.lower()
            
            # 统计匹配情况
            category_scores = {}
            
            # 域名规则匹配（如果有URL）
            if url:
                domain = RuleEngine.extract_domain(url)
                for rule_domain, categories in self.domain_rules.items():
                    if rule_domain in domain or domain.endswith('.' + rule_domain):
                        for category in categories:
                            # 域名规则给予较高权重
                            category_scores[category] = category_scores.get(category, 0) + self.domain_rule_weight
                            logger.debug(f"域名规则匹配: {rule_domain} -> {category}, 权重+{self.domain_rule_weight}, 当前得分: {category_scores.get(category, 0)}")
            
            # 方法1：直接关键词匹配
            for category, keywords in self.keyword_rules.items():
                score = 0
                for keyword in keywords:
                    # 使用单词边界匹配，避免部分匹配
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    matches = re.findall(pattern, text_lower)
                    if matches:
                        logger.debug(f"关键词匹配: 类别={category}, 关键词='{keyword}', 匹配次数={len(matches)}")
                        if self.scoring_method == "binary":
                            score = 1
                            break  # 匹配到即给分
                        else:  # weighted
                            score += len(matches)
                
                if score > 0:
                    category_scores[category] = score
            
            # 方法2：使用反向索引提高效率（备用）
            if not category_scores:
                for keyword, categories in self.reverse_index.items():
                    if keyword in text_lower:
                        for category in categories:
                            category_scores[category] = category_scores.get(category, 0) + 1
            
            # 过滤低于阈值的分类
            filtered_categories = []
            for category, score in category_scores.items():
                logger.debug(f"类别得分: 类别={category}, 得分={score}, 阈值={self.matching_threshold}, 是否通过={score >= self.matching_threshold}")
                if score >= self.matching_threshold:
                    filtered_categories.append(category)
            
            # 结果处理
            if filtered_categories:
                confidence = "high" if len(filtered_categories) >= 2 else "medium"
                result = {
                    "success": True,
                    "labels": filtered_categories,
                    "source": "rule_engine",
                    "confidence": confidence,
                    "scores": category_scores
                }
                logger.info("规则分类成功: 标签=%s, 置信度=%s", filtered_categories, confidence)
                return result
            else:
                result = {
                    "success": False,
                    "labels": [],
                    "source": "rule_engine",
                    "confidence": "low",
                    "message": "未匹配到足够的分类规则"
                }
                logger.debug("规则分类未匹配到足够规则")
                return result
                
        except Exception as e:
            logger.error("规则分类失败: %s", str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def add_rule(self, category: str, keywords: List[str]):
        """
        添加新的分类规则
        
        Args:
            category: 分类标签
            keywords: 关键词列表
        """
        if category not in self.keyword_rules:
            self.keyword_rules[category] = []
        
        # 添加新关键词
        existing_keywords = set(self.keyword_rules[category])
        new_keywords = set(keywords)
        self.keyword_rules[category] = list(existing_keywords.union(new_keywords))
        
        # 更新反向索引
        for keyword in new_keywords:
            if keyword not in self.reverse_index:
                self.reverse_index[keyword] = []
            if category not in self.reverse_index[keyword]:
                self.reverse_index[keyword].append(category)
        
        logger.info("添加规则: 分类=%s, 关键词数量=%d", category, len(new_keywords))
    
    def save_rules(self, filepath: str):
        """
        保存规则到文件
        
        Args:
            filepath: 文件路径
        """
        try:
            rules_data = {
                "keyword_rules": self.keyword_rules,
                "config": {
                    "matching_threshold": self.matching_threshold,
                    "scoring_method": self.scoring_method
                }
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(rules_data, f, ensure_ascii=False, indent=2)
            
            logger.info("规则已保存到: %s", filepath)
            
        except Exception as e:
            logger.error("保存规则失败: %s", str(e))
            raise
    
    def load_rules(self, filepath: str):
        """
        从文件加载规则
        
        Args:
            filepath: 文件路径
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                rules_data = json.load(f)
            
            # 更新关键词规则
            self.keyword_rules = rules_data.get("keyword_rules", {})
            
            # 更新配置
            if "config" in rules_data:
                config = rules_data["config"]
                self.matching_threshold = config.get("matching_threshold", 1)
                self.scoring_method = config.get("scoring_method", "binary")
            
            # 重建反向索引
            self._build_reverse_index()
            
            logger.info("规则已从 %s 加载，分类数量: %d", filepath, len(self.keyword_rules))
            
        except Exception as e:
            logger.error("加载规则失败: %s", str(e))
            raise


class AIModelClassifier:
    """AI模型分类器（模拟版本，实际系统中应使用BERT等模型）"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化AI分类器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", False)
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)
        
        logger.info("AIModelClassifier initialized (enabled=%s)", self.enabled)
    
    def classify(self, text: str) -> Dict[str, Any]:
        """
        AI模型分类（模拟实现）
        
        Args:
            text: 待分类文本
            url: 可选URL，用于域名规则匹配
            
        Returns:
            分类结果字典
        """
        if not self.enabled:
            return {
                "success": False,
                "labels": [],
                "source": "ai_model",
                "confidence": "low",
                "message": "AI模型未启用"
            }
        
        try:
            logger.debug("开始AI模型分类，文本长度: %d", len(text))
            text_lower = text.lower()
            
            # 模拟AI模型的逻辑（实际系统中应调用真实模型）
            predicted_labels = []
            
            # 简单的规则模拟（实际应用应替换为模型预测）
            if "python" in text_lower or "programming" in text_lower:
                predicted_labels.append("programming")
            
            if "ai" in text_lower or "machine learning" in text_lower:
                predicted_labels.append("ai")
            
            if "github" in text_lower:
                predicted_labels.append("technology")
            
            if "arxiv" in text_lower or "research" in text_lower:
                predicted_labels.append("academic")
            
            if "bbc" in text_lower or "news" in text_lower:
                predicted_labels.append("news")
            
            if "product" in text_lower or "management" in text_lower:
                predicted_labels.append("business")
            
            if "html" in text_lower or "web" in text_lower:
                predicted_labels.append("web_development")
            
            if "tutorial" in text_lower or "guide" in text_lower:
                predicted_labels.append("education")
            
            if "investing" in text_lower or "financial" in text_lower:
                predicted_labels.append("finance")
            
            if "health" in text_lower or "medical" in text_lower:
                predicted_labels.append("health")
            
            if "science" in text_lower or "physics" in text_lower:
                predicted_labels.append("science")
            
            # 去重
            predicted_labels = list(set(predicted_labels))
            
            if predicted_labels:
                result = {
                    "success": True,
                    "labels": predicted_labels,
                    "source": "ai_model",
                    "confidence": "medium",
                    "message": "AI模型分类完成"
                }
                logger.info("AI模型分类成功: 标签=%s", predicted_labels)
                return result
            else:
                result = {
                    "success": False,
                    "labels": [],
                    "source": "ai_model",
                    "confidence": "low",
                    "message": "AI模型未预测到分类"
                }
                logger.debug("AI模型分类未预测到结果")
                return result
                
        except Exception as e:
            logger.error("AI模型分类失败: %s", str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }


class HybridClassificationSystem:
    """混合智能分类系统：规则引擎优先，AI模型补充"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化混合分类系统
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        
        # 默认配置
        self.default_config = {
            "strategy": "hybrid",  # hybrid, rule_based, ai_only
            "rule_engine_priority": True,
            "fallback_to_ai": True,
            "default_labels": ["general"]
        }
        
        # 合并配置
        self.config = {**self.default_config, **self.config}
        
        # 初始化子组件
        rule_config = self.config.get("rule_engine", {})
        ai_config = self.config.get("ai_model", {})
        
        self.rule_engine = RuleEngine(rule_config)
        self.ai_classifier = AIModelClassifier(ai_config)
        
        logger.info("HybridClassificationSystem initialized with strategy: %s", 
                   self.config["strategy"])
    
    def classify(self, text: str, url: Optional[str] = None) -> Dict[str, Any]:
        """
        混合分类：规则引擎优先，AI模型补充
        
        Args:
            text: 待分类文本
            url: 可选URL，用于域名规则匹配
            
        Returns:
            分类结果字典
        """
        try:
            logger.debug("开始混合分类，文本长度: %d", len(text))
            
            strategy = self.config.get("strategy", "hybrid")
            rule_priority = self.config.get("rule_engine_priority", True)
            fallback_ai = self.config.get("fallback_to_ai", True)
            
            # 根据策略选择分类方法
            if strategy == "rule_based":
                # 仅使用规则引擎
                result = self.rule_engine.classify(text, url)
                return result
                
            elif strategy == "ai_only":
                # 仅使用AI模型
                result = self.ai_classifier.classify(text)
                return result
                
            else:  # hybrid 策略
                # 第一层：规则引擎分类
                rule_result = self.rule_engine.classify(text, url)
                
                # 如果规则引擎置信度高，直接返回
                if rule_result.get("success", False) and rule_result.get("confidence") in ["high", "medium"]:
                    logger.debug("规则引擎分类置信度高，直接返回")
                    return rule_result
                
                # 第二层：AI模型分类（如果需要）
                if fallback_ai:
                    ai_result = self.ai_classifier.classify(text)
                    
                    if ai_result.get("success", False):
                        # 融合结果：合并规则引擎和AI模型的标签
                        rule_labels = set(rule_result.get("labels", []))
                        ai_labels = set(ai_result.get("labels", []))
                        
                        all_labels = list(rule_labels.union(ai_labels))
                        
                        if all_labels:
                            # 确定结果来源和置信度
                            if rule_labels and ai_labels:
                                source = "hybrid"
                                confidence = "high"
                            elif rule_labels:
                                source = "rule_engine"
                                confidence = "medium"
                            else:
                                source = "ai_model"
                                confidence = "medium"
                            
                            result = {
                                "success": True,
                                "labels": all_labels,
                                "source": source,
                                "confidence": confidence,
                                "rule_labels": list(rule_labels),
                                "ai_labels": list(ai_labels)
                            }
                            logger.info("混合分类成功: 标签=%s, 来源=%s", all_labels, source)
                            return result
                
                # 如果以上都失败，使用默认标签
                default_labels = self.config.get("default_labels", ["general"])
                logger.debug("分类失败，使用默认标签: %s", default_labels)
                
                return {
                    "success": True,
                    "labels": default_labels,
                    "source": "default",
                    "confidence": "low",
                    "message": "使用默认分类标签"
                }
                
        except Exception as e:
            logger.error("混合分类失败: %s", str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def evaluate(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        评估分类系统性能
        
        Args:
            test_data: 测试数据列表，包含"text"和"true_labels"字段
            
        Returns:
            评估结果字典
        """
        try:
            logger.info("开始分类系统评估，测试数据数量: %d", len(test_data))
            
            results = []
            
            for item in test_data:
                text = item.get("text", "")
                true_labels = set(item.get("true_labels", []))
                
                # 获取预测结果
                prediction = self.classify(text)
                predicted_labels = set(prediction.get("labels", []))
                
                # 计算评估指标
                correct = true_labels.intersection(predicted_labels)
                incorrect = predicted_labels.difference(true_labels)
                missed = true_labels.difference(predicted_labels)
                
                precision = len(correct) / len(predicted_labels) if predicted_labels else 0
                recall = len(correct) / len(true_labels) if true_labels else 0
                f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
                
                result_item = {
                    "text": text[:100] + "..." if len(text) > 100 else text,
                    "true_labels": list(true_labels),
                    "predicted_labels": list(predicted_labels),
                    "source": prediction.get("source", "unknown"),
                    "confidence": prediction.get("confidence", "low"),
                    "correct": list(correct),
                    "incorrect": list(incorrect),
                    "missed": list(missed),
                    "precision": precision,
                    "recall": recall,
                    "f1_score": f1_score
                }
                results.append(result_item)
            
            # 计算总体统计
            avg_precision = sum(r["precision"] for r in results) / len(results)
            avg_recall = sum(r["recall"] for r in results) / len(results)
            avg_f1 = sum(r["f1_score"] for r in results) / len(results)
            
            # 分类源统计
            sources_count = {}
            for r in results:
                source = r["source"]
                sources_count[source] = sources_count.get(source, 0) + 1
            
            evaluation = {
                "detailed_results": results,
                "overall_metrics": {
                    "average_precision": avg_precision,
                    "average_recall": avg_recall,
                    "average_f1_score": avg_f1,
                    "total_items": len(results)
                },
                "source_distribution": sources_count,
                "accuracy_target": 0.7,  # 目标准确率
                "meets_target": avg_f1 >= 0.7
            }
            
            logger.info("评估完成: 平均F1分数=%.3f, 达到目标=%s", avg_f1, evaluation["meets_target"])
            
            return evaluation
            
        except Exception as e:
            logger.error("评估失败: %s", str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }


# 工厂函数
def create_classifier(config: Optional[Dict[str, Any]] = None) -> HybridClassificationSystem:
    """创建分类器实例"""
    return HybridClassificationSystem(config)


if __name__ == "__main__":
    # 简单测试
    import sys
    logging.basicConfig(level=logging.INFO)
    
    classifier = HybridClassificationSystem()
    
    test_texts = [
        "Python programming tutorial for beginners with examples",
        "AI and machine learning research paper from arXiv",
        "BBC news report on technology developments",
        "Financial analysis of stock market trends"
    ]
    
    print("测试分类系统:")
    for text in test_texts:
        result = classifier.classify(text)
        print(f"文本: {text[:50]}...")
        print(f"  分类: {result.get('labels', [])} (来源: {result.get('source', 'unknown')})")
        print()