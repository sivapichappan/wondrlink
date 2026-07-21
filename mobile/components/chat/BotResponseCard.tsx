import { ChevronDown, ChevronUp } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';
import { PER_MESSAGE_FOOTER } from '@shared/disclaimers';
import type { ChatHistoryMessage } from '@shared/types';

import { ConfirmationChips } from './ConfirmationChips';
import { EscalationCard } from './EscalationCard';
import { FollowupChips } from './FollowupChips';
import { MarkdownText } from './MarkdownText';
import { MessageActions } from './MessageActions';
import { ResourcesRow } from './ResourcesRow';
import { SourceCitations } from './SourceCitations';
import { TrialsCards } from './TrialsCards';
import { UrgencyBanner } from './UrgencyBanner';

interface Props {
  message: ChatHistoryMessage;
  onPickFollowup: (text: string) => void;
}

const Divider = () => (
  <View style={{ height: 1, backgroundColor: Colors.border, marginVertical: 4 }} />
);

export function BotResponseCard({ message, onPickFollowup }: Props) {
  const [expanded, setExpanded] = useState(false);
  const meta = message.metadata ?? {};
  const hasResources = !!meta.resources && meta.resources.length > 0;
  const hasTrials = !!meta.clinical_trials && meta.clinical_trials.trials?.length > 0;
  const hasFollowups = !!meta.followups && meta.followups.length > 0;
  const hasSources = !!meta.sources && meta.sources.length > 0;

  const counts = [
    hasResources && `${meta.resources!.length} resource${meta.resources!.length > 1 ? 's' : ''}`,
    hasTrials &&
      `${meta.clinical_trials!.trials.length} trial${meta.clinical_trials!.trials.length > 1 ? 's' : ''}`,
    hasFollowups && `${meta.followups!.length} follow-up${meta.followups!.length > 1 ? 's' : ''}`,
    hasSources && `${meta.sources!.length} source${meta.sources!.length > 1 ? 's' : ''}`,
  ].filter(Boolean) as string[];

  const hasMore = counts.length > 0;

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

      <MarkdownText>{message.content}</MarkdownText>

      {/* "Is that right?" chips — always visible (never behind Show details). */}
      {!!meta.pending_confirmations?.length && (
        <ConfirmationChips confirmations={meta.pending_confirmations} />
      )}

      <MessageActions messageText={message.content} />

      {hasMore && (
        <Pressable
          onPress={() => setExpanded((v) => !v)}
          accessibilityRole="button"
          accessibilityLabel={expanded ? 'Hide details' : 'Show details'}
          accessibilityState={{ expanded }}
          style={({ pressed }) => ({
            alignSelf: 'flex-start',
            flexDirection: 'row',
            alignItems: 'center',
            gap: 6,
            marginTop: 4,
            paddingVertical: 6,
            paddingHorizontal: 12,
            borderRadius: Radius.pill,
            borderWidth: 1,
            borderColor: Colors.border,
            backgroundColor: pressed ? Colors.primarySoft : Colors.surfaceMuted,
          })}>
          <Text
            style={{ color: Colors.primary, fontFamily: Fonts.sansSemiBold, fontSize: 12 }}>
            {expanded ? 'Hide details' : `Show details · ${counts.join(', ')}`}
          </Text>
          {expanded ? (
            <ChevronUp size={14} color={Colors.primary} strokeWidth={2.4} />
          ) : (
            <ChevronDown size={14} color={Colors.primary} strokeWidth={2.4} />
          )}
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
          <TrialsCards trials={meta.clinical_trials} />
        </>
      )}

      {expanded && hasFollowups && (
        <>
          <Divider />
          <FollowupChips followups={meta.followups} onPick={onPickFollowup} />
        </>
      )}

      {expanded && hasSources && (
        <>
          <Divider />
          <SourceCitations sources={meta.sources} />
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
