-- Representative application queries to EXPLAIN against demo.sqlite3.
SELECT * FROM orders WHERE customer_id = 42;
SELECT * FROM order_items WHERE order_id = 100;
SELECT * FROM audit_log WHERE actor = 'user5@example.com';
SELECT id, status FROM orders WHERE status = 'shipped';
SELECT c.full_name, COUNT(o.id) FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.id;
