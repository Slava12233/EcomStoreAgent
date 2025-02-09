import aiohttp
import asyncio
import logging
from typing import Optional, Dict, List, Any, Union, AsyncGenerator
from contextlib import asynccontextmanager

# הגדרת לוגר
logger = logging.getLogger(__name__)

class ConnectionManager:
    """מנהל חיבורים עם Connection Pooling מתקדם"""
    
    def __init__(self, max_connections: int = 100, dns_cache_ttl: int = 300):
        """
        אתחול מנהל החיבורים
        
        Args:
            max_connections: מספר החיבורים המקסימלי
            dns_cache_ttl: זמן שמירת DNS במטמון (בשניות)
        """
        self._pools: Dict[str, aiohttp.ClientSession] = {}
        self.max_connections = max(1, max_connections)
        self.dns_cache_ttl = max(60, dns_cache_ttl)
        self.semaphore = asyncio.Semaphore(self.max_connections)
        logger.info(f"Initialized connection manager with {max_connections} max connections")
        
    async def init_pool(self, name: str, base_url: str):
        """יצירת מאגר חיבורים חדש"""
        try:
            if name in self._pools:
                logger.warning(f"Pool {name} already exists")
                return
                
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                ttl_dns_cache=self.dns_cache_ttl,
                use_dns_cache=True,
                force_close=False,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(
                total=30,
                connect=10,
                sock_read=10,
                sock_connect=10
            )
            
            self._pools[name] = aiohttp.ClientSession(
                base_url=base_url,
                connector=connector,
                timeout=timeout,
                raise_for_status=True,
                headers={"Connection": "keep-alive"}
            )
            
            logger.info(f"Created connection pool {name} for {base_url}")
        except Exception as e:
            logger.error(f"Failed to initialize pool {name}: {e}")
            raise
            
    async def close_all(self):
        """סגירת כל מאגרי החיבורים"""
        try:
            close_tasks = []
            for name, pool in self._pools.items():
                logger.debug(f"Closing pool {name}")
                if not pool.closed:
                    close_tasks.append(pool.close())
                    
            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)
                
            # ניקוי משאבים נוספים
            for pool in self._pools.values():
                if hasattr(pool, '_connector') and pool._connector:
                    await pool._connector.close()
                    
            self._pools.clear()
            logger.info("Closed all connection pools")
        except Exception as e:
            logger.error(f"Error closing pools: {e}")
            raise
        
    @asynccontextmanager
    async def get_connection(self, pool_name: str) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """קבלת חיבור ממאגר החיבורים"""
        if not pool_name:
            raise ValueError("Pool name cannot be empty")
            
        async with self.semaphore:
            pool = self._pools.get(pool_name)
            if not pool:
                raise ValueError(f"Pool {pool_name} not initialized")
                
            try:
                yield pool
            except Exception as e:
                logger.error(f"Connection error in pool {pool_name}: {e}")
                raise
                
    async def request(
        self,
        pool_name: str,
        method: str,
        url: str,
        **kwargs
    ) -> Optional[Union[Dict[str, Any], str]]:
        """ביצוע בקשת HTTP עם ניהול חיבורים"""
        if not pool_name or not method or not url:
            raise ValueError("Missing required parameters")
            
        async with self.get_connection(pool_name) as session:
            try:
                async with session.request(method, url, **kwargs) as response:
                    try:
                        return await response.json()
                    except aiohttp.ContentTypeError:
                        # אם התגובה אינה JSON, נחזיר את הטקסט
                        return await response.text()
            except aiohttp.ClientError as e:
                logger.error(f"HTTP request error: {e}")
                return None
            except asyncio.TimeoutError:
                logger.error("Request timeout")
                return None
            except Exception as e:
                logger.error(f"Unexpected error in request: {e}")
                return None
                
    async def batch_request(
        self,
        pool_name: str,
        requests: List[Dict[str, Any]]
    ) -> List[Optional[Union[Dict[str, Any], str]]]:
        """ביצוע מספר בקשות במקביל"""
        if not pool_name or not requests:
            raise ValueError("Missing required parameters")
            
        async with self.get_connection(pool_name) as session:
            tasks = []
            for req in requests:
                if not isinstance(req, dict) or not req.get("method") or not req.get("url"):
                    logger.warning("Invalid request format, skipping")
                    continue
                    
                task = asyncio.create_task(
                    session.request(
                        req["method"],
                        req["url"],
                        **req.get("kwargs", {})
                    )
                )
                tasks.append(task)
                
            if not tasks:
                logger.warning("No valid requests to process")
                return []
                
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            results = []
            
            for response in responses:
                if isinstance(response, Exception):
                    logger.error(f"Batch request error: {response}")
                    results.append(None)
                else:
                    try:
                        try:
                            results.append(await response.json())
                        except aiohttp.ContentTypeError:
                            results.append(await response.text())
                    except Exception as e:
                        logger.error(f"Response parsing error: {e}")
                        results.append(None)
                        
            return results 