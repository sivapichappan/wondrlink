import { ChevronRight, Sparkles } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';

interface Props {
  onPress: () => void;
}

/**
 * Gentle lifecycle nudge — shown while WondrChat is still getting to know a
 * profile-less user. Passive framing: chatting is the primary path; the
 * 2-minute form is an optional accelerator.
 */
export function ProfileNudgeBanner({ onPress }: Props) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="Optional 2-minute setup for a head start"
      style={({ pressed }) => [
        styles.outer,
        pressed && { backgroundColor: Colors.surfaceMuted },
      ]}>
      <View style={styles.row}>
        <View style={styles.icon}>
          <Sparkles size={16} color={Colors.surface} />
        </View>
        <View style={styles.text}>
          <Text style={styles.title}>Sage learns about you as you chat</Text>
          <Text style={styles.subtitle} numberOfLines={2} ellipsizeMode="tail">
            Just start talking. Want a head start? An optional 2-minute setup is here.
          </Text>
        </View>
        <ChevronRight size={18} color={Colors.primary} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  outer: {
    marginHorizontal: 12,
    marginTop: 8,
    backgroundColor: Colors.sidebarBg,
    borderRadius: Radius.md,
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  icon: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  text: {
    flex: 1,
    minWidth: 0,
    marginRight: 8,
  },
  title: {
    fontFamily: Fonts.sansSemiBold,
    fontSize: 13,
    color: Colors.textPrimary,
  },
  subtitle: {
    color: Colors.textSecondary,
    fontSize: 11,
    lineHeight: 15,
    marginTop: 2,
  },
});
