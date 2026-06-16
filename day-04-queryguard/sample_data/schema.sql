-- Intentionally imperfect e-commerce schema used to demo QueryGuard's rules.
-- Issues planted on purpose (see README "Output Examples" for what gets flagged):
--   * orders            -> customer_id FK has no supporting index (PERF001)
--   * order_items       -> no PRIMARY KEY at all (SCHEMA001)
--   * order_items       -> duplicate indexes on order_id (PERF002)
--   * customers          -> notes column uses unconstrained TEXT (SCHEMA003)
--   * shipments          -> nullable order_id FK (SCHEMA002)
--   * audit_log          -> 50k+ rows, zero indexes (PERF003)

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status VARCHAR(20) NOT NULL,
    total_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
-- NOTE: no index on orders.customer_id (planted issue)

CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL
);
-- NOTE: no PRIMARY KEY (planted issue)

CREATE INDEX ix_order_items_order_id ON order_items(order_id);
CREATE INDEX ix_order_items_order_id_dup ON order_items(order_id);
-- NOTE: duplicate index above (planted issue)

CREATE TABLE shipments (
    id INTEGER PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    carrier VARCHAR(40) NOT NULL,
    tracking_number VARCHAR(64),
    shipped_at TEXT
);
-- NOTE: order_id is nullable FK (planted issue)
CREATE INDEX ix_shipments_order_id ON shipments(order_id);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    actor VARCHAR(120) NOT NULL,
    action VARCHAR(60) NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL
);
-- NOTE: zero indexes beyond rowid, will be seeded with 50k+ rows (planted issue)
