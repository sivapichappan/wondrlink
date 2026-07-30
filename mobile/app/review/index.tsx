/**
 * The review queue (SPEC §5.4, adapted phone-first per owner direction D5).
 *
 * One candidate per card, triage-style. The spec's one non-negotiable is kept:
 * every quotation is ON the card with the connection, never behind a tap —
 * that is the difference between five seconds and three minutes per edge.
 * Desktop keyboard shortcuts become large tap targets; approve is an explicit
 * two-step (show the exact attestation sentence, then sign) because a
 * signature minted by a stray tap is not a signature.
 *
 * Rejecting requires one of the eight §13.1 structured reasons — those
 * rejections are the extraction pipeline's only real evaluation signal.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, FileText, XCircle } from 'lucide-react-native';
import { useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pill } from '@/components/ui/Pill';
import { Screen } from '@/components/ui/Screen';
import { SectionLabel } from '@/components/ui/SectionLabel';
import { TextField } from '@/components/ui/TextField';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
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

type CardMode = 'view' | 'reword' | 'reject' | 'sign';

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
              “{ev.quoted_sentence}”
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

function QueueCard({ item }: { item: ReviewQueueItem }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<CardMode>('view');
  const [draft, setDraft] = useState(item.patient_phrasing ?? '');
  const [concerns, setConcerns] = useState<string[]>([]);
  const [copyProblems, setCopyProblems] = useState<string[]>([]);

  const done = () => qc.invalidateQueries({ queryKey: ['review-queue'] });

  const reword = useMutation({
    mutationFn: () => rewordEdge(item.id, draft.trim()),
    onSuccess: (res) => {
      setConcerns(res.concerns ?? []);
      setCopyProblems([]);
      setMode('view');
      done();
    },
    onError: (err: unknown) => {
      const body = (err as { body?: { error?: string; problems?: string[] } })?.body;
      if (body?.error === 'COPY_RULES') setCopyProblems(body.problems ?? []);
      else setCopyProblems(['Could not save the new wording. Please try again.']);
    },
  });

  const attest = useMutation({
    mutationFn: (args: { decision: 'approve' | 'reject'; reason?: RejectionReason }) =>
      attestEdge(item.id, args.decision, args.reason),
    // Leave the sign/reject panel immediately. The card stays mounted while
    // the queue refetches, so keeping live buttons on screen invites a second
    // signature on an edge that was just signed.
    onSuccess: () => {
      setMode('view');
      done();
    },
  });

  // Belt and braces on the same window: once a decision has been submitted,
  // this card takes no further action regardless of what is still rendered.
  const decided = attest.isPending || attest.isSuccess;

  const relationship = RELATIONSHIP_LABELS[item.relationship] ?? item.relationship;
  const busy = reword.isPending || attest.isPending;

  return (
    <Card gap={Spacing.md}>
      {/* status row */}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, flexWrap: 'wrap' }}>
        <Pill tone="brand">TIER {item.tier}</Pill>
        {item.urgency === 'urgent' ? <Pill tone="danger">URGENT</Pill> : null}
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.xs, color: Colors.textMuted }}>
          from {item.origin}
        </Text>
      </View>

      {/* the connection */}
      <View style={{ gap: 2 }}>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: FontSize.xl, color: Colors.textPrimary }}>
          {item.src.display}
        </Text>
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.textSecondary }}>
          {relationship}
        </Text>
        <Text style={{ fontFamily: Fonts.serifBold, fontSize: FontSize.xl, color: Colors.textPrimary }}>
          {item.dst.display}
        </Text>
      </View>

      <EvidenceBlock item={item} />

      {/* patient wording */}
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
              <Button label="Save wording" size="sm" onPress={() => reword.mutate()} loading={reword.isPending} />
              <Button label="Cancel" size="sm" variant="ghost" onPress={() => setMode('view')} />
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

      {/* actions */}
      {mode === 'view' ? (
        <View style={{ flexDirection: 'row', gap: Spacing.sm, flexWrap: 'wrap' }}>
          <Button
            label="Approve"
            size="md"
            onPress={() => setMode('sign')}
            disabled={busy || !item.patient_phrasing || item.attestation === null}
            leadingIcon={<CheckCircle2 size={16} color={Colors.surface} />}
          />
          <Button
            label="Reject"
            size="md"
            variant="secondary"
            onPress={() => setMode('reject')}
            disabled={busy}
            leadingIcon={<XCircle size={16} color={Colors.primary} />}
          />
          <Button label="Reword" size="md" variant="ghost" onPress={() => setMode('reword')} disabled={busy} />
        </View>
      ) : null}

      {mode === 'view' && item.attestation === null ? (
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.textSecondary }}>
          Tier {item.tier} connections cannot be signed yet. The wording for this kind of
          approval is still with legal review.
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

      {/* reject step: §13.1 structured reasons, one tap each */}
      {mode === 'reject' ? (
        <View style={{ gap: Spacing.sm }}>
          <SectionLabel>Why is this wrong?</SectionLabel>
          {REJECTION_REASONS.map((reason) => (
            <Button
              key={reason}
              label={REJECTION_REASON_LABELS[reason]}
              variant="secondary"
              size="sm"
              fullWidth
              onPress={() => attest.mutate({ decision: 'reject', reason })}
              disabled={decided}
            />
          ))}
          <Button label="Back" variant="ghost" size="sm" onPress={() => setMode('view')} />
        </View>
      ) : null}

      {attest.isError ? (
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.danger }}>
          That did not go through. Nothing was signed; please try again.
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

  return (
    <Screen gap={Spacing.lg}>
      {meta.data ? (
        <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.sm, color: Colors.textSecondary }}>
          Signed in as {meta.data.reviewer.name ?? 'reviewer'}. Every connection you approve
          here can reach patients; every quotation shown was verified against its source
          character for character.
        </Text>
      ) : null}

      {queue.isLoading ? (
        <View style={{ paddingVertical: Spacing.xxl, alignItems: 'center' }}>
          <ActivityIndicator color={Colors.primary} />
        </View>
      ) : null}

      {queue.isError ? (
        <Card>
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.md, color: Colors.textPrimary }}>
            The review queue could not be loaded. Your patients&apos; app is unaffected; try
            again in a moment.
          </Text>
        </Card>
      ) : null}

      {queue.data && queue.data.items.length === 0 ? (
        <Card>
          <Text style={{ fontFamily: Fonts.sans, fontSize: FontSize.md, color: Colors.textPrimary }}>
            Nothing is waiting for review.
          </Text>
        </Card>
      ) : null}

      {queue.data?.items.map((item) => <QueueCard key={item.id} item={item} />)}
    </Screen>
  );
}
