from redis import Redis

from src.config import settings
from src.logger import get_logger


logger = get_logger("storage")


class Storage:
    def __init__(self, host: str = settings.REDIS_HOST, port: int = settings.REDIS_PORT):
        self.redis = Redis(host=host, port=port)

    def get_order_cached(self, global_id: str) -> int:
        if self.redis.get(global_id):
            return 1
        return 0

    def set_order_cache(self, global_id: str, ex: int = 10) -> None:
        self.redis.set(global_id, 1, ex=ex)
