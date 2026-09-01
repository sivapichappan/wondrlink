/**
 * TrialsAskCard — "I can search for you, I just need one thing."
 *
 * Reported from a real session: someone asked Sage to find her clinical
 * trials and got a general answer pointing at other websites. She was never
 * asked for her ZIP code, so the search could never run.
 *
 * The server had already done its part. `validate_trial_search_readiness`
 * returned the reason, the question and a composer prefill, and the chat
 * client threw all three away: `BotResponseCard` decided whether to render
 * the trials block by testing `trials.length > 0`, and an ask has no trials.
 * So the block existed, carried exactly what she needed, and never painted.
 *
 * TWO RULES THIS CARD FOLLOWS.
 *
 * It is never behind "Show details". When someone asks for trials and the
 * search is blocked, this question IS the answer to what they asked; hiding
 * it under a disclosure most people never open is how the bug felt in the
 * first place. It sits with the confirmation chips, which are always visible
 * for the same reason.
 *
 * Answering happens HERE, in the conversation she is already in. The Trials
 * screen sends people to `/chat/new?prefill=` because it has no composer of
 * its own; doing that from inside a thread would abandon the thread to answer
 * a question about it. So this fills the composer under her thumb instead.
 */

import { Microscope } from 'lucide-react-native';
import { Text, View } from 'react-native';

import { CardChip } from '@/components/chat/DealtCard';
import { router } from 'expo-router';
import { Colors, Fonts, Radius, Spacing } from '@/constants/theme';
import type { ChatTrialsAsk } from '@shared/types';

/** The server's own words for the ZIP ask, used when a legacy payload has
 *  none. The one branch that can produce that (`no_zip_code`) predates the
 *  just-in-time gate. */
const FALLBACK_PREFILL = 'My ZIP code is ';

interface Props {
  ask: ChatTrialsAsk;
  /** Puts text in the composer without sending it. */
  onPrefill?: (text: string) => void;
}

export function TrialsAskCard({ ask, onPrefill }: Props) {
  const prefill = ask.chat_prefill || FALLBACK_PREFILL;

  return (
    <View
      style={{
        backgroundColor: Colors.surfaceMuted,
        borderWidth: 1,
        borderColor: Colors.accentBorder,
        borderRadius: Radius.md,
        padding: Spacing.md,
        gap: Spacing.sm,
      }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Microscope size={14} color={Colors.textMuted} />
        <Text
          style={{
            color: Colors.textMuted,
            fontFamily: Fonts.sansMedium,
            fontSize: 11,
            letterSpacing: 0.5,
          }}>
          CLINICAL TRIALS
        </Text>
      </View>

      {/* The server's plain-words reason, verbatim. It already names exactly
          what is missing and why, and it is reviewed copy. */}
      <Text
        style={{
          color: Colors.textPrimary,
          fontFamily: Fonts.serif,
          fontSize: 16,
          lineHeight: 24,
        }}>
        {ask.message}
      </Text>

      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginTop: 2 }}>
        {onPrefill && (
          <CardChip label="Type it here" onPress={() => onPrefill(prefill)} />
        )}
        {/* Offered only when a document could actually answer it. */}
        {ask.offer_scan && (
          <CardChip
            label="Scan a report"
            onPress={() => router.push('/tools/report-scan' as never)}
          />
        )}
      </View>
    </View>
  );
}
