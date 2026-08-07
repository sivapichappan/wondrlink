-- chat_turn: one row per question a patient asks, so the answer survives them
-- leaving the app.
--
-- /api/chat runs 15 to 40 seconds and already writes the answer to `messages`
-- BEFORE it returns. What was missing is an address the client can ask about
-- afterwards: iOS suspends the app, the socket dies, the fetch rejects, and for
-- a brand-new thread the client never even learned which conversation the
-- server made. So the answer sat in Postgres and nothing ever asked for it.
--
-- The client mints `client_turn_id` before the request, which makes it three
-- things at once: a recovery address that survives a process kill, an
-- idempotency key so a retry replays the stored answer instead of paying for a
-- second one, and the join point for the "tell me when it is ready" push.
--
-- WHY TWO FLAGS AND NOT ONE COLUMN. The handler and the notify request race,
-- and a single "notify wanted" value cannot close it: the write can land after
-- the handler read it and be seen by nobody. Each side instead performs one
-- atomic UPDATE that returns the OTHER side's flag, and whoever sees it set
-- claims `notified` with a compare-and-swap (update ... where notified = false).
-- Every interleaving then sends exactly one notification, or none.

CREATE TABLE IF NOT EXISTS chat_turn (
    client_turn_id   TEXT PRIMARY KEY,
    user_id          UUID NOT NULL,
    conversation_id  UUID,
    -- pending | answered. Deliberately NOT an inline CHECK: Postgres would name
    -- it chat_turn_status_check, and re-declaring that name later fails.
    status           TEXT NOT NULL DEFAULT 'pending',
    notify_requested BOOLEAN NOT NULL DEFAULT false,
    notified         BOOLEAN NOT NULL DEFAULT false,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    answered_at      TIMESTAMPTZ
);

-- Recovery reads by primary key. This index is for pruning and for looking at
-- a single account's recent turns while debugging.
CREATE INDEX IF NOT EXISTS idx_chat_turn_user_created
    ON chat_turn (user_id, created_at DESC);

-- Rows are tiny and short-lived by nature: a turn matters for the two minutes
-- the client might still be recovering it. Nothing prunes them yet on purpose
-- (a cron that deletes rows is worth having only once there is volume to
-- justify it), but anything older than 7 days is safe to delete:
--   DELETE FROM chat_turn WHERE created_at < now() - interval '7 days';

COMMENT ON TABLE chat_turn IS
    'One row per chat question: recovery address, idempotency key, and the '
    'handshake for the answer-ready push. Prunable after ~7 days.';
