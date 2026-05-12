import { ExternalLink, Microscope } from 'lucide-react-native';
import { Linking, Pressable, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';
import type { ChatClinicalTrialsBlock } from '@shared/types';

interface Props {
  trials?: ChatClinicalTrialsBlock | null;
}

const BAND_LABELS: Record<string, { label: string; color: string }> = {
  strong: { label: 'Strong match', color: Colors.primary },
  moderate: { label: 'Moderate match', color: Colors.accent },
  general: { label: 'General match', color: Colors.textMuted },
};

export function TrialsCards({ trials }: Props) {
  if (!trials || !trials.trials || trials.trials.length === 0) return null;

  return (
    <View style={{ gap: 8 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Microscope size={14} color={Colors.textMuted} />
        <Text
          style={{
            color: Colors.textMuted,
            fontFamily: Fonts.sansMedium,
            fontSize: 11,
            letterSpacing: 0.5,
          }}>
          {trials.found} OF {trials.total} CLINICAL TRIALS
        </Text>
      </View>
      <View style={{ gap: 8 }}>
        {trials.trials.slice(0, 5).map((t) => {
          const band = t.relevance?.band ?? 'general';
          const tag = BAND_LABELS[band];
          const url = t.url || `https://clinicaltrials.gov/study/${t.nct_id}`;
          return (
            <View
              key={t.nct_id}
              style={{
                borderWidth: 1,
                borderColor: Colors.border,
                borderRadius: Radius.md,
                padding: 12,
                backgroundColor: Colors.surface,
                gap: 6,
              }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 8 }}>
                <Text style={{ color: Colors.textMuted, fontFamily: Fonts.sansMedium, fontSize: 11 }}>
                  {t.nct_id} · {t.phase || 'Phase n/a'}
                </Text>
                <Text
                  style={{
                    color: tag.color,
                    fontFamily: Fonts.sansSemiBold,
                    fontSize: 11,
                  }}>
                  {tag.label}
                </Text>
              </View>
              <Text
                style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 13, lineHeight: 18 }}
                numberOfLines={3}>
                {t.title}
              </Text>
              {t.status && (
                <Text style={{ color: Colors.textSecondary, fontSize: 12 }}>{t.status}</Text>
              )}
              <Pressable
                onPress={() => Linking.openURL(url).catch(() => {})}
                accessibilityRole="link"
                style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 }}>
                <ExternalLink size={12} color={Colors.primary} />
                <Text style={{ color: Colors.primary, fontFamily: Fonts.sansMedium, fontSize: 12 }}>
                  View on ClinicalTrials.gov
                </Text>
              </Pressable>
            </View>
          );
        })}
      </View>
    </View>
  );
}
