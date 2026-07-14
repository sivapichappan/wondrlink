import { Beaker, HeartPulse, Microscope, Sparkles, X } from 'lucide-react-native';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';

interface Props {
  visible: boolean;
  onBuildProfile: () => void;
  onSkip: () => void;
}

const VALUE_BULLETS: { Icon: typeof Sparkles; title: string; body: string }[] = [
  {
    Icon: HeartPulse,
    title: 'Answers tuned to you',
    body: 'WondrChat uses your diagnosis, stage, and treatments to give responses that actually match your situation, not generic info.',
  },
  {
    Icon: Microscope,
    title: 'Better clinical-trial matches',
    body: 'Your biomarkers and ZIP code let us surface trials you might actually qualify for, with eligibility highlighted.',
  },
  {
    Icon: Beaker,
    title: 'Smarter visit prep + recaps',
    body: 'Tools like pre-visit questions and visit recap work much better when they know your treatment context.',
  },
];

export function WelcomeProfileModal({ visible, onBuildProfile, onSkip }: Props) {
  return (
    <Modal visible={visible} animationType="fade" transparent onRequestClose={onSkip}>
      <View style={styles.backdrop}>
        <Pressable style={styles.card} onPress={() => {}}>
          <View style={styles.header}>
            <View style={styles.heroBadge}>
              <Sparkles size={20} color={Colors.surface} />
            </View>
            <Pressable
              onPress={onSkip}
              accessibilityRole="button"
              accessibilityLabel="Close"
              hitSlop={8}
              style={({ pressed }) => [
                styles.closeBtn,
                pressed && { backgroundColor: Colors.surfaceMuted },
              ]}>
              <X size={18} color={Colors.textSecondary} />
            </Pressable>
          </View>

          <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false}>
            <Text style={styles.title}>Welcome to WondrChat</Text>
            <Text style={styles.subtitle}>
              An AI assistant that helps you understand your diagnosis, treatments, and trial
              options in everyday language, paired with a human Navigator when you need one.
            </Text>

            <View style={styles.calloutCard}>
              <Text style={styles.calloutHeader}>Just start chatting</Text>
              <Text style={styles.calloutBody}>
                No forms needed. WondrChat learns about you naturally as you talk, and may
                occasionally ask a gentle question. The more you chat, the more personal
                every answer gets.
              </Text>
            </View>

            <View style={{ gap: 12 }}>
              {VALUE_BULLETS.map((b) => (
                <View key={b.title} style={styles.bulletRow}>
                  <View style={styles.bulletIcon}>
                    <b.Icon size={16} color={Colors.primary} />
                  </View>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={styles.bulletTitle}>{b.title}</Text>
                    <Text style={styles.bulletBody}>{b.body}</Text>
                  </View>
                </View>
              ))}
            </View>
          </ScrollView>

          <View style={styles.footer}>
            <Button label="Start chatting" size="lg" fullWidth onPress={onSkip} />
            <Button label="Prefer a form? 2-minute setup" variant="ghost" fullWidth onPress={onBuildProfile} />
          </View>
        </Pressable>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(15, 32, 28, 0.55)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
  },
  card: {
    width: '100%',
    maxWidth: 440,
    maxHeight: '90%',
    backgroundColor: Colors.surface,
    borderRadius: Radius.lg,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOpacity: 0.25,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 },
    elevation: 14,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 4,
  },
  heroBadge: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.sidebarBg,
  },
  body: {
    paddingHorizontal: 18,
    paddingTop: 8,
    paddingBottom: 16,
    gap: 14,
  },
  title: {
    fontFamily: Fonts.serifBold,
    fontSize: 24,
    color: Colors.textPrimary,
    lineHeight: 30,
  },
  subtitle: {
    color: Colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
  },
  calloutCard: {
    backgroundColor: Colors.sidebarBg,
    borderRadius: Radius.md,
    padding: 12,
    gap: 4,
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary,
  },
  calloutHeader: {
    fontFamily: Fonts.sansSemiBold,
    fontSize: 14,
    color: Colors.textPrimary,
  },
  calloutBody: {
    color: Colors.textSecondary,
    fontSize: 13,
    lineHeight: 18,
  },
  bulletRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  bulletIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.sidebarBg,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
    marginTop: 1,
  },
  bulletTitle: {
    fontFamily: Fonts.sansSemiBold,
    fontSize: 14,
    color: Colors.textPrimary,
    marginBottom: 2,
  },
  bulletBody: {
    color: Colors.textSecondary,
    fontSize: 13,
    lineHeight: 18,
  },
  footer: {
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 16,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    backgroundColor: Colors.surface,
    gap: 6,
  },
});
