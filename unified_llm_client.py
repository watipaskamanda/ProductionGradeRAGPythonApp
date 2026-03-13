"""
Unified LLM Client with Groq and Gemini Support
Provides automatic fallback from Groq to Gemini on rate limit errors
"""

import os
import logging
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Import LLM clients
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logging.warning("Groq client not available")

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("Google Generative AI client not available")

load_dotenv()

logger = logging.getLogger(__name__)

class UnifiedLLMClient:
    """Unified client that supports both Groq and Gemini with automatic fallback"""
    
    def __init__(self):
        self.groq_client = None
        self.gemini_model = None
        
        # Initialize Groq client
        if GROQ_AVAILABLE and os.getenv("GROQ_API_KEY"):
            try:
                self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                logger.info("Groq client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")
        
        # Initialize Gemini client
        if GEMINI_AVAILABLE and os.getenv("GEMINI_API_KEY"):
            try:
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                # Use gemini-flash-latest for better performance and availability
                self.gemini_model = genai.GenerativeModel('gemini-flash-latest')
                logger.info("Gemini client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
        
        # Check if at least one client is available
        if not self.groq_client and not self.gemini_model:
            logger.error("No LLM clients available. Please check API keys.")
    
    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI-style messages to Gemini prompt format"""
        prompt_parts = []
        
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System Instructions: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        return "\n\n".join(prompt_parts)
    
    def _call_groq(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Call Groq API"""
        if not self.groq_client:
            raise Exception("Groq client not available")
        
        # Extract parameters with defaults
        model = kwargs.get("model", "llama-3.3-70b-versatile")
        max_tokens = kwargs.get("max_tokens", 300)
        temperature = kwargs.get("temperature", 0.1)
        
        response = self.groq_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return response.choices[0].message.content.strip()
    
    def _call_gemini(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Call Gemini API"""
        if not self.gemini_model:
            raise Exception("Gemini client not available")
        
        # Convert messages to Gemini format
        prompt = self._convert_messages_to_gemini_format(messages)
        
        # Extract parameters
        temperature = kwargs.get("temperature", 0.1)
        max_tokens = kwargs.get("max_tokens", 300)
        
        # Configure generation parameters
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        response = self.gemini_model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        # Handle response safely
        if response and hasattr(response, 'text') and response.text:
            return response.text.strip()
        elif response and hasattr(response, 'candidates') and response.candidates:
            # Try to get text from candidates
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                return part.text.strip()
        
        # If we can't get text, raise an error
        raise Exception("No valid response text received from Gemini")
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Create chat completion with automatic fallback
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional parameters (model, max_tokens, temperature, etc.)
        
        Returns:
            Generated text response
        """
        # Try Groq first
        if self.groq_client:
            try:
                logger.debug("Attempting Groq API call")
                return self._call_groq(messages, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                
                # Check if it's a rate limit error
                if 'rate_limit_exceeded' in error_str or 'rate limit' in error_str:
                    logger.warning("Groq API rate limit exceeded, falling back to Gemini")
                    
                    # Try Gemini fallback
                    if self.gemini_model:
                        try:
                            logger.info("Using Gemini API as fallback")
                            return self._call_gemini(messages, **kwargs)
                        except Exception as gemini_error:
                            logger.error(f"Gemini fallback failed: {gemini_error}")
                            raise Exception("I'm experiencing high demand right now. Please try again in a few minutes.")
                    else:
                        logger.error("Gemini fallback not available")
                        raise Exception("I'm experiencing high demand right now. Please try again in a few minutes.")
                
                # For non-rate-limit errors, handle as before
                elif 'authentication' in error_str or 'api_key' in error_str:
                    logger.error("Groq API authentication failed")
                    raise Exception("There's an issue with the AI service configuration. Please contact support.")
                elif 'timeout' in error_str or 'connection' in error_str:
                    logger.error(f"Groq API connection failed: {e}")
                    raise Exception("The AI service is temporarily unavailable. Please try again in a moment.")
                elif 'model' in error_str and 'not found' in error_str:
                    logger.error(f"Groq model not found: {e}")
                    raise Exception("The AI model is temporarily unavailable. Please try again later.")
                else:
                    logger.error(f"Groq API error: {e}")
                    raise Exception("I'm having trouble processing your request right now. Please try again in a moment.")
        
        # If Groq is not available, try Gemini directly
        elif self.gemini_model:
            try:
                logger.info("Using Gemini API (Groq not available)")
                return self._call_gemini(messages, **kwargs)
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                raise Exception("I'm having trouble processing your request right now. Please try again in a moment.")
        
        # No clients available
        else:
            logger.error("No LLM clients available")
            raise Exception("AI services are currently unavailable. Please contact support.")
    
    def get_available_providers(self) -> List[str]:
        """Get list of available LLM providers"""
        providers = []
        if self.groq_client:
            providers.append("groq")
        if self.gemini_model:
            providers.append("gemini")
        return providers
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of all available providers"""
        health = {
            "groq": {"available": bool(self.groq_client), "status": "unknown"},
            "gemini": {"available": bool(self.gemini_model), "status": "unknown"}
        }
        
        # Test Groq
        if self.groq_client:
            try:
                test_response = self._call_groq([{"role": "user", "content": "Hello"}], max_tokens=10)
                health["groq"]["status"] = "healthy" if test_response else "unhealthy"
            except Exception as e:
                health["groq"]["status"] = "unhealthy"
                health["groq"]["error"] = str(e)
        
        # Test Gemini
        if self.gemini_model:
            try:
                # Use a simple test that should work
                response = self.gemini_model.generate_content("Say 'OK'")
                if response and hasattr(response, 'text') and response.text:
                    health["gemini"]["status"] = "healthy"
                else:
                    health["gemini"]["status"] = "unhealthy"
                    health["gemini"]["error"] = "No valid response received"
            except Exception as e:
                health["gemini"]["status"] = "unhealthy"
                health["gemini"]["error"] = str(e)
        
        return health

# Global instance
unified_llm_client = UnifiedLLMClient()

def get_llm_client() -> UnifiedLLMClient:
    """Get the global unified LLM client instance"""
    return unified_llm_client