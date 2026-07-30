/**
 * The review queue (SPEC §5.4, adapted phone-first per owner direction D5).
 *
 * ONE CARD AT A TIME, not a list. A physician works through ~82 of these in a
 * single sitting, and the previous long-scrolling version refetched the whole
 * list after every decision, so her place on the page was lost 82 times. A
 * focused card has one position to keep and one obvious next action.
 *
 * The spec's one non-negotiable is kept: every quotation is ON the card with the
 * connection, never behind a tap — that is the difference between five seconds
 * and three minutes per edge.
 *
 * Both decisions are two deliberate taps. Approve shows the exact attestation
 * sentence before signing; reject shows which reason is about to be recorded.
 * Rejection is irreversible — there is no un-reject endpoint by design, since a
 * clinical decision is not something a script should be able to reopen — and it
 * used to be a single tap on one of eight identical small buttons.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, FileText, XCircle } from 'lucide-react-native';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, RefreshControl, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pill } from '@/components/ui/Pill';
import { Screen } from '@/components/ui/Screen';
import { SectionLabel } from '@/components/ui/SectionLabel';
import { TextField } from '@/components/ui/TextField';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { supabase } from '@/lib/supabase';
import {
  attestEdge,
  fetchReviewMeta,
  fetchReviewQueue,
  REJECTION_REASON_LABELS,
  REJECTION_REASONS,
  rewordEdge,
  type RejectionReason,
  type ReviewQueueItem,
} from '@/lib/api/review';

const RELATIONSHIP_LABELS: Record<string, string> = {
  side_effect_of: 'side effect of',
  co_occurs_with: 'often occurs with',
  indicated_by: 'indicated by',
  monitored_with: 'monitored with',
  mitigated_by: 'eased by',
  acts_through: 'acts through',
};

type CardMode = 'view' | 'reword' | 'reject' | 'confirmReject' | 'sign';

/** What a failed decision actually means, in words the reviewer can act on.
 *  Every failure used to read "that did not go through", which invites a retry
 *  even in the cases where retrying cannot possibly work. */
function decisionError(err: unknown): string {
  const e = err as { status?: number; body?: { error?: string } };
  switch (e?.body?.error ?? '') {
    case 'STALE_EDGE':
      return 'This connection changed while it was open, so nothing was signed. It has been reloaded; please read it again.';
    case 'SIGNED_EDGE':
      return 'This connection has already been signed, so its wording cannot change. Nothing was altered.';
    case 'NO_ATTESTATION_TEXT_FOR_TIER':
      return 'This kind of connection cannot be signed yet. The approval wording is still with legal review.';
    case 'REJECTION_REASON_REQUIRED':
      return 'Pick a reason before rejecting.';
    default:
      break;
  }
  if (e?.status === 401) return 'Your session has expired. Sign out and back in; nothing was signed.';
  if (e?.status === 403) return 'This account is not allowed to sign. Nothing was signed.';
  if (e?.status === undefined) return 'No connection. Nothing was signed; try again when you are back online.';
  return 'That did not go through. Nothing was signed; please try again.';
}

function ChainReasoning({ text }: { text: string }) {
  // A chained candidate rests on two quotations that each say something true,
  // combined by an argument no source makes. The reviewer has to be able to see
  // the argument and tell it apart from the quotations, so it is labelled as
  // proposed reasoning and styled unlike the serif quotation blocks.
  return (
    <View style={{ gap: Spacing.xs }}>
      <SectionLabel>Proposed reasoning, not a quotation</SectionLabel>
      <View
        style={{
          backgroundColor: Colors.surface,
          borderRadius: Radius.md,
          borderWidth: 1,
          borderColor: Colors.border,
          borderStyle: 'dashed',
          padding: Spacing.md,
        }}>
        <Text
          style={{
            fontFamily: Fonts.sans,
            fontSize: FontSize.sm,
            color: Colors.textSecondary,
            lineHeight: 20,
          }}>
          {text}
        </Text>
      </View>
    </View>
  );
}

