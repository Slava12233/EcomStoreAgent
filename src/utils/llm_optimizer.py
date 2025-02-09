import asyncio
import logging
from typing import Dict, List, Optional, Any
from functools import lru_cache
from .cache_manager import CacheManager

# הגדרת לוגר
logger = logging.getLogger(__name__)

class LLMOptimizer:
    """אופטימיזציה של תקשורת עם מודל השפה"""
    
    def __init__(self, cache_manager: CacheManager, batch_size: int = 5, batch_timeout: float = 0.1):
        """
        אתחול האופטימייזר
        
        Args:
            cache_manager: מנהל המטמון
            batch_size: גודל האצווה המקסימלי
            batch_timeout: זמן המתנה מקסימלי לאצווה (בשניות)
        """
        self.cache = cache_manager
        self.request_queue = asyncio.Queue()
        self.batch_size = max(1, batch_size)
        self.batch_timeout = max(0.01, batch_timeout)
        self.processing = False
        self._batch_processor_task = None
        
    async def start(self):
        """התחלת עיבוד אצוות ברקע"""
        if not self.processing:
            self.processing = True
            self._batch_processor_task = asyncio.create_task(self._process_batches())
            logger.info("Started batch processor")
            
    async def stop(self):
        """עצירת עיבוד אצוות"""
        if self.processing:
            self.processing = False
            if self._batch_processor_task:
                await self._batch_processor_task
            logger.info("Stopped batch processor")
        
    @lru_cache(maxsize=1000)
    def get_cached_response(self, prompt: str) -> Optional[str]:
        """קבלת תשובה מהמטמון"""
        if not prompt:
            logger.warning("Attempted to get cached response with empty prompt")
            return None
            
        try:
            cache_key = f"llm_response:{hash(prompt)}"
            return self.cache.get_from_memory(cache_key)
        except Exception as e:
            logger.error(f"Error getting cached response: {e}")
            return None
        
    async def optimize_prompt(self, prompt: str) -> str:
        """אופטימיזציה של הפרומפט לפני שליחה ל-LLM"""
        if not prompt:
            logger.warning("Attempted to optimize empty prompt")
            return ""
            
        try:
            # הסרת רווחים מיותרים
            optimized = prompt.strip()
            
            # קיצור הפרומפט אם ארוך מדי
            if len(optimized) > 1000:
                logger.warning(f"Prompt too long ({len(optimized)} chars), truncating")
                optimized = optimized[:1000] + "..."
            
            # שימוש בתבניות קבועות מראש לשיפור המהירות
            if "מחיר" in optimized:
                optimized = f"עדכן מחיר: {optimized}"
            elif "מלאי" in optimized:
                optimized = f"עדכן מלאי: {optimized}"
                
            return optimized
        except Exception as e:
            logger.error(f"Error optimizing prompt: {e}")
            return prompt
            
    async def _process_batches(self):
        """עיבוד רציף של אצוות ברקע"""
        while self.processing:
            try:
                batch = await self._collect_batch()
                if batch:
                    responses = await self._process_batch(batch)
                    await self._cache_responses(batch, responses)
            except Exception as e:
                logger.error(f"Error in batch processing loop: {e}")
                await asyncio.sleep(1)  # המתנה לפני ניסיון נוסף
                
    async def _collect_batch(self) -> List[str]:
        """איסוף בקשות לאצווה"""
        batch = []
        try:
            # איסוף בקשות עד לגודל האצווה או פסק הזמן
            while len(batch) < self.batch_size:
                try:
                    prompt = await asyncio.wait_for(
                        self.request_queue.get(),
                        timeout=self.batch_timeout
                    )
                    if prompt:
                        batch.append(prompt)
                except asyncio.TimeoutError:
                    break
                    
            return batch
        except Exception as e:
            logger.error(f"Error collecting batch: {e}")
            return []
            
    async def _process_batch(self, batch: List[str]) -> List[Dict[str, Any]]:
        """עיבוד אצווה של בקשות"""
        if not batch:
            return []
            
        try:
            # כאן צריך להיות הקוד שמעבד את האצווה מול ה-LLM
            # לדוגמה:
            # responses = await self.llm_client.process_batch(batch)
            # return responses
            return []  # TODO: implement actual LLM processing
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            return [{"error": str(e)}] * len(batch)
            
    async def _cache_responses(self, prompts: List[str], responses: List[Dict[str, Any]]):
        """שמירת תשובות במטמון"""
        try:
            for prompt, response in zip(prompts, responses):
                if prompt and response:
                    cache_key = f"llm_response:{hash(prompt)}"
                    self.cache.set_in_cache(cache_key, response)
        except Exception as e:
            logger.error(f"Error caching responses: {e}")
            
    async def get_response(self, prompt: str) -> Optional[Dict[str, Any]]:
        """קבלת תשובה מה-LLM עם אופטימיזציה"""
        if not prompt:
            logger.warning("Attempted to get response with empty prompt")
            return None
            
        try:
            # בדיקה במטמון
            cached = self.get_cached_response(prompt)
            if cached:
                logger.debug("Found cached response")
                return cached
                
            # אופטימיזציה של הפרומפט
            optimized = await self.optimize_prompt(prompt)
            
            # הוספה לתור לעיבוד באצווה
            await self.request_queue.put(optimized)
            
            # המתנה לתשובה
            while self.processing:
                cached = self.get_cached_response(prompt)
                if cached:
                    return cached
                await asyncio.sleep(0.1)
                
            return None
        except Exception as e:
            logger.error(f"Error getting response: {e}")
            return None 