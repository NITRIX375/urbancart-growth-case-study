-- UrbanCart case study: every SQL statement used in Part 1, in execution order.
-- Dialect: DuckDB. {margin} = 0.30 (contribution margin from the brief).

-- ============================================================================
-- Load raw tables
-- ============================================================================
-- [raw_users]
CREATE OR REPLACE TABLE raw_users AS
        SELECT * FROM read_csv('data/raw/users.csv', header = true,
            columns = {'user_id': 'BIGINT', 'signup_date': 'DATE', 'city': 'VARCHAR',
                        'acquisition_channel': 'VARCHAR', 'email': 'VARCHAR'});

-- [raw_orders]
CREATE OR REPLACE TABLE raw_orders AS
        SELECT * FROM read_csv('data/raw/orders.csv', header = true,
            columns = {'order_id': 'BIGINT', 'user_id': 'BIGINT', 'order_date': 'DATE',
                        'order_value': 'DOUBLE', 'status': 'VARCHAR'});

-- [raw_spend]
CREATE OR REPLACE TABLE raw_spend AS
        SELECT * FROM read_csv('data/raw/marketing_spend.csv', header = true,
            columns = {'month': 'VARCHAR', 'channel': 'VARCHAR', 'spend_inr': 'DOUBLE'});

-- ============================================================================
-- Data quality checks
-- ============================================================================
-- [duplicate_order_rows]
-- Issue 1: exact duplicate rows in orders (same order_id, every column identical)
        SELECT COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw_orders)) AS duplicate_rows,
               COUNT(*) AS raw_rows,
               COUNT(DISTINCT order_id) AS distinct_order_ids
        FROM raw_orders;

-- [conflicting_duplicates]
-- Are any duplicated order_ids NOT identical across columns? (0 = safe to dedupe with DISTINCT)
        SELECT COUNT(*) AS conflicting_order_ids FROM (
            SELECT order_id FROM (SELECT DISTINCT * FROM raw_orders) GROUP BY order_id HAVING COUNT(*) > 1);

-- [blank_channel]
-- Issue 2: users with a blank acquisition_channel, and what they contributed
        WITH b AS (SELECT user_id FROM raw_users WHERE NULLIF(TRIM(acquisition_channel), '') IS NULL)
        SELECT (SELECT COUNT(*) FROM b)                                                   AS users,
               (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw_orders) o JOIN b USING (user_id)) AS orders,
               (SELECT COUNT(DISTINCT o.user_id) FROM (SELECT DISTINCT * FROM raw_orders) o JOIN b USING (user_id)
                 WHERE o.status = 'delivered')                                             AS customers,
               (SELECT COALESCE(SUM(o.order_value), 0) FROM (SELECT DISTINCT * FROM raw_orders) o JOIN b USING (user_id)
                 WHERE o.status = 'delivered')                                             AS delivered_revenue;

-- [internal_accounts]
-- Issue 3: internal / test accounts on the company's own email domain
        WITH i AS (SELECT user_id, acquisition_channel FROM raw_users WHERE lower(email) LIKE '%@urbancart.in'),
             o AS (SELECT DISTINCT * FROM raw_orders)
        SELECT (SELECT COUNT(*) FROM i)                                                      AS users,
               (SELECT string_agg(DISTINCT acquisition_channel, ', ') FROM i)                 AS channels,
               (SELECT COUNT(*) FROM o JOIN i USING (user_id))                                AS orders,
               (SELECT COUNT(*) FROM o JOIN i USING (user_id) WHERE status = 'delivered')     AS delivered_orders,
               (SELECT MIN(n) FROM (SELECT COUNT(*) n FROM o JOIN i USING (user_id) GROUP BY o.user_id)) AS min_orders_per_user,
               (SELECT MAX(n) FROM (SELECT COUNT(*) n FROM o JOIN i USING (user_id) GROUP BY o.user_id)) AS max_orders_per_user,
               (SELECT AVG(order_value) FROM o JOIN i USING (user_id))                        AS avg_order_value,
               (SELECT AVG(order_value) FROM o)                                               AS avg_order_value_all;

-- [status_mix]
-- Issue 4: non-successful orders (excluded from revenue and customer counts per the brief)
        SELECT status, COUNT(*) AS orders_after_dedup FROM (SELECT DISTINCT * FROM raw_orders) GROUP BY status ORDER BY 2 DESC;

