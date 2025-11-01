import os
from typing import Optional
import httpx


class UpstashSync:
    def __init__(
        self,
        redis_url: Optional[str] = None,
        redis_token: Optional[str] = None,
        rest_url: Optional[str] = None,
        rest_token: Optional[str] = None
    ):
        from dotenv import load_dotenv
        load_dotenv()
        
        redis_url = redis_url or os.getenv('UPSTASH_REDIS_URL')
        redis_token = redis_token or os.getenv('UPSTASH_REDIS_TOKEN')
        rest_url = rest_url or os.getenv('UPSTASH_REST_URL')
        rest_token = rest_token or os.getenv('UPSTASH_REST_TOKEN')
        
        self.redis_url = redis_url
        self.redis_token = redis_token
        self.rest_url = rest_url
        self.rest_token = rest_token
    
    def set(self, key: str, value: str, ttl: Optional[int] = None):
        if not self.rest_url or not self.rest_token:
            return False
        try:
            url = f"{self.rest_url}"
            headers = {
                "Authorization": f"Bearer {self.rest_token}",
                "Content-Type": "application/json"
            }
            cmd = ["SET", key, value]
            if ttl:
                cmd.extend(["EX", str(ttl)])
            data = {"command": cmd}
            response = httpx.post(url, headers=headers, json=data, timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
    
    def get(self, key: str) -> Optional[str]:
        if not self.rest_url or not self.rest_token:
            return None
        try:
            url = f"{self.rest_url}"
            headers = {
                "Authorization": f"Bearer {self.rest_token}",
                "Content-Type": "application/json"
            }
            data = {"command": ["GET", key]}
            response = httpx.post(url, headers=headers, json=data, timeout=5.0)
            if response.status_code == 200:
                result = response.json()
                return result.get("result") if isinstance(result, dict) else str(result)
            return None
        except Exception:
            return None
    
    def delete(self, key: str):
        if not self.rest_url or not self.rest_token:
            return False
        try:
            url = f"{self.rest_url}"
            headers = {
                "Authorization": f"Bearer {self.rest_token}",
                "Content-Type": "application/json"
            }
            data = {"command": ["DEL", key]}
            response = httpx.post(url, headers=headers, json=data, timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
    
    def exists(self, key: str) -> bool:
        return self.get(key) is not None
