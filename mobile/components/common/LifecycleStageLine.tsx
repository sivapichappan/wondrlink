/**
 * LifecycleStageLine — the subtle "Getting to know you" cue.
 *
 * One quiet muted line showing where the patient is in the passive lifecycle,
 * so the occasional question in chat has visible context. Deliberately not a
 * progress bar or journey UI (locked decision: subtle stage cue only).
 */

import { Sparkles } from 'lucide-react-native';
import { Text, View } from 'react-native';

import { Colors, FontSize, Spacing } from '@/constants/theme';
import type { LifecycleStage } from '@shared/types';

export const LIFECYCLE_LABELS: Record<LifecycleStage, string> = {
  getting_to_know_you: 'Getting to know you',
  understanding_treatment: 'Understanding your treatment',
  connected: 'Connecting the dots',
  trial_ready: 'Trial ready',
};

export function LifecycleStageLine({ stage }: { stage?: LifecycleStage | null }) {
  const label = LIFECYCLE_LABELS[stage ?? 'getting_to_know_you'] ?? LIFECYCLE_LABELS.getting_to_know_you;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: Spacing.sm }}>
      <Sparkles size={12} color={Colors.textMuted} />
      <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted }}>{label}</Text>
    </View>
  );
}
