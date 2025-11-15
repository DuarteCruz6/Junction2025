"""
Translation Service
Handles translation of captions from detected language to target language
Uses OpenAI API for language detection and translation
"""

import os
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
import asyncio

load_dotenv()

class TranslationService:
    """Service for translating captions to target language"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[Translation] ⚠️  WARNING: OPENAI_API_KEY not found in environment variables", flush=True)
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.default_target_language = "en"  # Default target language is English
        self.model = "gpt-4o-mini"  # Use same model as LLM service for consistency
        
        # Cache for language detection (to avoid redundant API calls)
        self._language_cache: Dict[str, str] = {}
        
    async def translate_text(
        self,
        text: str,
        target_language: Optional[str] = None,
        source_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Translate text to target language
        
        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'en', 'pt', 'es'). Defaults to 'en'
            source_language: Source language code (optional, auto-detected if not provided)
            
        Returns:
            Dict with:
            - success: bool
            - translated_text: str (original text if translation not needed/failed)
            - detected_language: str (detected source language)
            - target_language: str
            - error: str (if failed)
        """
        try:
            # Check if client is initialized
            if not self.client:
                error_msg = "OpenAI API client not initialized (missing OPENAI_API_KEY)"
                print(f"[Translation] ❌ {error_msg}", flush=True)
                return {
                    "success": False,
                    "translated_text": text,  # Return original text if translation fails
                    "detected_language": None,
                    "target_language": target_language or self.default_target_language,
                    "error": error_msg,
                }
            
            # Validate input
            if not text or not isinstance(text, str) or not text.strip():
                return {
                    "success": False,
                    "translated_text": text,
                    "detected_language": None,
                    "target_language": target_language or self.default_target_language,
                    "error": "Empty text",
                }
            
            # Use default target language if not provided
            target_lang = target_language or self.default_target_language
            
            # Detect language if not provided
            detected_lang = source_language
            if not detected_lang:
                detected_lang = await self.detect_language(text)
            
            # If detected language is already target language, no translation needed
            if detected_lang and detected_lang.lower() == target_lang.lower():
                return {
                    "success": True,
                    "translated_text": text,  # Return original text if already in target language
                    "detected_language": detected_lang,
                    "target_language": target_lang,
                    "translation_needed": False,
                }
            
            # Skip translation if text is very short (likely noise or partial word)
            if len(text.strip()) < 3:
                return {
                    "success": True,
                    "translated_text": text,  # Return original text for very short text
                    "detected_language": detected_lang,
                    "target_language": target_lang,
                    "translation_needed": False,
                }
            
            # Translate text
            print(f"[Translation] 🌐 Translating from {detected_lang or 'unknown'} to {target_lang}: {text[:50]}...", flush=True)
            
            # Use OpenAI for translation (simple and effective)
            prompt = f"""Translate the following text to {target_lang} (ISO 639-1 language code). 
Return only the translated text, nothing else.

Text to translate: {text}

Translated text:"""
            
            # Run translation in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": f"You are a professional translator. Translate text to {target_lang}. Return only the translation, no explanations."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,  # Low temperature for consistent translations
                    max_tokens=500,  # Should be enough for captions
                )
            )
            
            translated_text = response.choices[0].message.content.strip()
            
            # Validate translation (should not be empty)
            if not translated_text:
                print(f"[Translation] ⚠️  Empty translation, using original text", flush=True)
                translated_text = text
            
            print(f"[Translation] ✅ Translation complete: {translated_text[:50]}...", flush=True)
            
            return {
                "success": True,
                "translated_text": translated_text,
                "detected_language": detected_lang,
                "target_language": target_lang,
                "translation_needed": True,
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"[Translation] ❌ Error translating text: {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            # Return original text on error (fail gracefully)
            return {
                "success": False,
                "translated_text": text,  # Return original text on error
                "detected_language": detected_lang if 'detected_lang' in locals() else None,
                "target_language": target_lang if 'target_lang' in locals() else (target_language or self.default_target_language),
                "error": error_msg,
            }
    
    def _is_likely_english(self, text: str) -> bool:
        """
        Quick heuristic to check if text is likely English (no API call)
        Uses simple patterns to detect English words
        """
        if not text or len(text.strip()) < 2:
            return True  # Default to English for very short text
        
        # Common English words (most frequent)
        common_english = {
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
            'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
            'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
            'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
            'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me',
            'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know', 'take'
        }
        
        # Extract words (simple, lowercase)
        words = text.lower().split()
        if not words:
            return True
        
        # Check if majority of words are common English words
        english_word_count = sum(1 for word in words if word.strip('.,!?;:"()[]{}') in common_english)
        total_words = len(words)
        
        # If at least 30% are common English words, likely English
        if total_words > 0 and english_word_count / total_words >= 0.3:
            return True
        
        # Check for common English patterns
        english_patterns = ['the ', 'and ', 'you ', 'that ', 'this ', 'with ', 'from ', 'have ', 'were ', 'would ']
        text_lower = text.lower()
        pattern_matches = sum(1 for pattern in english_patterns if pattern in text_lower)
        
        if pattern_matches >= 1:
            return True
        
        return False
    
    async def detect_language(self, text: str) -> Optional[str]:
        """
        Detect language of text
        
        Args:
            text: Text to detect language for
            
        Returns:
            Language code (ISO 639-1) or None if detection fails
        """
        try:
            # Check cache first (for common short texts)
            if text in self._language_cache:
                return self._language_cache[text]
            
            # Validate input
            if not text or not isinstance(text, str) or len(text.strip()) < 2:
                return None
            
            # Quick heuristic check first (no API call)
            if self._is_likely_english(text):
                self._language_cache[text] = 'en'
                return 'en'
            
            # If client not initialized, assume English
            if not self.client:
                return 'en'
            
            # Use OpenAI for language detection (only if heuristic suggests non-English)
            prompt = f"""What language is this text written in? Return only the ISO 639-1 language code (e.g., 'en', 'pt', 'es', 'fr', 'de', etc.). 
If you cannot determine the language, return 'unknown'.

Text: {text}

Language code:"""
            
            # Run detection in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a language detection expert. Return only ISO 639-1 language codes."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,  # Very low temperature for consistent detection
                    max_tokens=10,  # Just need language code
                )
            )
            
            detected_code = response.choices[0].message.content.strip().lower()
            
            # Validate language code (should be 2-3 characters, alphabetic)
            if detected_code and detected_code != "unknown" and len(detected_code) <= 3 and detected_code.isalpha():
                # Cache result for short texts
                if len(text) < 100:
                    self._language_cache[text] = detected_code
                return detected_code
            
            # Default to English if detection fails
            return 'en'
            
        except Exception as e:
            print(f"[Translation] ⚠️  Error detecting language: {e}", flush=True)
            return 'en'  # Default to English on error
    
    def get_target_language_for_user(self, user_id: Optional[str] = None) -> str:
        """
        Get target language for user from settings
        
        Args:
            user_id: User ID (optional)
            
        Returns:
            Target language code (defaults to 'en')
        """
        if not user_id:
            return self.default_target_language
        
        try:
            from models.database import UserSettings, SessionLocal
            if SessionLocal:
                db = SessionLocal()
                try:
                    user_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
                    if user_settings and user_settings.preferred_language:
                        return user_settings.preferred_language
                finally:
                    db.close()
        except Exception as e:
            print(f"[Translation] ⚠️  Could not retrieve user settings: {e}", flush=True)
        
        return self.default_target_language


# Singleton instance
print("[Translation] 🚀 Creating Translation Service singleton instance...")
translation_service = TranslationService()
print("[Translation] ✅ Translation Service singleton ready")

