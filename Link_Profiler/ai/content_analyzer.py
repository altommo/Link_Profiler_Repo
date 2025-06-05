"""
AI-Powered Content Analyzer - Provides advanced content analysis capabilities.
This module integrates with the AI service to perform tasks like:
- Content quality scoring
- Spam detection
- Language detection
- Topic classification
- Sentiment analysis
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
import json

from Link_Profiler.services.ai_service import AIService # Assuming AIService is available
from Link_Profiler.core.models import SEOMetrics # Assuming SEOMetrics is available

logger = logging.getLogger(__name__)

class ContentAnalyzer:
    """
    Orchestrates AI-powered content analysis tasks.
    """
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        self.logger = logging.getLogger(__name__ + ".ContentAnalyzer")

    async def assess_content_quality(self, content: str, url: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Assesses the quality of the given content and provides a classification.
        Returns a tuple of (quality_score, classification_string).
        """
        if not self.ai_service.enabled:
            self.logger.warning("AI service is disabled. Cannot assess content quality.")
            return None, None
        
        return await self.ai_service.assess_content_quality(content, url)

    async def analyze_content_nlp(self, content: str) -> Dict[str, Any]:
        """
        Performs Natural Language Processing (NLP) on content to extract entities, sentiment, and topics.
        Returns a dictionary with "entities", "sentiment", and "topics".
        """
        if not self.ai_service.enabled:
            self.logger.warning("AI service is disabled. Cannot perform NLP analysis.")
            return {
                "entities": [],
                "sentiment": "neutral",
                "topics": []
            }
        
        return await self.ai_service.analyze_content_nlp(content)

    async def perform_topic_clustering(self, texts: List[str], num_clusters: int = 5) -> Dict[str, List[str]]:
        """
        Performs AI-powered topic clustering for a list of texts.
        Returns a dictionary where keys are cluster names/topics and values are lists of texts belonging to that cluster.
        """
        if not self.ai_service.enabled:
            self.logger.warning("AI service is disabled. Cannot perform topic clustering.")
            return {"Simulated Topic 1": texts[:min(len(texts), 2)], "Simulated Topic 2": texts[min(len(texts), 2):]}
        
        return await self.ai_service.perform_topic_clustering(texts, num_clusters)

    async def suggest_semantic_keywords(self, primary_keyword: str) -> List[str]:
        """
        Generates a list of semantically related keywords using AI.
        """
        if not self.ai_service.enabled:
            self.logger.warning("AI service is disabled. Cannot suggest semantic keywords.")
            return []
        
        return await self.ai_service.suggest_semantic_keywords(primary_keyword)

    async def analyze_content_gaps(self, target_url: str, competitor_urls: List[str]) -> Dict[str, Any]:
        """
        Analyzes content gaps between a target URL and its competitors using AI.
        Returns a dictionary with insights.
        """
        if not self.ai_service.enabled:
            self.logger.warning("AI service is disabled. Cannot analyze content gaps.")
            return {
                "missing_topics": [],
                "missing_keywords": [],
                "content_format_gaps": [],
                "actionable_insights": ["AI analysis unavailable."]
            }
        
        result = await self.ai_service.analyze_content_gaps(target_url, competitor_urls)
        return result.to_dict() # Convert ContentGapAnalysisResult to dict for generic return

    async def generate_content_ideas(self, topic: str, num_ideas: int = 5) -> List[str]:
        """
        Generates content ideas for a given topic using AI.
        """
        if not self.ai_service.enabled:
            self.logger.warning("AI service is disabled. Cannot generate content ideas.")
            return []
        
        return await self.ai_service.generate_content_ideas(topic, num_ideas)

    async def analyze_domain_value(self, domain_name: str, domain_info: Optional[Any], link_profile_summary: Optional[Any]) -> Dict[str, Any]:
        """
        Performs an AI-driven analysis of a domain's value.
        """
        if not self.ai_service.enabled:
            self.logger.warning("AI service is disabled. Cannot analyze domain value.")
            return {"value_adjustment": 0, "reasons": ["AI analysis unavailable."], "details": {}}
        
        return await self.ai_service.analyze_domain_value(domain_name, domain_info, link_profile_summary)

    async def analyze_competitors(self, primary_domain: str, competitor_domains: List[str]) -> Dict[str, Any]:
        """
        Analyzes competitor strategies using AI.
        """
        if not self.ai_service.enabled:
            self.logger.warning("AI service is disabled. Cannot analyze competitors.")
            return {"competitor_strengths": {}, "competitor_weaknesses": {}, "strategic_recommendations": ["AI analysis unavailable."]}
        
        return await self.ai_service.analyze_competitors(primary_domain, competitor_domains)

    async def analyze_technical_seo(self, url: str, html_content: str, lighthouse_report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes technical SEO aspects of a page using AI.
        """
        if not self.ai_service.enabled:
            self.logger.warning("AI service is disabled. Cannot analyze technical SEO.")
            return {"technical_issues": [], "technical_suggestions": [], "overall_technical_score": 50}
        
        return await self.ai_service.analyze_technical_seo(url, html_content, lighthouse_report)

    async def analyze_video_content(self, video_url: str, video_data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Performs AI-powered video content analysis and transcription.
        """
        if not self.ai_service.enabled:
            self.logger.warning("AI service is disabled. Cannot analyze video content.")
            return {}
        
        return await self.ai_service.analyze_video_content(video_url, video_data)
