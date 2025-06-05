"""
AI Service - Integrates with OpenRouter for various AI tasks.
File: Link_Profiler/services/ai_service.py
"""

import asyncio
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import openai
import redis.asyncio as redis
import random # New: Import random for simulated video analysis

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.core.models import Domain, LinkProfile, ContentGapAnalysisResult, SEOMetrics # New: Import SEOMetrics
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager

logger = logging.getLogger(__name__)

class OpenRouterClient:
    """
    Client for interacting with the OpenRouter API.
    Uses the OpenAI Python client library.
    """
    def __init__(self, api_key: str, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to OpenRouterClient. Falling back to local SessionManager.")

        # OpenAI client can be initialized with a custom http_client
        # We need to create a custom aiohttp client for OpenAI to use our session_manager
        self.http_client = openai.AsyncClient(
            base_url=self.base_url,
            api_key=self.api_key,
            http_client=self.session_manager.session # Pass the aiohttp session directly
        )
        self.logger = logging.getLogger(__name__ + ".OpenRouterClient")

    async def __aenter__(self):
        """Ensure session manager is entered."""
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure session manager is exited."""
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def complete(self, model: str, prompt: str, temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        """
        Sends a completion request to the OpenRouter API.
        """
        if not self.api_key:
            self.logger.error("OpenRouter API key is not configured. Skipping AI completion.")
            return None

        try:
            self.logger.info(f"Calling OpenRouter model: {model} with prompt (first 100 chars): {prompt[:100]}...")
            response = await self.http_client.chat.completions.create( # Use self.http_client
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"} # Request JSON response if possible
            )
            content = response.choices[0].message.content
            self.logger.info(f"Received response from {model}.")
            return content
        except openai.APIStatusError as e:
            self.logger.error(f"OpenRouter API error (Status: {e.status_code}): {e.response}", exc_info=True)
            return None
        except openai.APIConnectionError as e:
            self.logger.error(f"OpenRouter API connection error: {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during OpenRouter API call: {e}", exc_info=True)
            return None


class AIService:
    """
    Service for providing various AI-powered functionalities using OpenRouter.
    Includes caching for expensive AI calls.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.logger = logging.getLogger(__name__)
        self.enabled = config_loader.get("ai.enabled", False)
        self.openrouter_api_key = config_loader.get("ai.openrouter_api_key")
        self.cache_ttl = config_loader.get("ai.cache_ttl", 3600) # Default 1 hour
        self.models = config_loader.get("ai.models", {})
        self.session_manager = session_manager # Store the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to AIService. Falling back to local SessionManager.")

        if self.enabled and not self.openrouter_api_key:
            self.logger.warning("AI integration is enabled but OpenRouter API key is missing. AI features will be disabled.")
            self.enabled = False

        if self.enabled:
            self.openrouter_client = OpenRouterClient(api_key=self.openrouter_api_key, session_manager=self.session_manager)
            self.redis_client = redis.Redis(
                connection_pool=redis.ConnectionPool.from_url(config_loader.get("redis.url"))
            )
            self.logger.info("AI Service initialized and enabled.")
        else:
            self.logger.info("AI Service is disabled by configuration.")
            self.openrouter_client = None
            self.redis_client = None

    async def __aenter__(self):
        """Ensure session manager and OpenRouter client are entered."""
        await self.session_manager.__aenter__()
        if self.openrouter_client:
            await self.openrouter_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close Redis connection and ensure session manager and OpenRouter client are exited."""
        if self.redis_client:
            await self.redis_client.close()
        if self.openrouter_client:
            await self.openrouter_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def _call_ai_with_cache(self, task_type: str, prompt: str, cache_key: str, temperature: float = 0.7, max_tokens: int = 1000) -> Optional[Dict[str, Any]]:
        """
        Internal method to call AI model with caching.
        """
        if not self.enabled or not self.openrouter_client:
            return None

        model = self.models.get(task_type)
        if not model:
            self.logger.error(f"AI model not configured for task type: {task_type}. Skipping AI call.")
            return None

        # Check cache first
        if self.redis_client:
            cached_response = await self.redis_client.get(cache_key)
            if cached_response:
                self.logger.info(f"Cache hit for AI task '{task_type}' (key: {cache_key}).")
                return json.loads(cached_response)

        # Call AI if not in cache
        raw_response = await self.openrouter_client.complete(model, prompt, temperature, max_tokens)
        if raw_response:
            try:
                parsed_response = json.loads(raw_response)
                # Cache the response
                if self.redis_client:
                    await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(parsed_response))
                return parsed_response
            except json.JSONDecodeError:
                self.logger.error(f"AI response for task '{task_type}' was not valid JSON: {raw_response[:200]}...")
                return None
        return None

    async def score_content(self, content: str, target_keyword: str) -> Dict[str, Any]:
        """
        Analyzes content for SEO optimization and provides a score and suggestions.
        Returns a dictionary with seo_score, keyword_density_score, readability_score,
        semantic_keywords, and improvement_suggestions.
        """
        prompt = f"""
        Analyze the following content for SEO optimization targeting the keyword '{target_keyword}'.
        Provide a JSON response with the following keys:
        - "seo_score": An integer score from 0 to 100, where 100 is perfectly optimized.
        - "keyword_density_score": An integer score from 0 to 100 based on optimal keyword density.
        - "readability_score": An integer score from 0 to 100, where 100 is highly readable.
        - "semantic_keywords": A list of 5-10 semantically related keywords not explicitly mentioned but relevant.
        - "improvement_suggestions": A list of 3-5 actionable suggestions to improve SEO.

        Content:
        ---
        {content}
        ---
        """
        cache_key = f"ai_content_score:{target_keyword}:{hash(content)}" # Simple hash for content
        result = await self._call_ai_with_cache("content_scoring", prompt, cache_key, max_tokens=1500)
        
        if result is None:
            self.logger.warning(f"AI content scoring failed for keyword '{target_keyword}'. Returning default scores.")
            return {
                "seo_score": 50,
                "keyword_density_score": 50,
                "readability_score": 50,
                "semantic_keywords": [],
                "improvement_suggestions": ["AI analysis unavailable."]
            }
        return result

    async def classify_content(self, content: str, target_keyword: str) -> Optional[str]:
        """
        Classifies the content based on its quality and relevance to a target keyword.
        Possible classifications: "high_quality", "low_quality", "spam", "irrelevant".
        """
        prompt = f"""
        Classify the following content based on its quality and relevance to the target keyword '{target_keyword}'.
        Consider factors like depth, originality, readability, and topical alignment.
        Return a single word classification in JSON format, with a key "classification".
        Possible classifications: "high_quality", "low_quality", "spam", "irrelevant".

        Content:
        ---
        {content}
        ---
        """
        cache_key = f"ai_content_classification:{target_keyword}:{hash(content)}"
        result = await self._call_ai_with_cache("content_classification", prompt, cache_key, max_tokens=50) # Small max_tokens for single word
        
        if result and "classification" in result:
            classification = result["classification"].lower()
            if classification in ["high_quality", "low_quality", "spam", "irrelevant"]:
                self.logger.info(f"Content classified as: {classification}")
                return classification
            else:
                self.logger.warning(f"AI returned unexpected classification: {classification}. Defaulting to 'unknown'.")
                return "unknown"
        self.logger.warning(f"AI content classification failed for keyword '{target_keyword}'. Returning None.")
        return None

    async def analyze_content_gaps(self, target_url: str, competitor_urls: List[str]) -> ContentGapAnalysisResult:
        """
        Analyzes content gaps between a target URL and its competitors.
        Returns a ContentGapAnalysisResult object with insights.
        """
        prompt = f"""
        Perform a content gap analysis for the target URL '{target_url}' against its competitors: {', '.join(competitor_urls)}.
        Identify topics, keywords, or content formats present in competitors but missing from the target.
        Provide a JSON response with the following keys:
        - "missing_topics": List of missing topics (strings).
        - "missing_keywords": List of missing keywords (strings).
        - "content_format_gaps": List of content formats competitors use but target doesn't (strings).
        - "actionable_insights": List of actionable suggestions to fill these gaps (strings).
        """
        cache_key = f"ai_content_gap:{target_url}:{hash(tuple(competitor_urls))}"
        result_dict = await self._call_ai_with_cache("content_gap_analysis", prompt, cache_key, max_tokens=2000)
        
        if result_dict is None:
            self.logger.warning(f"AI content gap analysis failed for {target_url}. Returning default empty result.")
            return ContentGapAnalysisResult(
                target_url=target_url,
                competitor_urls=competitor_urls,
                missing_topics=[],
                missing_keywords=[],
                content_format_gaps=[],
                actionable_insights=["AI analysis unavailable."]
            )
        
        # Ensure lists are actual lists and not None
        result_dict["missing_topics"] = result_dict.get("missing_topics", [])
        result_dict["missing_keywords"] = result_dict.get("missing_keywords", [])
        result_dict["content_format_gaps"] = result_dict.get("content_format_gaps", [])
        result_dict["actionable_insights"] = result_dict.get("actionable_insights", [])

        return ContentGapAnalysisResult(
            target_url=target_url,
            competitor_urls=competitor_urls,
            **result_dict
        )

    async def perform_topic_clustering(self, texts: List[str], num_clusters: int = 5) -> Dict[str, List[str]]:
        """
        Simulates AI-powered topic clustering for a list of texts.
        Returns a dictionary where keys are cluster names/topics and values are lists of texts belonging to that cluster.
        """
        if not self.enabled or not self.openrouter_client:
            self.logger.warning("AI service is disabled. Cannot perform topic clustering.")
            return {"Simulated Topic 1": texts[:min(len(texts), 2)], "Simulated Topic 2": texts[min(len(texts), 2):]}

        prompt = f"""
        Perform topic clustering on the following list of texts.
        Group them into {num_clusters} distinct topics.
        Provide a JSON response where keys are the topic names (e.g., "SEO Strategies", "Link Building")
        and values are lists of the original texts that belong to that topic.
        
        Texts:
        {json.dumps(texts)}
        """
        cache_key = f"ai_topic_clustering:{hash(tuple(texts))}:{num_clusters}"
        result = await self._call_ai_with_cache("topic_clustering", prompt, cache_key, max_tokens=2000)

        if result is None:
            self.logger.warning("AI topic clustering failed. Returning simulated clusters.")
            # Fallback to a very basic simulation if AI call fails
            return {
                "General Topic A": texts[:len(texts)//2],
                "General Topic B": texts[len(texts)//2:]
            }
        
        # Validate and return the result
        # Ensure the result is a dictionary with list values
        cleaned_result = {}
        for key, value in result.items():
            if isinstance(key, str) and isinstance(value, list):
                cleaned_result[key] = [str(item) for item in value if isinstance(item, str)]
        return cleaned_result


    async def suggest_semantic_keywords(self, primary_keyword: str) -> List[str]:
        """
        Generates a list of semantically related keywords.
        """
        prompt = f"""
        Generate a list of 10-15 semantically related keywords for the primary keyword '{primary_keyword}'.
        Focus on long-tail variations, related concepts, and user intent.
        Provide the response as a JSON object with a single key "keywords" which is a list of strings.
        """
        cache_key = f"ai_semantic_keywords:{primary_keyword}"
        result = await self._call_ai_with_cache("keyword_research", prompt, cache_key, max_tokens=500)
        
        if result is None:
            self.logger.warning(f"AI semantic keyword suggestion failed for '{primary_keyword}'.")
            return []
        return result.get("keywords", [])

    async def analyze_technical_seo(self, url: str, html_content: str, lighthouse_report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes technical SEO aspects of a page, combining HTML and Lighthouse data.
        """
        prompt = f"""
        Analyze the technical SEO of the following page.
        URL: {url}
        HTML Content (first 1000 chars): {html_content[:1000]}...
        Lighthouse Report Summary (if available): {json.dumps(lighthouse_report)[:1000] if lighthouse_report else 'N/A'}

        Provide a JSON response with:
        - "technical_issues": List of identified technical SEO issues.
        - "technical_suggestions": List of actionable suggestions to fix them.
        - "overall_technical_score": An integer score from 0 to 100.
        """
        cache_key = f"ai_tech_seo:{url}:{hash(html_content[:1000])}" # Cache based on URL and partial content
        result = await self._call_ai_with_cache("technical_seo_analysis", prompt, cache_key, max_tokens=1500)
        
        if result is None:
            self.logger.warning(f"AI technical SEO analysis failed for {url}.")
            return {"technical_issues": [], "technical_suggestions": [], "overall_technical_score": 50}
        return result

    async def analyze_competitors(self, primary_domain: str, competitor_domains: List[str]) -> Dict[str, Any]:
        """
        Analyzes competitor strategies based on their domains.
        """
        prompt = f"""
        Analyze the competitive landscape for '{primary_domain}' against these competitors: {', '.join(competitor_domains)}.
        Based on general SEO knowledge and common strategies, provide a JSON response with:
        - "competitor_strengths": Dict of competitor_domain -> list of strengths.
        - "competitor_weaknesses": Dict of competitor_domain -> list of weaknesses.
        - "strategic_recommendations": List of strategic recommendations for the primary domain.
        """
        cache_key = f"ai_competitor_analysis:{primary_domain}:{hash(tuple(competitor_domains))}"
        result = await self._call_ai_with_cache("competitor_analysis", prompt, cache_key, max_tokens=1500)
        
        if result is None:
            self.logger.warning(f"AI competitor analysis failed for {primary_domain}.")
            return {"competitor_strengths": {}, "competitor_weaknesses": {}, "strategic_recommendations": ["AI analysis unavailable."]}
        return result

    async def generate_content_ideas(self, topic: str, num_ideas: int = 5) -> List[str]:
        """
        Generates content ideas for a given topic.
        """
        prompt = f"""
        Generate {num_ideas} unique and engaging content ideas for the topic '{topic}'.
        Focus on ideas that are SEO-friendly and address user intent.
        Provide the response as a JSON object with a single key "ideas" which is a list of strings.
        """
        cache_key = f"ai_content_ideas:{topic}:{num_ideas}"
        result = await self._call_ai_with_cache("content_generation", prompt, cache_key, max_tokens=1000)
        
        if result is None:
            self.logger.warning(f"AI content idea generation failed for '{topic}'.")
            return []
        return result.get("ideas", [])

    async def analyze_domain_value(self, domain_name: str, domain_info: Optional[Domain], link_profile_summary: Optional[LinkProfile]) -> Dict[str, Any]:
        """
        Performs an AI-driven analysis of a domain's value, combining various data points.
        """
        domain_details = json.dumps(domain_info.to_dict()) if domain_info else "N/A"
        link_profile_details = json.dumps(link_profile_summary.to_dict()) if link_profile_summary else "N/A"

        prompt = f"""
        Analyze the potential value of the domain '{domain_name}' for acquisition or SEO purposes.
        Consider the following data:
        Domain Info: {domain_details}
        Link Profile Summary: {link_profile_details}

        Provide a JSON response with:
        - "value_adjustment": An integer score adjustment (-50 to +50) to the existing value score based on nuanced AI insights.
        - "reasons": A list of 3-5 key reasons for the domain's value or lack thereof.
        - "details": A dictionary with any additional AI-generated insights or flags (e.g., "niche_relevance": "high").
        """
        cache_key = f"ai_domain_value:{domain_name}:{hash(domain_details)}:{hash(link_profile_details)}"
        result = await self._call_ai_with_cache("domain_value_analysis", prompt, cache_key, max_tokens=1000)

        if result is None:
            self.logger.warning(f"AI domain value analysis failed for '{domain_name}'. Returning default adjustment.")
            return {"value_adjustment": 0, "reasons": ["AI analysis unavailable."], "details": {}}
        return result

    async def analyze_content_nlp(self, content: str) -> Dict[str, Any]:
        """
        Performs Natural Language Processing (NLP) on content to extract entities, sentiment, and topics.
        Returns a dictionary with "entities", "sentiment", and "topics".
        """
        prompt = f"""
        Perform Natural Language Processing (NLP) on the following content.
        Extract the most important entities (people, organizations, locations, key concepts).
        Determine the overall sentiment (positive, neutral, negative).
        Identify the main topics discussed.
        Provide a JSON response with the following keys:
        - "entities": A list of up to 10 key entities (strings).
        - "sentiment": A single string indicating overall sentiment ("positive", "neutral", "negative").
        - "topics": A list of up to 5 main topics (strings).

        Content:
        ---
        {content[:4000]} # Limit content length for prompt
        ---
        """
        cache_key = f"ai_content_nlp:{hash(content)}"
        result = await self._call_ai_with_cache("content_nlp_analysis", prompt, cache_key, max_tokens=700)
        
        if result is None:
            self.logger.warning("AI content NLP analysis failed. Returning default empty results.")
            return {
                "entities": [],
                "sentiment": "neutral",
                "topics": []
            }
        
        # Validate and clean up the response
        result["entities"] = [str(e) for e in result.get("entities", []) if isinstance(e, str)][:10]
        result["topics"] = [str(t) for t in result.get("topics", []) if isinstance(t, str)][:5]
        sentiment = result.get("sentiment", "neutral").lower()
        if sentiment not in ["positive", "neutral", "negative"]:
            sentiment = "neutral"
        result["sentiment"] = sentiment

        return result

    async def analyze_video_content(self, video_url: str, video_data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Simulates AI-powered video content analysis and transcription.
        In a real scenario, this would involve sending video data to a specialized API.
        """
        if not self.enabled:
            self.logger.warning("AI service is disabled. Cannot perform video analysis.")
            return {}

        # For simulation, we'll generate dummy data.
        # In a real implementation, video_data (bytes) would be sent to a specialized API.
        
        simulated_transcription = f"Simulated transcription for video at {video_url}. This video discusses {random.choice(['SEO strategies', 'digital marketing trends', 'web development', 'link building techniques'])} and provides actionable insights."
        simulated_topics = random.sample(["SEO", "Marketing", "Video Content", "Analytics", "Strategy"], random.randint(1, 3))
        
        self.logger.info(f"Simulated video analysis for {video_url}. Topics: {simulated_topics}")
        
        return {
            "transcription": simulated_transcription,
            "topics": simulated_topics
        }

    async def assess_content_quality(self, content: str, url: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Assesses the quality of the given content and provides a classification.
        Returns a tuple of (quality_score, classification_string).
        """
        if not self.enabled or not self.openrouter_client:
            self.logger.warning("AI service is disabled. Cannot assess content quality.")
            return None, None

        prompt = f"""
        Analyze the following web page content from URL: {url}.
        Assess its overall quality, originality, depth, and relevance.
        Provide a JSON response with two keys:
        - "quality_score": An integer score from 0 to 100, where 100 is excellent quality.
        - "classification": A single word classification: "excellent", "good", "average", "low_quality", "spam".

        Content:
        ---
        {content[:8000]} # Limit content length for prompt
        ---
        """
        cache_key = f"ai_content_quality_assessment:{url}:{hash(content[:1000])}" # Cache based on URL and partial content
        result = await self._call_ai_with_cache("content_quality_assessment", prompt, cache_key, max_tokens=200)
        
        if result:
            score = result.get("quality_score")
            classification = result.get("classification")
            if isinstance(score, (int, float)) and isinstance(classification, str):
                classification = classification.lower()
                if classification not in ["excellent", "good", "average", "low_quality", "spam"]:
                    classification = "average" # Default to average if AI gives unexpected classification
                self.logger.info(f"Content quality for {url}: Score={score}, Classification={classification}")
                return float(score), classification
            else:
                self.logger.warning(f"AI returned invalid format for content quality assessment for {url}: {result}")
        self.logger.warning(f"AI content quality assessment failed for {url}. Returning None, None.")
        return None, None
