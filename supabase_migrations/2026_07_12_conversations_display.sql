-- Migration: Promote conversations/messages to the display store
-- Date: 2026-07-12
-- Author: mobile navigation overhaul (assistant-home + drawer)
--
-- The `conversations` + `messages` tables already existed but were used only
-- as invisible LLM-memory (keyed by a hardcoded session_id='default'). The
-- mobile redesign surfaces them as the user-facing thread store (New chat,
-- Recents, Search, per-conversation titles). This migration adds the columns
-- and indexes that display model needs. It is additive and backwards-
-- compatible: the legacy `chat_messages` flat store is untouched so older
-- installed builds keep working during rollout.
--
--   - messages.metadata (JSONB): render metadata for the assistant turn
--     (sources, citations, follow-ups, clinical trials) so a reloaded thread
--     looks exactly like it did live. Mirrors chat_messages.metadata.
--   - conversations.updated_at (TIMESTAMPTZ): drives the Recents sort
--     ("most recently used first"). Defaults to now() for existing rows.
--   - indexes to make the Recents list and per-conversation reads fast.

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS metadata JSONB;

ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Seed updated_at for existing rows so Recents has a sensible initial order
-- (fall back to created_at where present).
UPDATE conversations
   SET updated_at = COALESCE(updated_at, created_at, now())
 WHERE updated_at IS NULL;

-- Recents list: a user's conversations, most-recently-updated first.
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
  ON conversations (user_id, updated_at DESC);

-- Per-conversation message reads (display history + LLM context), ordered.
CREATE INDEX IF NOT EXISTS idx_messages_conversation_seq
  ON messages (conversation_id, sequence_number);

-- Content search (drawer "Search chats") over message bodies, scoped by user.
CREATE INDEX IF NOT EXISTS idx_messages_user
  ON messages (user_id);

COMMENT ON COLUMN messages.metadata IS
  'Assistant-turn render metadata (sources, citations, followups, clinical_trials) for the multi-conversation display model.';
COMMENT ON COLUMN conversations.updated_at IS
  'Last activity timestamp; drives the Recents (most-recent-first) ordering in the mobile drawer.';
