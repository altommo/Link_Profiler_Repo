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
import httpx # New: Import httpx for OpenAI client compatibility

# New: Imports for video analysis
import cv2
import base64
import tempfile
import os

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.core.models import Domain, LinkProfile, ContentGapAnalysisResult, SEOMetrics # New: Import SEOMetrics
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager
from Link_Profiler.database.database import Database # Import Database for DB operations

logger = logging.getLogger(__name__)

class OpenRouterClient:
    """
    Client for interacting with the OpenRouter API.
    Uses the OpenAI Python client library.
    """
    def __init__(self, api_key: str, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, redis_client: Optional[redis.Redis] = None): # Added redis_client
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to OpenRouterClient. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to OpenRouterClient. Falling back to global instance.")
        self.redis_client = redis_client # Stored redis_client


        # OpenAI client can be initialized with a custom httpx client
        # We need to create a custom httpx client for OpenAI to use our session_manager's aiohttp session
        # This is a workaround as openai.AsyncClient expects httpx.AsyncClient, not aiohttp.ClientSession directly.
        # For simplicity and to avoid deep dependency injection issues with httpx,
        # we'll let openai.AsyncClient manage its own httpx client, but ensure it's within our context.
        # For now, we'll use the default httpx client managed by openai.AsyncClient.
        self.http_client = openai.AsyncClient(
            base_url=self.base_url,
            api_key=self.api_key,
            # http_client=httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(mounts={
            #     "http://": httpx.AsyncHTTPTransport(backend="asyncio", local_address=self.session_manager.session._connector),
            #     "https://": httpx.AsyncHTTPTransport(backend="asyncio", local_address=self.session_manager.session._connector)
            # })) # This is complex and might not work directly
        )
        self.logger = logging.getLogger(__name__ + ".OpenRouterClient")

    async def __aenter__(self):
        """Ensure session manager is entered."""
        await self.session_manager.__aenter__()
        # self.openrouter_client is not defined in OpenRouterClient, it's self.http_client
        # if self.openrouter_client:
        #     await self.openrouter_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close Redis connection and ensure session manager and OpenRouter client are exited."""
        if self.redis_client:
            await self.redis_client.close() # Corrected: Use self.redis_client.close()
        # self.openrouter_client is not defined in OpenRouterClient, it's self.http_client
        # if self.openrouter_client:
        #     await self.openrouter_client.__aexit__(exc_type, exc_val, exc_tb)
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
            # Use resilience manager for the actual API call
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.http_client.chat.completions.create( # Use self.http_client
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"} # Request JSON response if possible
                ),
                url=self.base_url # Use base_url for circuit breaker naming
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
    def __init__(self, database: Database, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, redis_client: Optional[redis.Redis] = None): # Added redis_client
        self.logger = logging.getLogger(__name__)
        self.db = database # Store database instance
        self.enabled = config_loader.get("ai.enabled", False)
        self.openrouter_api_key = config_loader.get("ai.openrouter_api_key")
        self.models = config_loader.get("ai.models", {})
        self.session_manager = session_manager # Store the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to AIService. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to AIService. Falling back to global instance.")
        self.redis_client = redis_client # Stored redis_client


        if self.enabled and not self.openrouter_api_key:
            self.logger.warning("AI integration is enabled but OpenRouter API key is missing. AI features will be disabled.")
            self.enabled = False

        if self.enabled:
            self.openrouter_client = OpenRouterClient(api_key=self.openrouter_api_key, session_manager=self.session_manager, resilience_manager=self.resilience_manager, redis_client=self.redis_client)
            # Removed: self.redis_client = redis.Redis(connection_pool=redis.ConnectionPool.from_url(config_loader.get("redis.url")))
            self.logger.info("AI Service initialized and enabled.")
        else:
            self.logger.info("AI Service is disabled by configuration.")
            self.openrouter_client = None
            self.redis_client = None

        self.allow_live = config_loader.get("ai.ai_service.allow_live", False)
        self.staleness_threshold = timedelta(hours=config_loader.get("ai.ai_service.staleness_threshold_hours", 24))

    async def __aenter__(self):
        """Ensure session manager and OpenRouter client are entered."""
        await self.session_manager.__aenter__()
        if self.openrouter_client:
            await self.openrouter_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close Redis connection and ensure session manager and OpenRouter client are exited."""
        if self.redis_client:
            await self.redis_client.close() # Corrected: Use self.redis_client.close()
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

    async def score_content(self, content: str, target_keyword: str, source: str = "cache") -> Dict[str, Any]:
        """
        Analyzes content for SEO optimization and provides a score and suggestions.
        Returns a dictionary with seo_score, keyword_density_score, readability_score,
        semantic_keywords, and improvement_suggestions.
        """
        cache_key = f"ai_content_score:{target_keyword}:{hash(content)}"
        
        # For AI services, we'll primarily use the internal Redis cache for "cache" source.
        # Live calls will bypass this cache and update it.
        if source == "cache":
            cached_result = await self._call_ai_with_cache("content_scoring", "", cache_key) # Pass empty prompt for cache check
            if cached_result:
                return cached_result

        if not self.allow_live and source == "live":
            self.logger.warning("Live AI content scoring not allowed by configuration. Returning default scores.")
            return {
                "seo_score": 50,
                "keyword_density_score": 50,
                "readability_score": 50,
                "semantic_keywords": [],
                "improvement_suggestions": ["AI analysis unavailable."],
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }

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
        result = await self._call_ai_with_cache("content_scoring", prompt, cache_key, max_tokens=1500)
        
        if result is None:
            self.logger.warning(f"AI content scoring failed for keyword '{target_keyword}'. Returning default scores.")
            return {
                "seo_score": 50,
                "keyword_density_score": 50,
                "readability_score": 50,
                "semantic_keywords": [],
                "improvement_suggestions": ["AI analysis unavailable."],
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }
        result['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
        return result

    async def classify_content(self, content: str, target_keyword: str, source: str = "cache") -> Optional[str]:
        """
        Classifies the content based on its quality and relevance to a target keyword.
        Possible classifications: "high_quality", "low_quality", "spam", "irrelevant".
        """
        cache_key = f"ai_content_classification:{target_keyword}:{hash(content)}"
        if source == "cache":
            cached_result = await self._call_ai_with_cache("content_classification", "", cache_key)
            if cached_result and "classification" in cached_result:
                return cached_result["classification"]

        if not self.allow_live and source == "live":
            self.logger.warning("Live AI content classification not allowed by configuration. Returning None.")
            return None

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
        result = await self._call_ai_with_cache("content_classification", prompt, cache_key, max_tokens=50) # Small max_tokens for single word
        
        if result and "classification" in result:
            classification = result["classification"].lower()
            if classification in ["high_quality", "low_quality", "spam", "irrelevant"]:
                self.logger.info(f"Content classified as: {classification}")
                result['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
                return classification
            else:
                self.logger.warning(f"AI returned unexpected classification: {classification}. Defaulting to 'unknown'.")
                return "unknown"
        self.logger.warning(f"AI content classification failed for keyword '{target_keyword}'. Returning None.")
        return None

    async def analyze_content_gaps(self, target_url: str, competitor_urls: List[str], source: str = "cache") -> ContentGapAnalysisResult:
        """
        Analyzes content gaps between a target URL and its competitors.
        Returns a ContentGapAnalysisResult object with insights.
        """
        cached_result = self.db.get_latest_content_gap_analysis_result(target_url)
        now = datetime.utcnow()

        if source == "live" and self.allow_live:
            if not cached_result or (now - cached_result.last_fetched_at) > self.staleness_threshold:
                self.logger.info(f"Live fetch requested or cache stale for {target_url}. Fetching live content gap analysis.")
                live_result = await self._fetch_live_content_gap_analysis(target_url, competitor_urls)
                if live_result:
                    self.db.save_content_gap_analysis_result(live_result)
                    return live_result
                else:
                    self.logger.warning(f"Live fetch failed for {target_url}. Returning cached data if available.")
                    return cached_result
            else:
                self.logger.info(f"Live fetch requested for {target_url}, but cache is fresh. Fetching live anyway.")
                live_result = await self._fetch_live_content_gap_analysis(target_url, competitor_urls)
                if live_result:
                    self.db.save_content_gap_analysis_result(live_result)
                    return live_result
                else:
                    self.logger.warning(f"Live fetch failed for {target_url}. Returning cached data.")
                    return cached_result
        else:
            self.logger.info(f"Returning cached content gap analysis for {target_url}.")
            if cached_result:
                return cached_result
            else:
                self.logger.warning(f"No cached content gap analysis found for {target_url}. Returning empty result.")
                return ContentGapAnalysisResult(
                    target_url=target_url,
                    competitor_urls=competitor_urls,
                    missing_topics=[],
                    missing_keywords=[],
                    content_format_gaps=[],
                    actionable_insights=["No cached AI analysis available."],
                    last_fetched_at=datetime.utcnow() # Set last_fetched_at for new empty result
                )

    async def _fetch_live_content_gap_analysis(self, target_url: str, competitor_urls: List[str]) -> Optional[ContentGapAnalysisResult]:
        """
        Fetches content gap analysis directly from AI.
        """
        self.logger.info(f"Fetching LIVE content gap analysis for {target_url}.")
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
            self.logger.warning(f"AI content gap analysis failed for {target_url}. Returning None.")
            return None
        
        # Ensure lists are actual lists and not None
        result_dict["missing_topics"] = result_dict.get("missing_topics", [])
        result_dict["missing_keywords"] = result_dict.get("missing_keywords", [])
        result_dict["content_format_gaps"] = result_dict.get("content_format_gaps", [])
        result_dict["actionable_insights"] = result_dict.get("actionable_insights", [])

        return ContentGapAnalysisResult(
            target_url=target_url,
            competitor_urls=competitor_urls,
            last_fetched_at=datetime.utcnow(), # Set last_fetched_at for live data
            **result_dict
        )

    async def perform_topic_clustering(self, texts: List[str], num_clusters: int = 5, source: str = "cache") -> Dict[str, List[str]]:
        """
        Simulates AI-powered topic clustering for a list of texts.
        Returns a dictionary where keys are cluster names/topics and values are lists of texts belonging to that cluster.
        """
        cache_key = f"ai_topic_clustering:{hash(tuple(texts))}:{num_clusters}"
        if source == "cache":
            cached_result = await self._call_ai_with_cache("topic_clustering", "", cache_key)
            if cached_result:
                return cached_result

        if not self.allow_live and source == "live":
            self.logger.warning("Live AI topic clustering not allowed by configuration. Returning simulated clusters.")
            return {
                "Simulated Topic 1": texts[:min(len(texts), 2)], 
                "Simulated Topic 2": texts[min(len(texts), 2):],
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }

        if not self.enabled or not self.openrouter_client:
            self.logger.warning("AI service is disabled. Cannot perform topic clustering. Returning simulated clusters.")
            return {
                "Simulated Topic 1": texts[:min(len(texts), 2)], 
                "Simulated Topic 2": texts[min(len(texts), 2):],
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }

        prompt = f"""
        Perform topic clustering on the following list of texts.
        Group them into {num_clusters} distinct topics.
        Provide a JSON response where keys are the topic names (e.g., "SEO Strategies", "Link Building")
        and values are lists of the original texts that belong to that cluster.
        
        Texts:
        {json.dumps(texts)}
        """
        result = await self._call_ai_with_cache("topic_clustering", prompt, cache_key, max_tokens=2000)

        if result is None:
            self.logger.warning("AI topic clustering failed. Returning simulated clusters.")
            # Fallback to a very basic simulation if AI call fails
            return {
                "General Topic A": texts[:len(texts)//2],
                "General Topic B": texts[len(texts)//2:],
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }
        
        # Validate and return the result
        # Ensure the result is a dictionary with list values
        cleaned_result = {}
        for key, value in result.items():
            if isinstance(key, str) and isinstance(value, list):
                cleaned_result[key] = [str(item) for item in value if isinstance(item, str)]
        cleaned_result['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
        return cleaned_result


    async def suggest_semantic_keywords(self, primary_keyword: str, source: str = "cache") -> List[str]:
        """
        Generates a list of semantically related keywords.
        """
        cache_key = f"ai_semantic_keywords:{primary_keyword}"
        if source == "cache":
            cached_result = await self._call_ai_with_cache("keyword_research", "", cache_key)
            if cached_result and "keywords" in cached_result:
                return cached_result["keywords"]

        if not self.allow_live and source == "live":
            self.logger.warning("Live AI semantic keyword suggestion not allowed by configuration. Returning empty list.")
            return []

        prompt = f"""
        Generate a list of 10-15 semantically related keywords for the primary keyword '{primary_keyword}'.
        Focus on long-tail variations, related concepts, and user intent.
        Provide the response as a JSON object with a single key "keywords" which is a list of strings.
        """
        result = await self._call_ai_with_cache("keyword_research", prompt, cache_key, max_tokens=500)
        
        if result is None:
            self.logger.warning(f"AI semantic keyword suggestion failed for '{primary_keyword}'.")
            return []
        result['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
        return result.get("keywords", [])

    async def analyze_technical_seo(self, url: str, html_content: str, lighthouse_report: Optional[Dict[str, Any]], source: str = "cache") -> Dict[str, Any]:
        """
        Analyzes technical SEO aspects of a page, combining HTML and Lighthouse data.
        """
        cache_key = f"ai_tech_seo:{url}:{hash(html_content[:1000])}" # Cache based on URL and partial content
        if source == "cache":
            cached_result = await self._call_ai_with_cache("technical_seo_analysis", "", cache_key)
            if cached_result:
                return cached_result

        if not self.allow_live and source == "live":
            self.logger.warning("Live AI technical SEO analysis not allowed by configuration. Returning default.")
            return {
                "technical_issues": [], 
                "technical_suggestions": [], 
                "overall_technical_score": 50,
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }

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
        result = await self._call_ai_with_cache("technical_seo_analysis", prompt, cache_key, max_tokens=1500)
        
        if result is None:
            self.logger.warning(f"AI technical SEO analysis failed for {url}.")
            return {
                "technical_issues": [], 
                "technical_suggestions": [], 
                "overall_technical_score": 50,
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }
        result['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
        return result

    async def analyze_competitors(self, primary_domain: str, competitor_domains: List[str], source: str = "cache") -> Dict[str, Any]:
        """
        Analyzes competitor strategies based on their domains.
        """
        cache_key = f"ai_competitor_analysis:{primary_domain}:{hash(tuple(competitor_domains))}"
        if source == "cache":
            cached_result = await self._call_ai_with_cache("competitor_analysis", "", cache_key)
            if cached_result:
                return cached_result

        if not self.allow_live and source == "live":
            self.logger.warning("Live AI competitor analysis not allowed by configuration. Returning default.")
            return {
                "competitor_strengths": {}, 
                "competitor_weaknesses": {}, 
                "strategic_recommendations": ["AI analysis unavailable."],
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }

        prompt = f"""
        Analyze the competitive landscape for '{primary_domain}' against these competitors: {', '.join(competitor_domains)}.
        Based on general SEO knowledge and common strategies, provide a JSON response with:
        - "competitor_strengths": Dict of competitor_domain -> list of strengths.
        - "competitor_weaknesses": Dict of competitor_domain -> list of weaknesses.
        - "strategic_recommendations": List of strategic recommendations for the primary domain.
        """
        result = await self._call_ai_with_cache("competitor_analysis", prompt, cache_key, max_tokens=1500)
        
        if result is None:
            self.logger.warning(f"AI competitor analysis failed for {primary_domain}.")
            return {
                "competitor_strengths": {}, 
                "competitor_weaknesses": {}, 
                "strategic_recommendations": ["AI analysis unavailable."],
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }
        result['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
        return result

    async def generate_content_ideas(self, topic: str, num_ideas: int = 5, source: str = "cache") -> List[str]:
        """
        Generates content ideas for a given topic.
        """
        cache_key = f"ai_content_ideas:{topic}:{num_ideas}"
        if source == "cache":
            cached_result = await self._call_ai_with_cache("content_generation", "", cache_key)
            if cached_result and "ideas" in cached_result:
                return cached_result["ideas"]

        if not self.allow_live and source == "live":
            self.logger.warning("Live AI content idea generation not allowed by configuration. Returning empty list.")
            return []

        prompt = f"""
        Generate {num_ideas} unique and engaging content ideas for the topic '{topic}'.
        Focus on ideas that are SEO-friendly and address user intent.
        Provide the response as a JSON object with a single key "ideas" which is a list of strings.
        """
        result = await self._call_ai_with_cache("content_generation", prompt, cache_key, max_tokens=1000)
        
        if result is None:
            self.logger.warning(f"AI content idea generation failed for '{topic}'.")
            return []
        result['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
        return result.get("ideas", [])

    async def analyze_domain_value(self, domain_name: str, domain_info: Optional[Domain], link_profile_summary: Optional[LinkProfile], source: str = "cache") -> Dict[str, Any]:
        """
        Performs an AI-driven analysis of a domain's value, combining various data points.
        """
        # For domain value, we might not cache the AI result directly in Redis,
        # but rather store the DomainIntelligence object in the DB.
        # So, for "cache" source, we'd retrieve from DB.
        cached_domain_intelligence = self.db.get_domain_intelligence(domain_name)
        now = datetime.utcnow()

        if source == "live" and self.allow_live:
            if not cached_domain_intelligence or (now - cached_domain_intelligence.last_fetched_at) > self.staleness_threshold:
                self.logger.info(f"Live fetch requested or cache stale for {domain_name}. Fetching live AI domain value analysis.")
                live_result = await self._fetch_live_domain_value_analysis(domain_name, domain_info, link_profile_summary)
                if live_result:
                    # Update DomainIntelligence in DB (handled by DomainAnalyzerService)
                    return live_result
                else:
                    self.logger.warning(f"Live fetch failed for {domain_name}. Returning cached data if available.")
                    return cached_domain_intelligence.to_dict() if cached_domain_intelligence else {"value_adjustment": 0, "reasons": ["No cached AI analysis available."], "details": {}, "last_fetched_at": datetime.utcnow().isoformat()}
            else:
                self.logger.info(f"Live fetch requested for {domain_name}, but cache is fresh. Fetching live anyway.")
                live_result = await self._fetch_live_domain_value_analysis(domain_name, domain_info, link_profile_summary)
                if live_result:
                    return live_result
                else:
                    self.logger.warning(f"Live fetch failed for {domain_name}. Returning cached data.")
                    return cached_domain_intelligence.to_dict() if cached_domain_intelligence else {"value_adjustment": 0, "reasons": ["No cached AI analysis available."], "details": {}, "last_fetched_at": datetime.utcnow().isoformat()}
        else:
            self.logger.info(f"Returning cached AI domain value analysis for {domain_name}.")
            if cached_domain_intelligence:
                return cached_domain_intelligence.to_dict()
            else:
                self.logger.warning(f"No cached AI domain value analysis found for {domain_name}. Returning default.")
                return {"value_adjustment": 0, "reasons": ["No cached AI analysis available."], "details": {}, "last_fetched_at": datetime.utcnow().isoformat()}

    async def _fetch_live_domain_value_analysis(self, domain_name: str, domain_info: Optional[Domain], link_profile_summary: Optional[LinkProfile]) -> Dict[str, Any]:
        """
        Fetches AI domain value analysis directly from AI.
        """
        self.logger.info(f"Fetching LIVE AI domain value analysis for {domain_name}.")
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
            return {"value_adjustment": 0, "reasons": ["AI analysis unavailable."], "details": {}, "last_fetched_at": datetime.utcnow().isoformat()}
        result['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
        return result

    async def analyze_content_nlp(self, content: str, source: str = "cache") -> Dict[str, Any]:
        """
        Performs Natural Language Processing (NLP) on content to extract entities, sentiment, and topics.
        Returns a dictionary with "entities", "sentiment", and "topics".
        """
        cache_key = f"ai_content_nlp:{hash(content)}"
        if source == "cache":
            cached_result = await self._call_ai_with_cache("content_nlp_analysis", "", cache_key)
            if cached_result:
                return cached_result

        if not self.allow_live and source == "live":
            self.logger.warning("Live AI content NLP analysis not allowed by configuration. Returning default.")
            return {
                "entities": [],
                "sentiment": "neutral",
                "topics": [],
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }

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
        result = await self._call_ai_with_cache("content_nlp_analysis", prompt, cache_key, max_tokens=700)
        
        if result is None:
            self.logger.warning("AI content NLP analysis failed. Returning default empty results.")
            return {
                "entities": [],
                "sentiment": "neutral",
                "topics": [],
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }
        
        # Validate and clean up the response
        result["entities"] = [str(e) for e in result.get("entities", []) if isinstance(e, str)][:10]
        result["topics"] = [str(t) for t in result.get("topics", []) if isinstance(t, str)][:5]
        sentiment = result.get("sentiment", "neutral").lower()
        if sentiment not in ["positive", "neutral", "negative"]:
            sentiment = "neutral"
        result["sentiment"] = sentiment
        result['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
        return result

    async def analyze_video_content(self, video_url: str, video_data: Optional[bytes] = None, 
                                  max_frames: int = 10, source: str = "cache") -> Dict[str, Any]:
        """
        Real video content analysis using OpenAI Vision API.
        Extracts frames from video and analyzes them with GPT-4 Vision.
        
        Args:
            video_url: URL of the video
            video_data: Raw video bytes (optional)
            max_frames: Maximum number of frames to extract and analyze
            
        Returns:
            Dictionary with transcription, topics, and analysis
        """
        # Video analysis results are not typically cached in Redis directly,
        # but might be part of a larger CrawlResult or DomainIntelligence object.
        # For simplicity, we'll treat this as a live-only operation for now,
        # but respect the allow_live flag.
        if not self.allow_live and source == "live":
            self.logger.warning("Live AI video analysis not allowed by configuration. Returning empty result.")
            return {
                "transcription": "",
                "topics": [],
                "timeline": [],
                "summary": "AI video analysis disabled",
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }

        if not self.enabled or not self.openrouter_client:
            self.logger.warning("AI service is disabled. Cannot analyze video content. Returning empty result.")
            return {
                "transcription": "",
                "topics": [],
                "timeline": [],
                "summary": "AI service disabled",
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }
        
        # Download video if only URL provided
        if video_data is None and video_url:
            video_data = await self._download_video(video_url)
        
        if not video_data:
            raise ValueError("No video data available for analysis")
        
        # Extract frames from video
        frames = await self._extract_video_frames(video_data, max_frames)
        
        if not frames:
            raise ValueError("No frames could be extracted from video")
        
        # Analyze frames with Vision API
        analysis_results = []
        for i, frame in enumerate(frames):
            frame_analysis = await self._analyze_video_frame(frame, i)
            if frame_analysis:
                analysis_results.append(frame_analysis)
        
        # Synthesize results
        result = await self._synthesize_video_analysis(analysis_results, video_url)
        result['last_fetched_at'] = datetime.utcnow().isoformat() # Set last_fetched_at for live data
        return result
    
    async def _download_video(self, video_url: str) -> Optional[bytes]:
        """Download video from URL."""
        try:
            async with self.session_manager.get(video_url, timeout=60) as response:
                response.raise_for_status()
                return await response.read()
        except Exception as e:
            self.logger.error(f"Error downloading video from {video_url}: {e}")
            return None
    
    async def _extract_video_frames(self, video_data: bytes, max_frames: int) -> List[bytes]:
        """Extract frames from video using OpenCV."""
        frames = []
        
        # Save video data to temporary file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(video_data)
            temp_path = temp_file.name
        
        try:
            # Open video with OpenCV
            cap = cv2.VideoCapture(temp_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames == 0:
                return frames
            
            # Calculate frame interval
            interval = max(1, total_frames // max_frames)
            
            frame_count = 0
            while len(frames) < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_count % interval == 0:
                    # Convert frame to JPEG bytes
                    _, buffer = cv2.imencode('.jpg', frame)
                    frames.append(buffer.tobytes())
                
                frame_count += 1
            
            cap.release()
            
        except Exception as e:
            self.logger.error(f"Error extracting video frames: {e}")
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
        
        return frames
    
    async def _analyze_video_frame(self, frame_data: bytes, frame_index: int) -> Optional[Dict[str, Any]]:
        """Analyze a single video frame with Vision API."""
        try:
            # Encode frame as base64
            frame_b64 = base64.b64encode(frame_data).decode('utf-8')
            
            prompt = f"""
            Analyze this video frame (frame #{frame_index}). Describe:
            1. What objects, people, or text you see
            2. Any actions or activities taking place
            3. The setting or environment
            4. Any text that appears on screen
            
            Provide response as JSON with keys: objects, actions, setting, text_content
            """
            
            # Make API call with image
            response = await self.openrouter_client.http_client.chat.completions.create(
                model=self.models.get("video_frame_analysis", "openai/gpt-4o"),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{frame_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            content = response.choices[0].message.content
            import json
            parsed_content = json.loads(content)
            parsed_content['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
            return parsed_content
            
        except Exception as e:
            self.logger.error(f"Error analyzing video frame {frame_index}: {e}")
            return None
    
    async def _synthesize_video_analysis(self, frame_analyses: List[Dict[str, Any]], 
                                       video_url: str) -> Dict[str, Any]:
        """Synthesize individual frame analyses into comprehensive video analysis."""
        if not frame_analyses:
            return {
                "transcription": "",
                "topics": [],
                "timeline": [],
                "summary": "No analysis data available",
                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
            }
        
        # Combine all text content found in frames
        all_text = []
        all_objects = []
        all_actions = []
        timeline = []
        
        for i, analysis in enumerate(frame_analyses):
            if analysis.get('text_content'):
                all_text.append(analysis['text_content'])
            if analysis.get('objects'):
                all_objects.extend(analysis['objects'])
            if analysis.get('actions'):
                all_actions.extend(analysis['actions'])
            
            # Build timeline
            timeline.append({
                "frame": i,
                "timestamp": f"{i*2}s",  # Approximate 2 seconds per frame
                "description": f"{analysis.get('setting', '')} - {analysis.get('actions', '')}"
            })
        
        # Extract unique topics
        topics = list(set(all_objects + all_actions))
        
        # Generate summary
        summary_prompt = f"""
        Based on the following video frame analyses, provide a comprehensive summary:
        
        Objects seen: {', '.join(set(all_objects))}
        Actions observed: {', '.join(set(all_actions))}
        Text found: {', '.join(all_text)}
        
        Provide a coherent summary of what this video appears to be about.
        """
        
        summary = await self._call_ai_with_cache(
            "content_generation", 
            summary_prompt, 
            f"video_summary:{hash(str(frame_analyses))}"
        )
        
        return {
            "transcription": ' '.join(all_text),
            "topics": topics[:10],  # Limit to top 10 topics
            "timeline": timeline,
            "summary": summary.get('summary', 'Video analysis completed') if summary else "Analysis completed",
            "objects_detected": list(set(all_objects)),
            "actions_detected": list(set(all_actions)),
            "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
        }

    async def assess_content_quality(self, content: str, url: str, source: str = "cache") -> Tuple[Optional[float], Optional[str]]:
        """
        Assesses the quality of the given content and provides a classification.
        Returns a tuple of (quality_score, classification_string).
        """
        cache_key = f"ai_content_quality_assessment:{url}:{hash(content[:1000])}" # Cache based on URL and partial content
        if source == "cache":
            cached_result = await self._call_ai_with_cache("content_quality_assessment", "", cache_key)
            if cached_result:
                score = cached_result.get("quality_score")
                classification = cached_result.get("classification")
                if isinstance(score, (int, float)) and isinstance(classification, str):
                    return float(score), classification
                
        if not self.allow_live and source == "live":
            self.logger.warning("Live AI content quality assessment not allowed by configuration. Returning None, None.")
            return None, None

        if not self.enabled or not self.openrouter_client:
            self.logger.warning("AI service is disabled. Cannot assess content quality. Returning None, None.")
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
        result = await self._call_ai_with_cache("content_quality_assessment", prompt, cache_key, max_tokens=200)
        
        if result:
            score = result.get("quality_score")
            classification = result.get("classification")
            if isinstance(score, (int, float)) and isinstance(classification, str):
                classification = classification.lower()
                if classification not in ["excellent", "good", "average", "low_quality", "spam"]:
                    classification = "average" # Default to average if AI gives unexpected classification
                self.logger.info(f"Content quality for {url}: Score={score}, Classification={classification}")
                result['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
                return float(score), classification
            else:
                self.logger.warning(f"AI returned invalid format for content quality assessment for {url}: {result}")
        self.logger.warning(f"AI content quality assessment failed for {url}. Returning None, None.")
        return None, None
