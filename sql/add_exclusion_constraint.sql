-- SQL to prevent overlapping reservations on the same desk (Postgres)
-- Prerequisites:
-- 1) This uses the range type and gist index; ensure the extension is available:
--    CREATE EXTENSION IF NOT EXISTS btree_gist;
-- 2) The reservation table must use timestamptz columns (or adjust to timestamp)
-- 3) Run this as a DBA or a user with ALTER TABLE privileges.

-- Example:
-- ALTER TABLE reservation
--   ADD CONSTRAINT reservation_no_overlap
--   EXCLUDE USING GIST (
--     desk_id WITH =,
--     tstzrange(starttijd, eindtijd) WITH &&
--   );

-- If your columns are plain timestamp (without timezone), use "tsrange" instead of "tstzrange":
-- ALTER TABLE reservation
--   ADD CONSTRAINT reservation_no_overlap
--   EXCLUDE USING GIST (
--     desk_id WITH =,
--     tsrange(starttijd, eindtijd) WITH &&
--   );

-- Note: this enforces at the DB level that no two rows have overlapping time ranges for the same desk.
-- Run manually after reviewing and backing up your DB.
