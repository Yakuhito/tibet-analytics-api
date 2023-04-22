from leaflet_client import LeafletFullNodeRpcClient
from typing import List
import models
import sys
import os

client: LeafletFullNodeRpcClient = None

def ensure_client():
    global client
    if client is not None:
        return

    network = os.environ.get("TIBET_NETWORK")
    api_key = os.environ.get()
    url = f"https://kraken.fireacademy.io/{api-key}/leaflet"

    if network == "testnet10":
        url += "-tesntet10/"
    elif network == "mainnet":
        url += "/"
    else:
        print("Unknown TIBET_NETWORK")
        sys.exit(1)

    client = LeafletFullNodeRpcClient(url)


async def sync_router(router: models.Router) -> [models.Router, List[models.Pair]]:
    print("sync_router", router)
    return None, []

async def sync_pair(pair: models.Pair) -> [models.Pair, List[models.Transaction]]:
    print("sync_pair", pair)
    return None, []