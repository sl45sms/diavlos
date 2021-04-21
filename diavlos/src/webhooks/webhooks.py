#Notify webhooks for the PUT POST DELETE events
import logging
import aiohttp
import asyncio

logging.basicConfig(level=logging.NOTSET)

#TODO parse the webhooks.yaml and loop on webhooks list
#TODO logging webhook responses on log file 
#TODO keep track on wish webhooks actualy responce with 201 (and maybe 200/202) and remove from list
#TODO repeat until every webhook informend or die after some retries  

logger = logging.getLogger(__name__)

class WebHooks:
    """Post message to all registered webhooks"""
    
    def __init__(self):
        self.loop = asyncio.get_event_loop()

    async def __async__post(self,message):
        logger.info("Start Notify Webhooks")
        await asyncio.sleep(1) #to prevent API server overload
        async with aiohttp.ClientSession() as session:
            async with session.post('https://eugo.dev.grnet.gr/emd_events',data=message) as resp:
                print(message)
                print(resp.status)
                print(await resp.text())
        logger.info("Finish Notify Webhooks")
    
    def notify_webhooks(self, message={}):
        return self.loop.run_until_complete(self.__async__post(message))
