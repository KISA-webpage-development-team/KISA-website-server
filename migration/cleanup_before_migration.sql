-- Run against the production RDS MySQL database immediately before the copy.
--
-- The Postgres schema enforces two foreign keys that MySQL never had, and
-- production carries three rows that reference users who no longer exist. The
-- copy aborts on them. Both rows belong to deleted accounts, so the fix is to
-- retire the dead references rather than to weaken the target schema.
--
-- Verified against production on 2026-08-25: exactly 3 rows match.
--
--   mysql --default-character-set=utf8mb4 -h <rds-host> -u <user> -p ebdb \
--         < cleanup_before_migration.sql

START TRANSACTION;

-- order 188 belongs to a deleted account. The Postgres schema declares
-- order.email as ON DELETE SET NULL, so NULL is what that account's deletion
-- should have left behind. The order and its 3 items are preserved.
UPDATE `order` o
  LEFT JOIN users u ON o.email = u.email
SET o.email = NULL
WHERE o.email IS NOT NULL AND u.email IS NULL;

-- APNS device tokens for deleted accounts. Nothing can be delivered to them,
-- and notificationARNs.email is a primary key so it cannot be nulled.
DELETE n FROM notificationARNs n
  LEFT JOIN users u ON n.email = u.email
WHERE u.email IS NULL;

-- Both must report 0 before committing.
SELECT COUNT(*) AS orphan_orders FROM `order` o
  LEFT JOIN users u ON o.email = u.email
  WHERE o.email IS NOT NULL AND u.email IS NULL;
SELECT COUNT(*) AS orphan_arns FROM notificationARNs n
  LEFT JOIN users u ON n.email = u.email
  WHERE u.email IS NULL;

COMMIT;