-- [passed_checks]
-- Checks that found nothing (reported so the reader knows they were run)
        WITH o AS (SELECT DISTINCT * FROM raw_orders)
        SELECT
          (SELECT COUNT(*) FROM o WHERE user_id NOT IN (SELECT user_id FROM raw_users))                  AS orphan_orders,
          (SELECT COUNT(*) FROM o JOIN raw_users u USING (user_id) WHERE o.order_date < u.signup_date)    AS orders_before_signup,
          (SELECT COUNT(*) FROM o WHERE order_date IS NULL OR order_value IS NULL OR status IS NULL)      AS null_order_fields,
          (SELECT COUNT(*) FROM raw_users WHERE signup_date IS NULL OR email IS NULL OR city IS NULL)     AS null_user_fields,
          (SELECT COUNT(*) FROM o WHERE order_value <= 0)                                                AS non_positive_values,
          (SELECT COUNT(*) FROM raw_users) - (SELECT COUNT(DISTINCT user_id) FROM raw_users)             AS duplicate_user_ids,
          (SELECT COUNT(*) FROM raw_users) - (SELECT COUNT(DISTINCT email) FROM raw_users)               AS duplicate_emails,
          (SELECT COUNT(DISTINCT status) FROM o)                                                         AS distinct_status_values,
          (SELECT COUNT(DISTINCT acquisition_channel) FROM raw_users WHERE acquisition_channel IS NOT NULL) AS distinct_channel_values,
          (SELECT COUNT(*) FROM raw_spend)                                                               AS spend_rows,
          (SELECT COUNT(DISTINCT channel) * COUNT(DISTINCT month) FROM raw_spend)                        AS spend_expected_rows,
          (SELECT COUNT(*) FROM raw_users WHERE signup_date < '2026-01-01' OR signup_date > '2026-06-30') AS signups_outside_window,
          (SELECT COUNT(*) FROM o WHERE order_date < '2026-01-01' OR order_date > '2026-06-30')          AS orders_outside_window,
          (SELECT MIN(order_value) FROM o) AS min_order_value, (SELECT MAX(order_value) FROM o) AS max_order_value,
          (SELECT COUNT(*) FROM raw_users WHERE user_id NOT IN (SELECT user_id FROM o))                  AS users_with_no_orders,
          (SELECT SUM(spend_inr) FROM raw_spend)                                                         AS total_spend;

-- ============================================================================
-- Clean layer
-- ============================================================================
-- [orders]
-- Handling 1: drop exact duplicate rows
        CREATE OR REPLACE VIEW orders AS SELECT DISTINCT * FROM raw_orders;

-- [users]
-- Handling 2 & 3: flag (not delete) unknown-channel users and internal accounts
        CREATE OR REPLACE VIEW users AS
        SELECT user_id, signup_date, city, email,
               NULLIF(TRIM(acquisition_channel), '')                   AS acquisition_channel,
               strftime(signup_date, '%Y-%m')                          AS signup_month,
               COALESCE(lower(email) LIKE '%@urbancart.in', false)     AS is_internal,
               NULLIF(TRIM(acquisition_channel), '') IS NULL           AS is_unknown_channel
        FROM raw_users;

-- [customers]
-- Handling 4: a customer = user with >= 1 DELIVERED order (cancelled/returned never count)
        CREATE OR REPLACE VIEW customers AS
        SELECT u.user_id, u.acquisition_channel, u.signup_month, u.is_internal, u.is_unknown_channel,
               COUNT(o.order_id)   AS delivered_orders,
               SUM(o.order_value)  AS revenue
        FROM users u
        JOIN orders o ON o.user_id = u.user_id AND o.status = 'delivered'
        GROUP BY ALL;

-- [customers_clean]
-- The population every channel metric is computed on
        CREATE OR REPLACE VIEW customers_clean AS
        SELECT * FROM customers WHERE NOT is_internal AND NOT is_unknown_channel;

-- [spend]
CREATE OR REPLACE VIEW spend AS SELECT month, channel, spend_inr FROM raw_spend;

-- ============================================================================
-- Q2 acquisition cost
-- ============================================================================
-- [q2]
-- Q2: total spend, new customers and CAC per paid channel (Jan–Jun)
    WITH nc AS (SELECT acquisition_channel AS channel, COUNT(*) AS new_customers FROM customers_clean GROUP BY 1),
         sp AS (SELECT channel, SUM(spend_inr) AS spend_inr FROM spend GROUP BY 1)
    SELECT sp.channel, sp.spend_inr, nc.new_customers, sp.spend_inr / nc.new_customers AS cac
    FROM sp JOIN nc USING (channel)
    ORDER BY cac;

-- ============================================================================
-- Q3 customer value
-- ============================================================================
-- [q3]
-- Q3: revenue per customer and repeat purchase rate per channel, including Organic
    SELECT acquisition_channel AS channel,
           COUNT(*)                                                   AS customers,
           SUM(revenue)                                               AS revenue,
           SUM(revenue) / COUNT(*)                                    AS revenue_per_customer,
           100.0 * COUNT(*) FILTER (WHERE delivered_orders >= 2) / COUNT(*) AS repeat_rate_pct
    FROM customers_clean
    GROUP BY 1
    ORDER BY revenue_per_customer DESC;

