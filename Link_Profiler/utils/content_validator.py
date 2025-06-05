import re
import html
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import logging
from bs4 import BeautifulSoup # Added for HTML parsing

logger = logging.getLogger(__name__)

class ContentValidator:
    """Real content validation with actual analysis algorithms."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".ContentValidator")
        
        # Spam indicators
        self.spam_keywords = {
            'high_risk': ['buy now', 'act fast', 'limited time', 'click here', 'free money'],
            'medium_risk': ['discount', 'sale', 'offer', 'deal', 'bonus'],
            'low_risk': ['cheap', 'best', 'top', 'amazing', 'incredible']
        }
        
        # Content quality indicators
        self.quality_indicators = {
            'positive': ['analysis', 'research', 'study', 'comprehensive', 'detailed'],
            'negative': ['lorem ipsum', 'placeholder', 'dummy', 'test content']
        }

        # Bot detection phrases
        self.bot_detection_phrases = [
            "access denied", "you have been blocked", "captcha", "robot check",
            "rate limit exceeded", "please verify you are human", "403 forbidden",
            "too many requests", "cloudflare" # Cloudflare often indicates bot protection
        ]
        # Minimum content length for a "meaningful" page (can be configured)
        self.min_meaningful_content_length = 500 # characters
    
    def validate_content_quality(self, content: str, url: str) -> Dict[str, Any]:
        """
        Real content quality validation with multiple metrics.
        
        Returns:
            Dictionary with quality scores and indicators
        """
        if not content or not content.strip():
            return {
                'quality_score': 0,
                'issues': ['Empty content'],
                'word_count': 0,
                'readability_score': 0,
                'spam_score': 0,
                'bot_detection_indicators': []
            }
        
        # Clean content
        clean_content = self._clean_html(content)
        
        # Calculate metrics
        word_count = len(clean_content.split())
        readability = self._calculate_readability(clean_content)
        spam_score = self._calculate_spam_score(clean_content)
        duplicate_score = self._check_duplicate_content(clean_content)
        bot_indicators = self.detect_bot_indicators(content) # Use raw content for bot detection
        
        # Determine overall quality
        quality_score = self._calculate_quality_score(
            word_count, readability, spam_score, duplicate_score
        )
        
        # Identify issues
        issues = self._identify_content_issues(clean_content, url)
        if bot_indicators:
            issues.extend([f"Bot detection indicator found: '{indicator}'" for indicator in bot_indicators])
        
        return {
            'quality_score': quality_score,
            'word_count': word_count,
            'readability_score': readability,
            'spam_score': spam_score,
            'duplicate_score': duplicate_score,
            'issues': issues,
            'content_hash': hashlib.md5(clean_content.encode()).hexdigest(),
            'bot_detection_indicators': bot_indicators
        }
    
    def _clean_html(self, content: str) -> str:
        """Remove HTML tags and decode entities."""
        # Remove script and style elements
        content = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', content, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)
        
        # Decode HTML entities
        content = html.unescape(content)
        
        # Clean up whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        return content
    
    def _calculate_readability(self, content: str) -> float:
        """
        Calculate readability score using Flesch Reading Ease formula.
        """
        sentences = len(re.findall(r'[.!?]+', content))
        words = len(content.split())
        syllables = self._count_syllables(content)
        
        if sentences == 0 or words == 0:
            return 0
        
        # Flesch Reading Ease formula
        score = 206.835 - (1.015 * (words / sentences)) - (84.6 * (syllables / words))
        
        # Normalize to 0-100
        return max(0, min(100, score))
    
    def _count_syllables(self, text: str) -> int:
        """Estimate syllable count for readability calculation."""
        words = text.lower().split()
        syllable_count = 0
        
        for word in words:
            # Remove punctuation
            word = re.sub(r'[^a-z]', '', word)
            if not word:
                continue
            
            # Count vowel groups
            vowels = 'aeiouy'
            syllables = 0
            prev_was_vowel = False
            
            for char in word:
                is_vowel = char in vowels
                if is_vowel and not prev_was_vowel:
                    syllables += 1
                prev_was_vowel = is_vowel
            
            # Adjust for silent e
            if word.endswith('e') and syllables > 1:
                syllables -= 1
            
            # Minimum one syllable per word
            syllables = max(1, syllables)
            syllable_count += syllables
        
        return syllable_count
    
    def _calculate_spam_score(self, content: str) -> float:
        """Calculate spam score based on keyword analysis."""
        content_lower = content.lower()
        spam_score = 0
        
        # Check for spam keywords
        for risk_level, keywords in self.spam_keywords.items():
            multiplier = {'high_risk': 3, 'medium_risk': 2, 'low_risk': 1}[risk_level]
            
            for keyword in keywords:
                count = content_lower.count(keyword)
                spam_score += count * multiplier
        
        # Check for excessive capitalization
        caps_ratio = sum(1 for c in content if c.isupper()) / len(content) if content else 0
        if caps_ratio > 0.3:  # More than 30% caps
            spam_score += 10
        
        # Check for excessive punctuation
        punct_ratio = sum(1 for c in content if c in '!?') / len(content) if content else 0
        if punct_ratio > 0.05:  # More than 5% exclamation/question marks
            spam_score += 5
        
        # Normalize to 0-100
        return min(100, spam_score)
    
    def _check_duplicate_content(self, content: str) -> float:
        """Check for duplicate/repetitive content patterns."""
        if not content:
            return 0
        
        words = content.split()
        if len(words) < 10:
            return 0
        
        # Check for repeated phrases
        duplicate_score = 0
        phrase_counts = {}
        
        # Check 3-word phrases
        for i in range(len(words) - 2):
            phrase = ' '.join(words[i:i+3]).lower()
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
        
        # Calculate duplication percentage
        total_phrases = len(phrase_counts)
        duplicated_phrases = sum(1 for count in phrase_counts.values() if count > 1)
        
        if total_phrases > 0:
            duplicate_score = (duplicated_phrases / total_phrases) * 100
        
        return duplicate_score
    
    def _calculate_quality_score(self, word_count: int, readability: float, 
                               spam_score: float, duplicate_score: float) -> float:
        """Calculate overall content quality score."""
        # Base score from word count
        if word_count < 50:
            length_score = 0
        elif word_count < 200:
            length_score = 30
        elif word_count < 500:
            length_score = 60
        elif word_count < 1000:
            length_score = 80
        else:
            length_score = 100
        
        # Readability contribution (0-40 points)
        readability_contribution = (readability / 100) * 40
        
        # Penalties for spam and duplication
        spam_penalty = (spam_score / 100) * 30
        duplicate_penalty = (duplicate_score / 100) * 20
        
        # Final score
        quality_score = (length_score * 0.4) + (readability_contribution * 0.6) - spam_penalty - duplicate_penalty
        
        return max(0, min(100, quality_score))
    
    def _identify_content_issues(self, content: str, url: str) -> List[str]:
        """Identify specific content issues."""
        issues = []
        
        # Check for placeholder content
        placeholder_patterns = [
            r'lorem ipsum',
            r'placeholder',
            r'dummy text',
            r'test content',
            r'sample text'
        ]
        
        content_lower = content.lower()
        for pattern in placeholder_patterns:
            if re.search(pattern, content_lower):
                issues.append(f"Contains placeholder content: {pattern}")
        
        # Check for thin content
        if len(content.split()) < 100:
            issues.append("Thin content (less than 100 words)")
        
        # Check for excessive keyword repetition
        words = content.split()
        if words:
            word_freq = {}
            for word in words:
                word = word.lower().strip('.,!?";')
                if len(word) > 3:  # Only count meaningful words
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Find words that appear too frequently
            total_words = len(words)
            for word, count in word_freq.items():
                if count / total_words > 0.05:  # More than 5% of content
                    issues.append(f"Excessive keyword repetition: '{word}' ({count} times)")
        
        # Check for broken internal structure
        if not re.search(r'[.!?]', content):
            issues.append("No sentence-ending punctuation found")
        
        return issues

    def detect_bot_indicators(self, html_content: str) -> List[str]:
        """
        Detects common phrases or patterns indicating bot detection.
        """
        found_indicators = []
        content_lower = html_content.lower()
        
        for phrase in self.bot_detection_phrases:
            if phrase in content_lower:
                found_indicators.append(phrase)
        
        # Check for specific HTML elements often used in CAPTCHAs or blocks
        if re.search(r'<div[^>]*id=["\']g-recaptcha["\']', html_content):
            found_indicators.append("reCAPTCHA element")
        if re.search(r'<title>attention required! | cloudflare</title>', content_lower):
            found_indicators.append("Cloudflare 'Attention Required' page")

        # Check content completeness/quality (moved from validate_crawl_result)
        content_completeness_issues = self.check_content_completeness(html_content)
        if content_completeness_issues:
            found_indicators.extend(content_completeness_issues)
        
        # Check for common scraping artifacts (moved from validate_crawl_result)
        scraping_artifacts = self.detect_scraping_artifacts(html_content)
        if scraping_artifacts:
            found_indicators.extend([f"Scraping artifact detected: '{artifact}'" for artifact in scraping_artifacts])

        return found_indicators

    def check_content_completeness(self, html_content: str) -> List[str]:
        """
        Checks if the content appears to be complete and meaningful.
        This is a heuristic and might need tuning.
        """
        issues = []
        
        # Remove HTML tags to get plain text for length check
        soup = BeautifulSoup(html_content, 'lxml')
        text_content = soup.get_text(separator=' ', strip=True)
        
        if len(text_content) < self.min_meaningful_content_length:
            issues.append(f"Content is unusually short ({len(text_content)} characters), possibly incomplete or an error page.")
            
        # Check for common "empty page" or "loading" indicators
        if re.search(r'loading\.\.\.', text_content.lower()) and len(text_content) < 200:
            issues.append("Page contains 'loading...' text and is very short, possibly indicating incomplete load.")
        
        return issues

    def detect_scraping_artifacts(self, html_content: str) -> List[str]:
        """
        Identifies patterns that suggest the page was not fully loaded or rendered correctly,
        or contains anti-scraping placeholders.
        """
        issues = []
        content_lower = html_content.lower()

        # Common placeholder texts
        if "javascript is required" in content_lower:
            issues.append("Page requires JavaScript, content might be incomplete without rendering.")
        if "enable cookies" in content_lower:
            issues.append("Page requires cookies, content might be incomplete.")
        
        # Check for truncated HTML (very basic, might need more advanced parsing)
        if not html_content.strip().endswith(('</html>', '</body>')):
            # This is a very weak check, as content might be streamed or malformed.
            # More robust check would involve parsing and checking for unclosed tags.
            pass 
            
        return issues
