import logging
import aiohttp
import asyncio

logging.basicConfig(level=logging.NOTSET)

#GET a list of endpoints from webhooks.yaml and post there the PUT POST DELETE events

logger = logging.getLogger(__name__)


class WebHooks:
    """Post message to all registered webhooks"""
    
    def __init__(self):
        self.loop = asyncio.get_event_loop()

    async def __async__post(self):
        logger.info("Start Notify Webhooks")
        await asyncio.sleep(6)
        logger.info("Finish Notify Webhooks")
    
    def notify_webhooks(self):
        return self.loop.run_until_complete(self.__async__post())
