import requests
import time
import models
from sqlalchemy.orm import Session
from typing import Optional

CRYPTOCOMPARE_API_URL = "https://min-api.cryptocompare.com/data/v2/histohour"

def fetch_price_data(to_timestamp: int, limit: int = 1) -> Optional[dict]:
    try:
        params = {
            "fsym": "XCH",
            "tsym": "USD",
            "limit": limit,
            "toTs": to_timestamp
        }
        response = requests.get(CRYPTOCOMPARE_API_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if data.get("Response") != "Success":
            print(f"CryptoCompare API error: {data.get('Message', 'Unknown error')}")
            return None
            
        return data.get("Data")
    except Exception as e:
        print(f"Error fetching price data: {e}")
        return None


def calculate_average_price_cents(price_entry: dict) -> int:
    volume_from = price_entry.get("volumefrom", 0)
    volume_to = price_entry.get("volumeto", 0)
    
    if volume_from == 0 or volume_to == 0:
        # Use the close price as fallback
        close_price = price_entry.get("close", 0)
        return int(close_price * 100)
    
    return int(volume_to * 100 // volume_from)


def get_max_synced_timestamp(db: Session) -> int:
    max_entry = db.query(models.AverageUsdPrice).order_by(
        models.AverageUsdPrice.to_timestamp.desc()
    ).first()
    
    # TibetSwap v2 launched May 15th, 2023
    return max_entry.to_timestamp if max_entry else 1684130400


def get_price_for_timestamp(db: Session, timestamp: int) -> Optional[models.AverageUsdPrice]:
    return db.query(models.AverageUsdPrice).filter(
        models.AverageUsdPrice.from_timestamp <= timestamp,
        models.AverageUsdPrice.to_timestamp > timestamp
    ).first()


def update_pair_usd_volumes_for_period(
    db: Session, 
    from_timestamp: int, 
    to_timestamp: int, 
    price_cents: int
):
    """
    Update USD volumes for all pairs that have SWAP transactions in the given period.
    This is called when a new price entry is inserted.
    """
    # Get all transactions in this period
    transactions = db.query(models.Transaction).join(
        models.HeightToTimestamp,
        models.Transaction.height == models.HeightToTimestamp.height
    ).filter(
        models.Transaction.operation == "SWAP",
        models.HeightToTimestamp.timestamp >= from_timestamp,
        models.HeightToTimestamp.timestamp < to_timestamp
    ).all()
    
    # Group by pair and calculate USD volume
    pair_volumes = {}
    for tx in transactions:
        pair_id = tx.pair_launcher_id
        xch_volume = abs(tx.state_change.get("xch", 0))
        
        # Convert XCH volume to USD cents (xch_volume is in mojos, 1 XCH = 10^12 mojos)
        usd_volume_cents = (xch_volume * price_cents) // (10 ** 12)
        
        if pair_id not in pair_volumes:
            pair_volumes[pair_id] = 0
        pair_volumes[pair_id] += usd_volume_cents
    
    # Update each pair's USD volume
    for pair_id, usd_volume in pair_volumes.items():
        pair = db.query(models.Pair).filter(
            models.Pair.launcher_id == pair_id
        ).first()
        if pair:
            pair.trade_volume_usd = int(pair.trade_volume_usd or 0) + usd_volume
    
    print(f"Updated USD volumes for {len(pair_volumes)} pairs in period {from_timestamp}-{to_timestamp}")

def sync_prices(db: Session) -> int:
    """
    Sync price data from CryptoCompare API.
    Returns the maximum to_timestamp synced, or 0 if failed.
    """
    max_synced = get_max_synced_timestamp(db)
    current_time = int(time.time())
    
    # Determine the starting point
    if max_synced == 0:
        # If no data exists, start from the earliest transaction
        earliest_height = db.query(models.HeightToTimestamp).order_by(
            models.HeightToTimestamp.timestamp.asc()
        ).first()
        
        if earliest_height is None:
            print("No transactions to sync prices for")
            return 0
        
        # Round down to the nearest hour
        start_timestamp = (earliest_height.timestamp // 3600) * 3600
    else:
        # Continue from where we left off
        start_timestamp = max_synced
    
    # Don't sync data that's too recent (need at least 15 minutes for API to have data)
    max_sync_timestamp = ((current_time - 900) // 3600) * 3600
    
    if start_timestamp >= max_sync_timestamp:
        print(f"Already synced up to {start_timestamp}, waiting for more data")
        return max_synced
    
    print(f"Syncing prices from {start_timestamp} to {max_sync_timestamp}")
    
    # Fetch data in batches (API limit is 2000, but we'll use smaller batches)
    batch_size = 2000
    current_timestamp = start_timestamp
    synced_count = 0
    
    while current_timestamp < max_sync_timestamp:
        # Calculate how many entries we need
        remaining = (max_sync_timestamp - current_timestamp) // 3600
        limit = min(batch_size, remaining)
        
        # Fetch data
        to_ts = current_timestamp + (limit * 3600)
        print(f"Fetching {limit} price entries up to timestamp {to_ts}")
        
        data = fetch_price_data(to_ts, limit)
        if data is None:
            print("Failed to fetch price data")
            return 0
        
        price_entries = data.get("Data", [])
        if not price_entries:
            print("No price entries returned")
            break
        
        # Process each price entry
        for entry in price_entries:
            entry_time = entry.get("time")
            if entry_time <= current_timestamp:
                continue
            
            from_ts = entry_time
            to_ts = entry_time + 3600
            price_cents = calculate_average_price_cents(entry)
            
            # Check if this entry already exists
            existing = db.query(models.AverageUsdPrice).filter(
                models.AverageUsdPrice.from_timestamp == from_ts
            ).first()
            
            if existing:
                print(f"Price entry for {from_ts} already exists, skipping")
                current_timestamp = to_ts
                continue
            
            # Insert the new price entry
            new_price = models.AverageUsdPrice(
                from_timestamp=from_ts,
                to_timestamp=to_ts,
                price_cents=price_cents
            )
            db.add(new_price)
            
            # Update USD volumes for pairs with transactions in this period
            update_pair_usd_volumes_for_period(db, from_ts, to_ts, price_cents)
            
            # Commit the transaction
            db.commit()
            
            synced_count += 1
            current_timestamp = to_ts
            print(f"Synced price for {from_ts}: ${price_cents/100:.2f} USD/XCH")
    
    print(f"Successfully synced {synced_count} price entries")
    return current_timestamp

def update_transaction_usd_volume(db: Session, transaction: models.Transaction):
    """
    Update the USD volume for a pair when a new transaction is added.
    This checks if a price is available for the transaction's timestamp and updates accordingly.
    """
    if transaction.operation != "SWAP":
        return
    
    # Get the timestamp for this transaction
    height_entry = db.query(models.HeightToTimestamp).filter(
        models.HeightToTimestamp.height == transaction.height
    ).first()
    
    if not height_entry:
        print(f"No timestamp found for height {transaction.height}")
        return
    
    # Get the price for this timestamp
    price_entry = get_price_for_timestamp(db, height_entry.timestamp)
    
    if not price_entry:
        print(f"No price data available for timestamp {height_entry.timestamp}")
        return
    
    # Calculate USD volume
    xch_volume = abs(transaction.state_change.get("xch", 0))
    usd_volume_cents = (xch_volume * price_entry.price_cents) // (10 ** 12)
    
    # Update the pair's USD volume
    pair = db.query(models.Pair).filter(
        models.Pair.launcher_id == transaction.pair_launcher_id
    ).first()
    
    if pair:
        pair.trade_volume_usd = int(pair.trade_volume_usd or 0) + usd_volume_cents
        print(f"Updated USD volume for pair {pair.launcher_id}: +${usd_volume_cents/100:.2f}")

