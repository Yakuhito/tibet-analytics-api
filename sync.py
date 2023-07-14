from chia.wallet.puzzles.singleton_top_layer_v1_1 import SINGLETON_LAUNCHER_HASH
from chia.util.condition_tools import conditions_dict_for_solution
from chia.types.blockchain_format.program import INFINITE_COST
from chia.types.condition_opcodes import ConditionOpcode
from chia.types.blockchain_format.program import Program
from leaflet_client import LeafletFullNodeRpcClient
from chia.types.blockchain_format.coin import Coin
from typing import List
import requests
import models
import time
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
        last_tx_index = -1,
    )


async def sync_router(router: models.Router) -> [models.Router, List[models.Pair]]:
    new_pairs: List[models.Pair] = []

    current_router_coin_id = bytes.fromhex(router.current_coin_id)
    router_coin_record = await client.get_coin_record_by_name(current_router_coin_id)
    if not router_coin_record.spent:
        return None, []

    while router_coin_record.spent:
        print(f"Processing router coin spend {current_router_coin_id.hex()}...")
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
            print(f"New pair for asset id 0x{tail_hash.hex()}")

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

def state_to_xch_reserve(state: Program) -> int:
    return state.at("rf").as_int()

def state_to_token_reserve(state: Program) -> int:
    return state.at("rr").as_int()

def state_to_liquidity(state: Program) -> int:
    return state.at("f").as_int()

def state_to_dict(state: Program):
    return {
        "xch": state_to_xch_reserve(state),
        "token": state_to_token_reserve(state),
        "liquidity": state_to_liquidity(state)
    }

def create_new_transaction(
    coin_id: str,
    pair_coin_id: str,
    old_state: Program,
    new_state: Program,
    height: int,
    index: int,
) -> [models.Transaction, int]:
    state_change = {
        "xch": state_to_xch_reserve(new_state) - state_to_xch_reserve(old_state),
        "token": state_to_token_reserve(new_state) - state_to_token_reserve(old_state),
        "liquidity": state_to_liquidity(new_state) - state_to_liquidity(old_state),
    }

    operation = None
    if state_change["liquidity"] == 0:
        operation = "SWAP"
    else:
        if state_change["liquidity"] > 0:
            operation = "ADD_LIQUIDITY"
        else:
            operation = "REMOVE_LIQUIDITY"

    tx = models.Transaction(
        coin_id = coin_id,
        pair_launcher_id = pair_coin_id,
        operation = operation,
        state_change = state_change,
        new_state = state_to_dict(new_state),
        height = height,
        pair_tx_index = index,
    )

    trade_volume = abs(state_change["xch"]) if operation == "SWAP" else 0
    return tx, trade_volume

async def sync_pair(
    pair: models.Pair,
) -> [models.Pair, List[models.Transaction], List[models.HeightToTimestamp]]:
    new_transactions = []
    new_heights = []
    
    current_pair_coin_id = bytes.fromhex(pair.current_coin_id)
    coin_record = await client.get_coin_record_by_name(current_pair_coin_id)

    if coin_record.coin.puzzle_hash == SINGLETON_LAUNCHER_HASH:
        creation_spend = await client.get_puzzle_and_solution(current_pair_coin_id, coin_record.spent_block_index)
        _, conditions_dict, __ = conditions_dict_for_solution(
            creation_spend.puzzle_reveal,
            creation_spend.solution,
            INFINITE_COST
        )
        last_synced_coin = Coin(coin_record.coin.name(), conditions_dict[ConditionOpcode.CREATE_COIN][0].vars[0], 1)

        current_pair_coin_id = last_synced_coin.name()
        coin_record = await client.get_coin_record_by_name(current_pair_coin_id)

    if not coin_record.spent:
        return None, [], []

    new_state = None
    while coin_record.spent:
        print(f"Processing pair coin spend {current_pair_coin_id.hex()}...")
        creation_spend = await client.get_puzzle_and_solution(current_pair_coin_id, coin_record.spent_block_index)
        _, conditions_dict, __ = conditions_dict_for_solution(
            creation_spend.puzzle_reveal,
            creation_spend.solution,
            INFINITE_COST
        )

        # for a particular pair, the puzzle run throug p2_merkle_root
        # returns the new state as the first element!
        old_state = creation_spend.puzzle_reveal.uncurry()[1].at("rf").uncurry()[1].at("rrf")
        p2_merkle_solution = creation_spend.solution.to_program().at("rrf")
        new_state_puzzle = p2_merkle_solution.at("f") # p2_merkle_tree_modified -> parameters (which is a puzzle)
        params = p2_merkle_solution.at("rrf").at("r")

        dummy_singleton_struct = (b"\x00" * 32, (b"\x00" * 32, b"\x00" * 32))
        dummy_coin_id = b"\x00" * 32

        new_state_puzzle_sol = Program.to([
            old_state,
            params,
            dummy_singleton_struct,
            dummy_coin_id
        ])
        new_state_puzzle_output = new_state_puzzle.run(new_state_puzzle_sol)
        new_state = new_state_puzzle_output.at("f")

        height = coin_record.spent_block_index
        tx, volume = create_new_transaction(
            current_pair_coin_id.hex(),
            pair.launcher_id,
            old_state, new_state,
            height,
            int(pair.last_tx_index) + 1,
        )
        new_transactions.append(tx)

        block_record = await client.get_block_record_by_height(height)
        timestamp = block_record.timestamp if block_record is not None else None
        while timestamp is None or timestamp == 0:
            time.sleep(5)
            block_record = await client.get_block_record_by_height(height)
            timestamp = block_record.timestamp if block_record is not None else None

        new_heights.append(models.HeightToTimestamp(
            height=height,
            timestamp=int(timestamp if timestamp is not None else 0)
        ))

        pair.trade_volume = int(pair.trade_volume) + volume
        pair.last_tx_index = int(pair.last_tx_index) + 1
        print(f"Volume of tx: {volume / 10 ** 12} XCH")

        for cwa in conditions_dict.get(ConditionOpcode.CREATE_COIN, []):
            new_puzzle_hash = cwa.vars[0]
            new_amount = cwa.vars[1]

            if new_amount == b"\x01": # CREATE_COIN with amount=1 -> pair recreation
                current_pair_coin_id = Coin(current_pair_coin_id, new_puzzle_hash, 1).name()

        coin_record = await client.get_coin_record_by_name(current_pair_coin_id)

    pair.xch_reserve = state_to_xch_reserve(new_state)
    pair.token_reserve = state_to_token_reserve(new_state)
    pair.liquidity = state_to_liquidity(new_state)
    pair.current_coin_id = current_pair_coin_id.hex()
    return pair, new_transactions, new_heights
