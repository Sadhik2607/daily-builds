#!/usr/bin/env python3
"""Builds sample_data/demo.sqlite3 from schema.sql, then seeds realistic-ish demo data,
including a 50k-row audit_log table to make the PERF003 (no index, big table) rule trigger.

Usage: python sample_data/build_demo_db.py [output_path]
"""
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))


def build(db_path: str) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    with open(os.path.join(HERE, "schema.sql")) as fh:
        conn.executescript(fh.read())

    rng = random.Random(42)
    now = datetime.utcnow()

    # customers
    customers = []
    for i in range(1, 201):
        customers.append((
            i,
            f"user{i}@example.com",
            f"Customer {i}",
            "VIP — handle with care" if i % 37 == 0 else None,
            (now - timedelta(days=rng.randint(0, 700))).isoformat(),
        ))
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)

    # orders
    statuses = ["pending", "paid", "shipped", "delivered", "cancelled"]
    orders = []
    for i in range(1, 3001):
        orders.append((
            i,
            rng.randint(1, 200),
            rng.choice(statuses),
            rng.randint(500, 50000),
            (now - timedelta(days=rng.randint(0, 365))).isoformat(),
        ))
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)

    # order_items
    items = []
    for order_id in range(1, 3001):
        for _ in range(rng.randint(1, 4)):
            items.append((order_id, rng.randint(1, 500), rng.randint(1, 3), rng.randint(500, 20000)))
    conn.executemany("INSERT INTO order_items VALUES (?,?,?,?)", items)

    # shipments (only for paid+ orders, some intentionally null order_id to show nullable FK)
    shipments = []
    sid = 1
    for order_id in range(1, 3001, 2):
        shipments.append((sid, order_id, rng.choice(["UPS", "FedEx", "USPS", "DHL"]),
                           f"TRK{rng.randint(10**9, 10**10-1)}",
                           (now - timedelta(days=rng.randint(0, 60))).isoformat()))
        sid += 1
    conn.executemany("INSERT INTO shipments VALUES (?,?,?,?,?)", shipments)

    # audit_log: 50k+ rows, no indexes -> triggers PERF003
    actions = ["login", "logout", "update_profile", "place_order", "refund", "password_reset"]
    batch = []
    for i in range(1, 52001):
        batch.append((
            i,
            f"user{rng.randint(1, 200)}@example.com",
            rng.choice(actions),
            "ip=10.0.{}.{}".format(rng.randint(0, 255), rng.randint(0, 255)),
            (now - timedelta(minutes=rng.randint(0, 500000))).isoformat(),
        ))
        if len(batch) >= 5000:
            conn.executemany("INSERT INTO audit_log VALUES (?,?,?,?,?)", batch)
            batch = []
    if batch:
        conn.executemany("INSERT INTO audit_log VALUES (?,?,?,?,?)", batch)

    conn.commit()
    conn.close()
    print(f"Built {db_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "demo.sqlite3")
    build(out)
