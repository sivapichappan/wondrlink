import { Sparkles } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';
import type { HeroResponse } from '@shared/types';

interface Props {
  hero?: HeroResponse;
  onAskSuggestion?: (question: string) => void;
}

export function HeroCard({ hero, onAskSuggestion }: Props) {
  if (!hero) return null;

  const greeting = hero.first_name ? `Hi, ${hero.first_name}` : 'Welcome back';

  return (
    <View
      style={{
        backgroundColor: Colors.surface,
        borderWidth: 1,
        borderColor: Colors.border,
        borderRadius: Radius.lg,
        padding: 16,
        gap: 10,
      }}>
      <Text style={{ fontFamily: Fonts.serifBold, fontSize: 22, color: Colors.textPrimary }}>
        {greeting}
      </Text>

      {hero.phase_description ? (
        <Text style={{ color: Colors.textSecondary, fontSize: 14, lineHeight: 20 }}>
          {hero.phase_description}
        </Text>
      ) : null}

      {hero.last_visit ? (
        <View
          style={{
            marginTop: 4,
            backgroundColor: Colors.sidebarBg,
            paddingHorizontal: 10,
            paddingVertical: 8,
            borderRadius: Radius.sm,
          }}>
          <Text style={{ color: Colors.textSecondary, fontSize: 12 }}>
            Last visit · {hero.last_visit.when_pretty}
            {hero.last_visit.pending_followups
              ? ` · ${hero.last_visit.pending_followups} follow-up${hero.last_visit.pending_followups === 1 ? '' : 's'}`
              : ''}
            {hero.last_visit.changed_treatment ? ' · treatment updated' : ''}
          </Text>
        </View>
      ) : null}

      {hero.suggestions && hero.suggestions.length > 0 ? (
        <View style={{ gap: 6, marginTop: 4 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Sparkles size={12} color={Colors.textMuted} />
            <Text
              style={{
                color: Colors.textMuted,
                fontFamily: Fonts.sansMedium,
                fontSize: 11,
                letterSpacing: 0.5,
              }}>
              SUGGESTED QUESTIONS
            </Text>
          </View>
          <View style={{ gap: 6 }}>
            {hero.suggestions.map((q, i) => (
              <Pressable
                key={i}
                onPress={() => onAskSuggestion?.(q)}
                accessibilityRole="button"
                accessibilityLabel={q}
                accessibilityHint="Send this question to chat"
                style={({ pressed }) => ({
                  paddingHorizontal: 12,
                  paddingVertical: 10,
                  borderRadius: Radius.md,
                  backgroundColor: pressed ? Colors.surfaceMuted : Colors.sidebarBg,
                  borderWidth: 1,
                  borderColor: Colors.border,
                })}>
                <Text
                  numberOfLines={2}
                  ellipsizeMode="tail"
                  style={{ color: Colors.textPrimary, fontSize: 13, lineHeight: 18 }}>
                  {q}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}
    </View>
  );
}