function EvidenceBlock({ item }: { item: ReviewQueueItem }) {
  return (
    <View style={{ gap: Spacing.sm }}>
      {item.chain_reasoning ? <ChainReasoning text={item.chain_reasoning} /> : null}
      <SectionLabel>Evidence</SectionLabel>
      {item.evidence.length === 0 ? (
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.danger }}>
          No evidence rows. This should not be possible; do not approve.
        </Text>
      ) : (
        item.evidence.map((ev, i) => (
          <View
            key={`${item.id}-ev-${i}`}
            style={{
              backgroundColor: Colors.surfaceMuted,
              borderRadius: Radius.md,
              padding: Spacing.md,
              gap: Spacing.xs,
            }}>
            <Text
              style={{
                fontFamily: Fonts.serif,
                fontSize: FontSize.md,
                color: Colors.textPrimary,
                lineHeight: 22,
              }}>
              {/* An inferred (tier C) row has no quotation; it carries reasoning
                  instead. Rendering the empty string inside quote marks looked
                  like a loading bug. */}
              {ev.quoted_sentence ? `“${ev.quoted_sentence}”` : 'No quotation: this source is cited for context.'}
            </Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, flexWrap: 'wrap' }}>
              <FileText size={13} color={Colors.textMuted} />
              <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.xs, color: Colors.textSecondary, flexShrink: 1 }}>
                {ev.document_title ?? ev.section_ref}
                {ev.publisher ? ` · ${ev.publisher}` : ''}
              </Text>
              <Pill tone={ev.scope === 'general_survivorship' ? 'accent' : 'brand'}>
                {ev.scope === 'general_survivorship' ? 'SURVIVORSHIP' : 'BREAST'}
              </Pill>
            </View>
          </View>
        ))
      )}
    </View>
  );
}

