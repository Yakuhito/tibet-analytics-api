from leaflet_client import LeafletFullNodeRpcClient
from typing import List
import models

async def sync_router(router: models.Router) -> [models.Router, List[models.Pair]]:
    print("sync_router", router)
    return None, []

async def sync_pair(pair: models.Pair) -> [models.Pair, List[models.Transaction]]:
    print("sync_pair", pair)
    return None, []