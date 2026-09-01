import { ChevronDown, ChevronUp } from 'lucide-react-native';
import { useMemo, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { splitAnswer } from '@/lib/answer-text';
import { PER_MESSAGE_FOOTER } from '@shared/disclaimers';
import type { ChatHistoryMessage } from '@shared/types';

import { ConfirmationChips } from './ConfirmationChips';
import { EscalationCard } from './EscalationCard';
import { MarkdownText } from './MarkdownText';
import { ResourcesRow } from './ResourcesRow';
import { TrialsAskCard } from './TrialsAskCard';
import { TrialsCards } from './TrialsCards';
import { UrgencyBanner } from './UrgencyBanner';

interface Props {
  message: ChatHistoryMessage;
  onPickFollowup: (text: string) => void;
  /** Long press on the answer text opens the select-text sheet. */
  onSelectText?: (content: string) => void;
  /** Fills the composer without sending — how a card asks a question that
   *  the patient answers in their own words. */
  onPrefill?: (text: string) => void;
}

const Divider = () => (
  <View style={{ height: 1, backgroundColor: Colors.border, marginVertical: 4 }} />
);

// Module-level, and they must stay that way: Markdown is React.memo, and an
// inline style object is a new identity every render, which defeats it.
const sectionFirst = { marginTop: Spacing.xs };
const sectionRest = {
  marginTop: Spacing.sm,
  paddingTop: Spacing.sm,
  borderTopWidth: 1,
  borderTopColor: Colors.border,
};
const labelStyle = {
  fontFamily: Fonts.sansSemiBold,
  fontSize: FontSize.sm,
  color: Colors.textSecondary,
  letterSpacing: 0.4,
  marginBottom: Spacing.xs,
};

export function BotResponseCard({ message, onPickFollowup, onSelectText, onPrefill }: Props) {
  const [expanded, setExpanded] = useState(false);
  const meta = message.metadata ?? {};
  const hasResources = !!meta.resources && meta.resources.length > 0;
  // The trials block is a union: results, or the server asking for the one
  // field that is blocking the search. Narrow on `error` before touching
  // `trials` — reading `.trials` off an ask is exactly how the ask was lost.
  const trialsBlock = meta.clinical_trials ?? null;
  const trialsAsk = trialsBlock?.error ? trialsBlock : null;
  const trialsResults = trialsBlock && !trialsBlock.error ? trialsBlock : null;
  const hasTrials = !!trialsResults && trialsResults.trials?.length > 0;

  const counts = [
    hasResources && `${meta.resources!.length} place${meta.resources!.length > 1 ? 's' : ''} to get help`,
    hasTrials &&
      `${trialsResults!.trials.length} trial${trialsResults!.trials.length > 1 ? 's' : ''}`,
    // follow-ups render beneath the card; sources live in the
    // composer's "+" menu, for the whole thread at once.
  ].filter(Boolean) as string[];

  const hasMore = counts.length > 0;

  const { lead, sections } = useMemo(() => splitAnswer(message.content), [message.content]);

  return (
    <View
      style={{
        backgroundColor: Colors.surface,
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.lg,
        paddingHorizontal: 12,
        paddingVertical: 10,
        gap: 6,
        shadowColor: Colors.textPrimary,
        shadowOpacity: 0.04,
        shadowRadius: 6,
        shadowOffset: { width: 0, height: 2 },
        elevation: 1,
      }}>
      {/* T1/T2/MH escalation card renders INSTEAD of the urgency banner
          (T3 and legacy urgency keep the banner). */}
      {meta.safety && meta.safety.tier !== 'T3' ? (
        <EscalationCard safety={meta.safety} crisisResources={meta.crisis_resources} />
      ) : (
        <UrgencyBanner urgency={meta.urgency} />
      )}

      {/* Only the answer text gets the long press, so pressing and holding
          "Show details" or a trial card below does nothing surprising. No style
          function on this Pressable: NativeWind strips visual styles from
          those, and the card's visuals live on the static View above anyway. */}
      <Pressable
        onLongPress={onSelectText ? () => onSelectText(message.content) : undefined}
        delayLongPress={350}
        accessibilityHint="Press and hold to copy or select text">
        {/* The lead is the sentence that answers the question, set a step
            larger so the eye lands on it first. Then labelled blocks, each
            separated by a hairline, so the whole answer can be skimmed by its
            labels or read straight down.

            An answer with no "## " headings comes back as all lead and no
            sections, which is EVERY answer already stored in the database, and
            renders exactly as it did before. That is why the split lives here
            rather than in the markdown styles. */}
        {!!lead && <MarkdownText variant="lead">{lead}</MarkdownText>}
        {sections.map((section, i) => (
          <View key={`${section.label}-${i}`} style={i === 0 && !lead ? sectionFirst : sectionRest}>
            <Text style={labelStyle}>{section.label}</Text>
            <MarkdownText>{section.body}</MarkdownText>
          </View>
        ))}
      </Pressable>

      {/* "Is that right?" chips — always visible (never behind Show details). */}
      {!!meta.pending_confirmations?.length && (
        <ConfirmationChips confirmations={meta.pending_confirmations} />
      )}

      {/* Same rule, same reason: when the trial search is blocked, the
          question that unblocks it IS the answer to what was just asked, so
          it cannot live behind a disclosure. */}
      {trialsAsk && <TrialsAskCard ask={trialsAsk} onPrefill={onPrefill} />}

      {hasMore && (
        <Pressable
          onPress={() => setExpanded((v) => !v)}
          accessibilityRole="button"
          accessibilityLabel={expanded ? 'Hide details' : 'Show details'}
          accessibilityState={{ expanded }}
          style={({ pressed }) => ({
            alignSelf: 'flex-start',
            marginTop: 4,
            opacity: pressed ? 0.85 : 1,
          })}>
          {/* Visuals live on a static inner View — NativeWind strips
              visual styles from Pressable style FUNCTIONS. */}
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              gap: 6,
              paddingVertical: 6,
              paddingHorizontal: 12,
              borderRadius: Radius.pill,
              borderWidth: 1,
              borderColor: Colors.border,
              backgroundColor: Colors.surfaceMuted,
            }}>
            <Text
              style={{ color: Colors.primary, fontFamily: Fonts.sansSemiBold, fontSize: 12 }}>
              {expanded ? 'Hide details' : `Show details · ${counts.join(', ')}`}
            </Text>
            {expanded ? (
              <ChevronUp size={14} color={Colors.primary} strokeWidth={2.4} />
            ) : (
              <ChevronDown size={14} color={Colors.primary} strokeWidth={2.4} />
            )}
          </View>
        </Pressable>
      )}

      {expanded && hasResources && (
        <>
          <Divider />
          <ResourcesRow resources={meta.resources} />
        </>
      )}

      {expanded && hasTrials && (
        <>
          <Divider />
          <TrialsCards trials={trialsResults} />
        </>
      )}

      {expanded && (
        <Text
          style={{
            color: Colors.textMuted,
            fontSize: 10,
            fontStyle: 'italic',
            fontFamily: Fonts.sans,
            marginTop: 2,
          }}>
          {PER_MESSAGE_FOOTER}
        </Text>
      )}
    </View>
  );
}
