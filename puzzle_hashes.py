from chia.wallet.puzzles.singleton_top_layer_v1_1 import SINGLETON_MOD_HASH, SINGLETON_LAUNCHER_HASH
from chia.wallet.cat_wallet.cat_utils import construct_cat_puzzle
from chia.types.blockchain_format.program import Program
from chia.wallet.puzzles.cat_loader import CAT_MOD
from chia.util.bech32m import encode_puzzle_hash
import os

try:
    from chia.types.blockchain_format.serialized_program import SerializedProgram
except:
    from chia.types.blockchain_format.program import SerializedProgram


def program_from_hex(h: str) -> Program:
    return SerializedProgram.from_bytes(bytes.fromhex(h)).to_program()


# https://github.com/Yakuhito/tibet/blob/master/clvm/p2_singleton_flashloan.clvm.hex
P2_SINGLETON_FLASHLOAN = program_from_hex("ff02ffff01ff04ffff04ff14ffff04ffff0bffff0bff56ffff0bff0affff0bff0aff66ff0580ffff0bff0affff0bff76ffff0bff0affff0bff0aff66ffff02ff1effff04ff02ffff04ffff04ff05ffff04ff0bff178080ff8080808080ffff0bff0affff0bff76ffff0bff0affff0bff0aff66ff2f80ffff0bff0aff66ff46808080ff46808080ff46808080ff5f80ff808080ffff04ffff04ff1cffff01ff248080ffff04ffff04ff08ffff04ff5fff808080ff81bf808080ffff04ffff01ffff46ff3f3cff02ffffffa04bf5122f344554c53bde2ebb8cd2b7e3d1600ad631c385a5d7cce23c7785459aa09dcf97a184f32623d11a73124ceb99a5709b083721e878a16d78f596718ba7b2ffa102a12871fee210fb8619291eaea194581cbd2531e4b23759d225f6806923f63222a102a8d5dd63fba471ebcb1f3e8f7c1e1879b7152a6e7298a91ce119a63400ade7c5ff02ffff03ffff07ff0580ffff01ff0bffff0102ffff02ff1effff04ff02ffff04ff09ff80808080ffff02ff1effff04ff02ffff04ff0dff8080808080ffff01ff0bffff0101ff058080ff0180ff018080")
puzzle_hash_cache = {}

def get_pair_puzzle_hash_info(pair):
    pair_launcher_id = pair.launcher_id
    tail_hash = pair.asset_id

    cached = puzzle_hash_cache.get(pair_launcher_id, -1)
    if cached != -1:
        return cached

    info = {
        "pair_launcher_id": pair_launcher_id
    }

    prefix = "txch"
    if "testnet" not in os.environ.get("DEXIE_TOKEN_URL"):
        prefix = "xch"

    # p2_singleton_flashloan has 3 arguments that need to be curried in:
    # SINGLETON_MOD_HASH, LAUNCHER_ID, LAUNCHER_PUZZLE_HASH
    # first and third are constant, 2nd is the pair launcher id
    p2_singleton_flashloan_puzzle = P2_SINGLETON_FLASHLOAN.curry(
        SINGLETON_MOD_HASH,
        bytes.fromhex(pair_launcher_id),
        SINGLETON_LAUNCHER_HASH
    )
    p2_singleton_flashloan_puzzle_hash = p2_singleton_flashloan_puzzle.get_tree_hash()
    info["puzzle_hash"] = p2_singleton_flashloan_puzzle_hash.hex()
    info["address"] = encode_puzzle_hash(p2_singleton_flashloan_puzzle_hash, prefix)

    cat_p2_singleton_flashloan_puzzle = construct_cat_puzzle(CAT_MOD, tail_hash, p2_singleton_flashloan_puzzle)
    cat_p2_singleton_flashloan_puzzle_hash = cat_p2_singleton_flashloan_puzzle.get_tree_hash()
    info["cat_puzzle_hash"] = cat_p2_singleton_flashloan_puzzle_hash.hex()

    puzzle_hash_cache[pair_launcher_id] = info
    return info