-- ============================================================================
-- Q4 LTV:CAC
-- ============================================================================
-- [q4]
-- Q4: LTV = revenue per customer x 30% contribution margin; LTV:CAC per paid channel
    WITH v AS (SELECT acquisition_channel AS channel, SUM(revenue) / COUNT(*) AS revenue_per_customer
               FROM customers_clean GROUP BY 1),
         sp AS (SELECT channel, SUM(spend_inr) AS spend_inr FROM spend GROUP BY 1),
         nc AS (SELECT acquisition_channel AS channel, COUNT(*) AS new_customers FROM customers_clean GROUP BY 1),
         c  AS (SELECT channel, sp.spend_inr / nc.new_customers AS cac FROM sp JOIN nc USING (channel))
    SELECT v.channel, v.revenue_per_customer, v.revenue_per_customer * 0.3 AS ltv, c.cac,
           (v.revenue_per_customer * 0.3) / c.cac AS ltv_to_cac
    FROM v JOIN c USING (channel)
    ORDER BY ltv_to_cac DESC;

-- ============================================================================
-- Q5 monthly CAC
-- ============================================================================
-- [q5]
-- Q5: CAC by month per paid channel; new customers grouped by SIGNUP month
    WITH nc AS (SELECT acquisition_channel AS channel, signup_month AS month, COUNT(*) AS new_customers
                FROM customers_clean GROUP BY 1, 2)
    SELECT s.month, s.channel, s.spend_inr, nc.new_customers, s.spend_inr / nc.new_customers AS cac
    FROM spend s LEFT JOIN nc USING (channel, month)
    ORDER BY s.channel, s.month;

-- ============================================================================
-- Q6 reconciliation
-- ============================================================================
-- [q6]
-- Q6: every user with a delivered order must land in exactly one bucket
    SELECT 'total distinct customers (deduped orders)' AS bucket, COUNT(DISTINCT user_id) AS customers
    FROM orders WHERE status = 'delivered'
    UNION ALL
    SELECT CASE WHEN is_internal THEN 'internal / test accounts'
                WHEN is_unknown_channel THEN 'unknown channel'
                ELSE acquisition_channel END, COUNT(*)
    FROM customers GROUP BY 1
    ORDER BY 1;

-- ============================================================================
-- Supporting
-- ============================================================================
-- [affiliate_before_after]
-- Impact of Issue 3: Affiliate metrics with and without the internal accounts
    WITH base AS (SELECT * FROM customers WHERE acquisition_channel = 'Affiliate'),
         sp   AS (SELECT SUM(spend_inr) AS spend FROM spend WHERE channel = 'Affiliate'),
         calc AS (
           SELECT 'with internal accounts (naive)' AS version, COUNT(*) AS customers,
                  SUM(revenue) / COUNT(*) AS revenue_per_customer,
                  100.0 * COUNT(*) FILTER (WHERE delivered_orders >= 2) / COUNT(*) AS repeat_rate_pct,
                  (SELECT spend FROM sp) / COUNT(*) AS cac
           FROM base
           UNION ALL
           SELECT 'without internal accounts (clean)', COUNT(*), SUM(revenue) / COUNT(*),
                  100.0 * COUNT(*) FILTER (WHERE delivered_orders >= 2) / COUNT(*), (SELECT spend FROM sp) / COUNT(*)
           FROM base WHERE NOT is_internal)
    SELECT version, customers, revenue_per_customer, repeat_rate_pct, cac,
           revenue_per_customer * 0.3 / cac AS ltv_to_cac
    FROM calc;

-- [return_rate]
-- Supporting: share of orders that were cancelled or returned, by channel (clean users)
    SELECT u.acquisition_channel AS channel, COUNT(*) AS orders,
           100.0 * COUNT(*) FILTER (WHERE o.status <> 'delivered') / COUNT(*) AS cancel_or_return_pct
    FROM orders o JOIN users u USING (user_id)
    WHERE NOT u.is_internal AND NOT u.is_unknown_channel
    GROUP BY 1 ORDER BY 3 DESC;

-- [conversion]
-- Supporting: signups -> customers conversion by channel (clean users)
    SELECT u.acquisition_channel AS channel, COUNT(*) AS signups,
           COUNT(c.user_id) AS customers, 100.0 * COUNT(c.user_id) / COUNT(*) AS conversion_pct
    FROM users u LEFT JOIN customers_clean c USING (user_id)
    WHERE NOT u.is_internal AND NOT u.is_unknown_channel
    GROUP BY 1 ORDER BY 4 DESC;

-- [repeat_by_month]
-- Supporting: repeat rate by signup month (shows cohort truncation at the end of the window)
    SELECT signup_month, COUNT(*) AS customers,
           100.0 * COUNT(*) FILTER (WHERE delivered_orders >= 2) / COUNT(*) AS repeat_rate_pct
    FROM customers_clean GROUP BY 1 ORDER BY 1;

-- [spend_by_quarter]
-- Supporting: spend by channel and quarter (baseline for the 20% cut)
    SELECT channel,
           SUM(spend_inr) FILTER (WHERE month <= '2026-03') AS q1_spend,
           SUM(spend_inr) FILTER (WHERE month >= '2026-04') AS q2_spend,
           SUM(spend_inr) AS h1_spend
    FROM spend GROUP BY 1 ORDER BY q2_spend DESC;
