"""
Translation Service
Handles text translation from original language to target language (default: English)
Supports language detection and translation using deep-translator
Future-proof for user language preferences
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

try:
    from deep_translator import GoogleTranslator
    TRANSLATION_AVAILABLE = True
    print("[Translation] ✅ deep-translator library loaded successfully")
except ImportError as e:
    TRANSLATION_AVAILABLE = False
    print(f"[Translation] ⚠️  deep-translator not installed: {e}")
    print("[Translation] ⚠️  Translation will be disabled. Install with: pip install deep-translator")
except Exception as e:
    TRANSLATION_AVAILABLE = False
    print(f"[Translation] ⚠️  Error loading translation library: {e}")
    print("[Translation] ⚠️  Translation will be disabled.")


class TranslationService:
    """Service for translating text from original language to target language"""
    
    def __init__(self, default_target_language: str = "en"):
        """
        Initialize translation service
        
        Args:
            default_target_language: Default target language code (e.g., 'en' for English)
                                     Can be configured via env var TRANSLATION_TARGET_LANGUAGE
        """
        if not TRANSLATION_AVAILABLE:
            print("[Translation] ⚠️  Translation service not available (library not installed)")
            self.enabled = False
            return
        
        self.enabled = os.getenv("TRANSLATION_ENABLED", "true").lower() == "true"
        self.default_target_language = os.getenv(
            "TRANSLATION_TARGET_LANGUAGE", 
            default_target_language
        ).lower()
        
        print(f"[Translation] 🔧 Initializing Translation Service...")
        print(f"[Translation] ✅ Target language: {self.default_target_language}")
        print(f"[Translation] {'✅ Enabled' if self.enabled else '❌ Disabled'}")
    
    async def translate_text(
        self,
        text: str,
        target_language: Optional[str] = None,
        source_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Translate text from source language to target language
        
        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'en', 'pt', 'es')
                           If None, uses default_target_language
            source_language: Source language code (e.g., 'pt', 'es', 'fr')
                           If None, auto-detects language
            
        Returns:
            Dict with:
            - success: bool
            - translated_text: str (translated text, or original if already in target language)
            - detected_language: str (detected source language code)
            - target_language: str (target language used)
            - was_translated: bool (True if translation was performed, False if already in target language)
            - error: str (error message if failed)
        """
        # Always return original text as fallback if anything goes wrong
        fallback_result = {
            "success": True,
            "translated_text": text,
            "detected_language": None,
            "target_language": target_language or self.default_target_language,
            "was_translated": False,
            "error": None,
        }
        
        if not self.enabled or not TRANSLATION_AVAILABLE:
            # Return original text if translation is disabled
            return fallback_result
        
        if not text or not text.strip():
            return {
                **fallback_result,
                "success": False,
                "error": "Empty text provided",
            }
        
        try:
            # Use target language from parameter or default
            target_lang = (target_language or self.default_target_language).lower()
            
            # Detect language if not provided
            if source_language:
                detected_lang = source_language.lower()
            else:
                try:
                    # Try to detect language using Google Translator
                    # Note: deep-translator doesn't have a direct detect method,
                    # but we can try translation with 'auto' source and check the result
                    # For now, we'll use 'auto' and let the translator handle detection
                    detected_lang = None  # Will be auto-detected by translator
                except Exception as e:
                    print(f"[Translation] ⚠️  Language detection failed: {e}, defaulting to auto")
                    detected_lang = None
            
            # Perform translation with auto-detection
            try:
                translator = GoogleTranslator(source=detected_lang or "auto", target=target_lang)
                translated_text = translator.translate(text)
                
                # Check if translation is the same as original (likely already in target language)
                # Use case-insensitive comparison for short texts, exact for longer texts
                text_lower = text.lower().strip()
                translated_lower = translated_text.lower().strip()
                
                if translated_lower == text_lower:
                    # Same text - likely already in target language
                    print(f"[Translation] ✅ Text already in target language ({target_lang}), no translation needed")
                    return {
                        "success": True,
                        "translated_text": text,  # Use original text
                        "detected_language": detected_lang or target_lang,
                        "target_language": target_lang,
                        "was_translated": False,
                        "error": None,
                    }
                else:
                    # Different text - translation was performed
                    print(f"[Translation] ✅ Translated from {detected_lang or 'auto'} to {target_lang}")
                    return {
                        "success": True,
                        "translated_text": translated_text,
                        "detected_language": detected_lang,
                        "target_language": target_lang,
                        "was_translated": True,
                        "error": None,
                    }
                
            except Exception as e:
                print(f"[Translation] ❌ Translation failed: {e}")
                # Return original text on translation failure
                return {
                    "success": False,
                    "translated_text": text,
                    "detected_language": detected_lang,
                    "target_language": target_lang,
                    "was_translated": False,
                    "error": str(e),
                }
                
        except Exception as e:
            print(f"[Translation] ❌ Translation service error: {e}")
            import traceback
            traceback.print_exc()
            # Return original text on error
            return {
                "success": False,
                "translated_text": text,
                "detected_language": None,
                "target_language": target_language or self.default_target_language,
                "was_translated": False,
                "error": str(e),
            }
    
    async def translate_transcript_entry(
        self,
        transcript_entry: Dict[str, Any],
        target_language: Optional[str] = None,
        source_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Translate a transcript entry and add translated_text field
        
        Args:
            transcript_entry: Transcript entry dict with 'text' field
            target_language: Target language code (default: English)
            source_language: Source language code (default: auto-detect)
            
        Returns:
            Updated transcript_entry dict with 'translated_text' field added
        """
        original_text = transcript_entry.get("text", "")
        print(f"[Translation] [DEBUG] 🔍 translate_transcript_entry called")
        print(f"[Translation] [DEBUG]   Original text: '{original_text[:50]}...' (length: {len(original_text)})")
        print(f"[Translation] [DEBUG]   Target language: {target_language or self.default_target_language}")
        print(f"[Translation] [DEBUG]   Entry keys before: {list(transcript_entry.keys())}")
        
        if not original_text:
            print(f"[Translation] [DEBUG] ⚠️  Empty text, skipping translation")
            transcript_entry["translated_text"] = ""
            transcript_entry["detected_language"] = None
            transcript_entry["was_translated"] = False
            return transcript_entry
        
        try:
            # IMPORTANT: We preserve the original 'text' field unchanged
            # Only ADD new fields: translated_text, detected_language, was_translated
            
            # Translate the text
            print(f"[Translation] [DEBUG] 🚀 Calling translate_text...")
            translation_result = await self.translate_text(
                text=original_text,
                target_language=target_language,
                source_language=source_language
            )
            
            print(f"[Translation] [DEBUG] ✅ Translation result received")
            print(f"[Translation] [DEBUG]   Success: {translation_result.get('success')}")
            print(f"[Translation] [DEBUG]   Translated text: '{translation_result.get('translated_text', '')[:50]}...'")
            print(f"[Translation] [DEBUG]   Was translated: {translation_result.get('was_translated')}")
            print(f"[Translation] [DEBUG]   Detected language: {translation_result.get('detected_language')}")
            print(f"[Translation] [DEBUG]   Error: {translation_result.get('error')}")
            
            # Add NEW fields to transcript entry (do NOT modify existing 'text' field)
            # The 'text' field always contains the original transcribed text in the source language
            transcript_entry["translated_text"] = translation_result["translated_text"]
            transcript_entry["detected_language"] = translation_result.get("detected_language")
            transcript_entry["was_translated"] = translation_result.get("was_translated", False)
            
            print(f"[Translation] [DEBUG] ✅ Entry updated")
            print(f"[Translation] [DEBUG]   Entry keys after: {list(transcript_entry.keys())}")
            print(f"[Translation] [DEBUG]   Original 'text' preserved: '{transcript_entry.get('text', '')[:50]}...'")
            print(f"[Translation] [DEBUG]   New 'translated_text': '{transcript_entry.get('translated_text', '')[:50]}...'")
            
            # Original 'text' field is preserved and unchanged
            return transcript_entry
            
        except Exception as e:
            print(f"[Translation] [DEBUG] ❌ Exception in translate_transcript_entry: {e}")
            import traceback
            traceback.print_exc()
            # On error, set translated_text to original text
            transcript_entry["translated_text"] = original_text
            transcript_entry["detected_language"] = None
            transcript_entry["was_translated"] = False
            print(f"[Translation] [DEBUG] ⚠️  Fallback: translated_text set to original text")
            return transcript_entry


# Singleton instance
print("[Translation] 🚀 Creating Translation Service singleton instance...")
translation_service = TranslationService()
print("[Translation] ✅ Translation Service singleton ready")

