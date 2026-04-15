-- WAL lets readers proceed concurrently with a writer (important since the
-- MCP server and CLI may touch the same DB).
PRAGMA journal_mode = WAL;
-- Wait up to 5s for a competing writer before raising SQLITE_BUSY.
PRAGMA busy_timeout = 5000;
-- NORMAL is safe under WAL and noticeably faster than FULL.
PRAGMA synchronous = NORMAL;
-- Required for ON DELETE CASCADE on the derived index tables.
PRAGMA foreign_keys = ON;
