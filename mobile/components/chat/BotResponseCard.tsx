import { Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';
import { PER_MESSAGE_FOOTER } from '@shared/disclaimers';
import type { ChatHistoryMessage } from '@shared/types';

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
  const meta = message.metadata ?? {};
  const hasResources = !!meta.resources && meta.resources.length > 0;
  const hasTrials = !!meta.clinical_trials && meta.clinical_trials.trials?.length > 0;
  const hasFollowups = !!meta.followups && meta.followups.length > 0;
  const hasSources = !!meta.sources && meta.sources.length > 0;

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
      <UrgencyBanner urgency={meta.urgency} />

      <MarkdownText>{message.content}</MarkdownText>

      <MessageActions messageText={message.content} />

      {hasResources && (
        <>
          <Divider />
          <ResourcesRow resources={meta.resources} />
        </>
      )}

      {hasTrials && (
        <>
          <Divider />
          <TrialsCards trials={meta.clinical_trials} />
        </>
      )}

      {hasFollowups && (
        <>
          <Divider />
          <FollowupChips followups={meta.followups} onPick={onPickFollowup} />
        </>
      )}

      {hasSources && (
        <>
          <Divider />
          <SourceCitations sources={meta.sources} />
        </>
      )}

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
    </View>
  );
}