function QueueCard({
  item,
  canSign,
  onDecided,
}: {
  item: ReviewQueueItem;
  canSign: boolean;
  onDecided: () => void;
}) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<CardMode>('view');
  const [pendingReason, setPendingReason] = useState<RejectionReason | null>(null);
  const [draft, setDraft] = useState(item.patient_phrasing ?? '');
  const [concerns, setConcerns] = useState<string[]>([]);
  const [copyProblems, setCopyProblems] = useState<string[]>([]);

  const refetch = useCallback(
    () => qc.invalidateQueries({ queryKey: ['review-queue'] }),
    [qc],
  );

  const reword = useMutation({
    mutationFn: () => rewordEdge(item.id, draft.trim()),
    onSuccess: (res) => {
      setConcerns(res.concerns ?? []);
      setCopyProblems([]);
      setMode('view');
      refetch();
    },
    onError: (err: unknown) => {
      const body = (err as { body?: { error?: string; problems?: string[] } })?.body;
      if (body?.error === 'COPY_RULES') setCopyProblems(body.problems ?? []);
      else setCopyProblems([decisionError(err)]);
    },
  });

  const attest = useMutation({
    mutationFn: (args: { decision: 'approve' | 'reject'; reason?: RejectionReason }) =>
      // item.edge_hash pins the signature to the card as it was rendered. If a
      // citation arrived while it sat open, the server refuses with 409 rather
      // than quietly signing something that was never read.
      attestEdge(item.id, args.decision, item.edge_hash, args.reason),
    onSuccess: () => {
      setMode('view');
      onDecided();
      refetch();
    },
    onError: (err: unknown) => {
      setMode('view');
      // A stale card is only recoverable by reloading it, so do that rather
      // than leaving her to guess that a retry will fail the same way.
      if ((err as { body?: { error?: string } })?.body?.error === 'STALE_EDGE') refetch();
    },
  });

  // Once a decision has been submitted this card takes no further action, in any
  // mode. Gating only the sign and reject panels left the view-mode buttons live
  // during the refetch, so a signed card still offered Approve.
  const decided = attest.isPending || attest.isSuccess;
  const busy = reword.isPending || attest.isPending || decided;
  const relationship = RELATIONSHIP_LABELS[item.relationship] ?? item.relationship;
  const noWording = !item.patient_phrasing?.trim();

  return (
    <Card gap={Spacing.md}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, flexWrap: 'wrap' }}>
        <Pill tone="brand">TIER {item.tier}</Pill>
        {item.urgency === 'urgent' ? <Pill tone="danger">URGENT</Pill> : null}
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.xs, color: Colors.textMuted }}>
          from {item.origin}
        </Text>
      </View>

      {/* the connection, in clinical terms, with the patient-facing name beneath
          it — she is approving both, so she has to see both. */}
      <View style={{ gap: Spacing.xs }}>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: FontSize.xl, color: Colors.textPrimary }}>
          {item.src.display}
        </Text>
        {item.src.display_patient ? (
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.xs, color: Colors.textMuted }}>
            patients see: {item.src.display_patient}
          </Text>
        ) : null}
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.textSecondary }}>
          {relationship}
        </Text>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: FontSize.xl, color: Colors.textPrimary }}>
          {item.dst.display}
        </Text>
        {item.dst.display_patient ? (
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.xs, color: Colors.textMuted }}>
            patients see: {item.dst.display_patient}
          </Text>
        ) : null}
      </View>

      <EvidenceBlock item={item} />

      <View style={{ gap: Spacing.sm }}>
        <SectionLabel>Patient wording</SectionLabel>
        {mode === 'reword' ? (
          <View style={{ gap: Spacing.sm }}>
            <TextField
              value={draft}
              onChangeText={setDraft}
              multiline
              placeholder="How should Sage ask the patient?"
            />
            {copyProblems.map((p, i) => (
              <Text key={i} style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.danger }}>
                {p}
              </Text>
            ))}
            <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
              <Button
                label="Save wording"
                onPress={() => reword.mutate()}
                loading={reword.isPending}
                disabled={!draft.trim()}
              />
              <Button label="Cancel" variant="ghost" onPress={() => setMode('view')} />
            </View>
          </View>
        ) : (
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.md, color: Colors.textPrimary, lineHeight: 22 }}>
            {item.patient_phrasing ?? 'No wording yet. Add it before approving.'}
          </Text>
        )}
        {concerns.map((c, i) => (
          <View
            key={i}
            style={{
              flexDirection: 'row',
              gap: Spacing.sm,
              backgroundColor: Colors.warningBg,
              borderRadius: Radius.md,
              padding: Spacing.md,
            }}>
            <AlertCircle size={16} color={Colors.warning} />
            <Text style={{ flex: 1, fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.warning }}>
              {c}
            </Text>
          </View>
        ))}
      </View>

      {mode === 'view' ? (
        <View style={{ gap: Spacing.sm }}>
          <Button
            label="Approve"
            fullWidth
            onPress={() => setMode('sign')}
            disabled={busy || noWording || item.attestation === null || !canSign}
            leadingIcon={<CheckCircle2 size={16} color={Colors.surface} />}
          />
          <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
            <Button
              label="Reject"
              variant="secondary"
              onPress={() => setMode('reject')}
              disabled={busy || item.attestation === null || !canSign}
              leadingIcon={<XCircle size={16} color={Colors.primary} />}
            />
            <Button label="Reword" variant="ghost" onPress={() => setMode('reword')} disabled={busy} />
          </View>
        </View>
      ) : null}

      {mode === 'view' && !canSign ? (
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.textSecondary }}>
          This account can suggest wording but cannot sign. Only an attesting physician
          approves or rejects a connection.
        </Text>
      ) : null}

      {mode === 'view' && canSign && item.attestation === null ? (
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.textSecondary }}>
          Tier {item.tier} connections cannot be signed or rejected yet. The wording for this
          kind of approval is still with legal review.
        </Text>
      ) : null}

      {mode === 'view' && canSign && noWording && item.attestation !== null ? (
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.textSecondary }}>
          Add the patient wording before approving. Reject and Reword still work.
        </Text>
      ) : null}

      {/* sign step: the exact sentence being signed, then one deliberate tap */}
      {mode === 'sign' && item.attestation ? (
        <View
          style={{
            gap: Spacing.md,
            backgroundColor: Colors.surfaceMuted,
            borderRadius: Radius.md,
            padding: Spacing.md,
          }}>
          <SectionLabel>You are signing</SectionLabel>
          <Text style={{ fontFamily: Fonts.serif, fontSize: FontSize.md, color: Colors.textPrimary, lineHeight: 22 }}>
            {item.attestation.text}
          </Text>
          <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
            <Button
              label="Sign and approve"
              onPress={() => attest.mutate({ decision: 'approve' })}
              loading={attest.isPending}
              disabled={decided}
            />
            <Button label="Back" variant="ghost" onPress={() => setMode('view')} />
          </View>
        </View>
      ) : null}

      {/* reject step one: pick a §13.1 reason. These are full-size targets now;
          they were 36pt and one tap was the whole irreversible decision. */}
      {mode === 'reject' ? (
        <View style={{ gap: Spacing.sm }}>
          <SectionLabel>Why is this wrong?</SectionLabel>
          {REJECTION_REASONS.map((reason) => (
            <Button
              key={reason}
              label={REJECTION_REASON_LABELS[reason]}
              variant="secondary"
              fullWidth
              onPress={() => {
                setPendingReason(reason);
                setMode('confirmReject');
              }}
              disabled={decided}
            />
          ))}
          <Button label="Back" variant="ghost" onPress={() => setMode('view')} />
        </View>
      ) : null}

      {/* reject step two: say plainly what is about to happen and that it is
          final, then one deliberate tap — the mirror of the sign step. */}
      {mode === 'confirmReject' && pendingReason ? (
        <View
          style={{
            gap: Spacing.md,
            backgroundColor: Colors.surfaceMuted,
            borderRadius: Radius.md,
            padding: Spacing.md,
          }}>
          <SectionLabel>Confirm rejection</SectionLabel>
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.md, color: Colors.textPrimary, lineHeight: 22 }}>
            Reject this connection as “{REJECTION_REASON_LABELS[pendingReason]}”. This is
            recorded with your name and cannot be undone.
          </Text>
          <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
            <Button
              label="Reject"
              variant="secondary"
              onPress={() => attest.mutate({ decision: 'reject', reason: pendingReason })}
              loading={attest.isPending}
              disabled={decided}
            />
            <Button label="Back" variant="ghost" onPress={() => setMode('reject')} />
          </View>
        </View>
      ) : null}

      {attest.isError ? (
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.danger }}>
          {decisionError(attest.error)}
        </Text>
      ) : null}
    </Card>
  );
}

