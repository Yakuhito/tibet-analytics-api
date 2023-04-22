from chia.wallet.puzzles.singleton_top_layer_v1_1 import SINGLETON_LAUNCHER_HASH
from chia.util.condition_tools import conditions_dict_for_solution
from chia.types.blockchain_format.program import INFINITE_COST
from chia.types.condition_opcodes import ConditionOpcode
from leaflet_client import LeafletFullNodeRpcClient
from chia.types.blockchain_format.coin import Coin
from typing import List
import requests
import models
import sys
import os

client: LeafletFullNodeRpcClient = None

def ensure_client():
    global client
    if client is not None:
        return

    network = os.environ.get("TIBET_NETWORK")
    api_key = os.environ.get("FIREACADEMYIO_API_KEY")
    url = f"https://kraken.fireacademy.io/{api_key}/leaflet"

    if network == "testnet10":
        url += "-testnet10/"
    elif network == "mainnet":
        url += "/"
    else:
        print("Unknown TIBET_NETWORK")
        sys.exit(1)

    client = LeafletFullNodeRpcClient(url)


def create_new_pair(asset_id: str, launcher_id: str) -> models.Pair:
    name = f"CAT 0x{asset_id[:8]}"
    short_name = "???"
    image_url = "https://bafybeigzcazxeu7epmm4vtkuadrvysv74lbzzbl2evphtae6k57yhgynp4.ipfs.dweb.link/9098.gif"

    try:
        url = os.environ.get("TAILDATABASE_TAIL_INFO_URL") + asset_id
        resp = requests.get(url)
        j = resp.json()
        if j.get("error") == "Not found":
            raise Exception("TailDatabase: Asset id not found")

        name = j["name"]
        short_name = j["code"]
        image_url = j["nft_uri"]
    except:
        pass

    return models.Pair(
        launcher_id = launcher_id,
        name = name,
        short_name = short_name,
        image_url = image_url,
        asset_id = asset_id,
        current_coin_id = launcher_id,
        xch_reserve = 0,
        token_reserve = 0,
        liquidity = 0,
        trade_volume = 0,
    )


async def sync_router(router: models.Router) -> [models.Router, List[models.Pair]]:
    new_pairs: List[models.Pair] = []

    current_router_coin_id = bytes.fromhex(router.current_coin_id)
    router_coin_record = await client.get_coin_record_by_name(current_router_coin_id)
    if not router_coin_record.spent:
        return None, []

    while router_coin_record.spent:
        creation_spend = await client.get_puzzle_and_solution(
            current_router_coin_id,
            router_coin_record.spent_block_index
        )

        _, conditions_dict, __ = conditions_dict_for_solution(
            creation_spend.puzzle_reveal,
            creation_spend.solution,
            INFINITE_COST
        )

        tail_hash = None
        if router_coin_record.coin.puzzle_hash != SINGLETON_LAUNCHER_HASH:
            solution_program = creation_spend.solution.to_program()
            tail_hash = [_ for _ in solution_program.as_iter()][-1].as_python()[-1]

        for cwa in conditions_dict[ConditionOpcode.CREATE_COIN]:
            new_puzzle_hash = cwa.vars[0]
            new_amount = cwa.vars[1]

            if new_amount == b"\x01": # CREATE_COIN with amount=1 -> router recreated
                new_router_coin = Coin(current_router_coin_id, new_puzzle_hash, 1)

                current_router_coin_id = new_router_coin.name()
            elif new_amount == b"\x02": # CREATE_COIN with amount=2 -> pair launcher deployed
                assert new_puzzle_hash == SINGLETON_LAUNCHER_HASH
                
                pair_launcher_coin = Coin(creation_spend.coin.name(), new_puzzle_hash, 2)
                pair_launcher_id = pair_launcher_coin.name()
                
                new_pairs.append(create_new_pair(tail_hash.hex(), pair_launcher_id.hex()))
            else:
                print("Someone did something extremely weird with the router - time to call the cops.")
                sys.exit(1)

        router_coin_record = await client.get_coin_record_by_name(current_router_coin_id)

    router.current_coin_id = current_router_coin_id.hex()
    return router, new_pairs

async def sync_pair(pair: models.Pair) -> [models.Pair, List[models.Transaction]]:
    new_transactions = []
    

    return None, []