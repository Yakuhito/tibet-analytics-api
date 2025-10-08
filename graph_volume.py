#!/usr/bin/env python3
# pip install matplotlib==3.9.2
"""
Graph total traded volume over time for TibetSwap.
Shows cumulative volume in both XCH and USD.

To check final USD volume you can also run:
```
sqlite3 database.db "SELECT SUM(CAST(trade_volume_usd AS INTEGER)) as total_trade_volume_usd FROM pairs"
```
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from sqlalchemy import func
import models, database
from usd_price_sync import get_price_for_timestamp


def fetch_all_usd_prices(db):
    """Fetch all historic USD prices from the database."""
    prices = db.query(models.AverageUsdPrice).order_by(
        models.AverageUsdPrice.from_timestamp.asc()
    ).all()
    
    print(f"Loaded {len(prices)} USD price entries")
    return prices


def get_transaction_count(db):
    """Get total number of transactions."""
    count = db.query(func.count(models.Transaction.coin_id)).scalar()
    return count


def fetch_transactions_batch(db, batch_size=5000, offset=0):
    """Fetch transactions in batches, ordered by height."""
    transactions = db.query(
        models.Transaction,
        models.HeightToTimestamp.timestamp
    ).outerjoin(
        models.HeightToTimestamp,
        models.Transaction.height == models.HeightToTimestamp.height
    ).order_by(
        models.Transaction.height.asc()
    ).limit(batch_size).offset(offset).all()
    
    return transactions


def process_transactions(db):
    """
    Process all transactions and calculate cumulative volume in XCH and USD.
    Returns lists of timestamps, XCH volumes, and USD volumes.
    """
    timestamps = []
    cumulative_xch_volume = []
    cumulative_usd_volume = []
    
    total_xch = 0
    total_usd = 0
    
    # Get total count
    total_count = get_transaction_count(db)
    print(f"Total transactions: {total_count}")
    
    batch_size = 5000
    offset = 0
    processed = 0
    
    while offset < total_count:
        print(f"Processing transactions {offset}-{min(offset + batch_size, total_count)}/{total_count}...")
        
        batch = fetch_transactions_batch(db, batch_size, offset)
        
        if not batch:
            break
        
        for tx, timestamp in batch:
            # Only process SWAP transactions
            if tx.operation != "SWAP":
                continue
            
            # Skip if no timestamp
            if not timestamp:
                continue
            
            # Get XCH volume (absolute value of XCH change)
            xch_volume = abs(tx.state_change.get("xch", 0))
            
            if xch_volume == 0:
                continue
            
            # Get USD price for this timestamp
            price_entry = get_price_for_timestamp(db, timestamp)
            
            if price_entry:
                # Calculate USD volume
                # XCH is in mojos (10^12 mojos = 1 XCH)
                # price_cents is in cents (100 cents = 1 USD)
                usd_volume_cents = (xch_volume * price_entry.price_cents) // (10 ** 12)
                usd_volume = usd_volume_cents / 100
            else:
                usd_volume = 0
            
            # Update cumulative volumes
            total_xch += xch_volume / (10 ** 12)  # Convert mojos to XCH
            total_usd += usd_volume
            
            # Store the data point
            timestamps.append(datetime.fromtimestamp(timestamp))
            cumulative_xch_volume.append(total_xch)
            cumulative_usd_volume.append(total_usd)
            
            processed += 1
            if processed % 1000 == 0:
                print(f"  Processed {processed} swap transactions...")
        
        offset += batch_size
    
    print(f"Processed {processed} swap transactions total")
    print(f"Final cumulative XCH volume: {total_xch:,.2f} XCH")
    print(f"Final cumulative USD volume: ${total_usd:,.2f}")
    
    return timestamps, cumulative_xch_volume, cumulative_usd_volume


def create_graph(timestamps, cumulative_xch_volume, cumulative_usd_volume):
    """Create a graph showing cumulative volume over time."""
    if not timestamps:
        print("No data to plot!")
        return
    
    # Create figure with two y-axes
    fig, ax1 = plt.subplots(figsize=(14, 8))
    
    # Plot XCH volume on left y-axis
    color = 'tab:blue'
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('Cumulative Volume (XCH)', color=color, fontsize=12)
    line1 = ax1.plot(timestamps, cumulative_xch_volume, color=color, linewidth=2, label='XCH Volume')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.grid(True, alpha=0.3)
    
    # Format x-axis dates
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Create second y-axis for USD
    ax2 = ax1.twinx()
    color = 'tab:green'
    ax2.set_ylabel('Cumulative Volume (USD)', color=color, fontsize=12)
    line2 = ax2.plot(timestamps, cumulative_usd_volume, color=color, linewidth=2, label='USD Volume')
    ax2.tick_params(axis='y', labelcolor=color)
    
    # Add title
    plt.title('TibetSwap Cumulative Trading Volume Over Time', fontsize=16, fontweight='bold', pad=20)
    
    # Add legend
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', fontsize=11)
    
    # Tight layout to prevent label cutoff
    plt.tight_layout()
    
    # Save the figure
    output_file = 'cumulative_volume_graph.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\nGraph saved to {output_file}")
    
    # Show the plot
    plt.show()


def main():
    """Main function to generate the volume graph."""
    print("Starting volume graph generation...")
    print("=" * 60)
    
    # Create database session
    db = database.SessionLocal()
    
    try:
        # Fetch USD prices
        print("\n1. Fetching USD price data...")
        usd_prices = fetch_all_usd_prices(db)
        
        # Process transactions
        print("\n2. Processing transactions...")
        timestamps, cumulative_xch_volume, cumulative_usd_volume = process_transactions(db)
        
        # Create graph
        print("\n3. Creating graph...")
        create_graph(timestamps, cumulative_xch_volume, cumulative_usd_volume)
        
        print("\n" + "=" * 60)
        print("Done!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