export default function ReviewQueueScreen() {
  const meta = useQuery({ queryKey: ['review-meta'], queryFn: fetchReviewMeta, staleTime: 300_000 });
  const queue = useQuery({
    queryKey: ['review-queue'],
    queryFn: () => fetchReviewQueue('candidate'),
  });

  const items = useMemo(() => queue.data?.items ?? [], [queue.data]);
  const total = queue.data?.total ?? items.length;
  const [cursor, setCursor] = useState(0);
  const [decidedCount, setDecidedCount] = useState(0);

  // Items leave the list as they are decided, so a fixed index would skip the
  // one that slid into its place.
  useEffect(() => {
    if (cursor > 0 && cursor >= items.length) setCursor(Math.max(0, items.length - 1));
  }, [items.length, cursor]);

  const item = items[cursor];
  const canSign = meta.data?.reviewer.role === 'reviewer_attesting';

  if (queue.isLoading) {
    return (
      <Screen>
        <View style={{ paddingVertical: Spacing.xxl, alignItems: 'center' }}>
          <ActivityIndicator color={Colors.primary} />
        </View>
      </Screen>
    );
  }

  if (queue.isError) {
    return (
      <Screen gap={Spacing.lg}>
        <Card gap={Spacing.md}>
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.md, color: Colors.textPrimary }}>
            The review queue could not be loaded. Your patients&apos; app is unaffected.
          </Text>
          <Button label="Try again" onPress={() => queue.refetch()} loading={queue.isFetching} />
        </Card>
        <Button
          label="Sign out"
          variant="ghost"
          onPress={() => supabase.auth.signOut()}
        />
      </Screen>
    );
  }

  return (
    <Screen
      gap={Spacing.lg}
      keyboardAvoiding
      keyboardShouldPersistTaps
      refreshControl={
        <RefreshControl refreshing={queue.isFetching} onRefresh={() => queue.refetch()} tintColor={Colors.primary} />
      }>
      {/* progress. The server caps a page, so `total` is the real number of
          candidates rather than however many arrived in this response. */}
      <View style={{ gap: Spacing.xs }}>
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.textSecondary }}>
          {items.length > 0
            ? `Reviewing ${cursor + 1} of ${items.length} waiting${total > items.length ? ` (${total} in total)` : ''}`
            : 'Nothing is waiting for review.'}
          {decidedCount > 0 ? ` · ${decidedCount} decided this session` : ''}
        </Text>
        {meta.data ? (
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.xs, color: Colors.textMuted }}>
            Signed in as {meta.data.reviewer.name ?? 'reviewer'}. Every quotation shown was
            verified against its source character for character.
          </Text>
        ) : null}
      </View>

      {items.length === 0 ? (
        <Card>
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.md, color: Colors.textPrimary }}>
            {decidedCount > 0
              ? 'That is everything waiting for review. Thank you.'
              : 'Nothing is waiting for review.'}
          </Text>
        </Card>
      ) : null}

      {item ? (
        <QueueCard
          // Remount on a new item so no draft or panel state leaks across cards.
          key={item.id}
          item={item}
          canSign={canSign}
          onDecided={() => setDecidedCount((n) => n + 1)}
        />
      ) : null}

      {items.length > 0 ? (
        <View style={{ flexDirection: 'row', gap: Spacing.sm }}>
          <Button
            label="Previous"
            variant="ghost"
            onPress={() => setCursor((c) => Math.max(0, c - 1))}
            disabled={cursor === 0}
          />
          <Button
            label="Skip for now"
            variant="ghost"
            onPress={() => setCursor((c) => Math.min(items.length - 1, c + 1))}
            disabled={cursor >= items.length - 1}
          />
        </View>
      ) : null}

      <Button label="Sign out" variant="ghost" onPress={() => supabase.auth.signOut()} />
    </Screen>
  );
}
