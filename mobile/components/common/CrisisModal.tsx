import { AlertCircle, Phone } from 'lucide-react-native';
import { Linking, Modal, Pressable, ScrollView, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { CRISIS_HELPLINES, CRISIS_MODAL, type Helpline } from '@shared/disclaimers';
import type { CrisisCategory } from '@/lib/safety/crisis-keywords';

interface Props {
  category: CrisisCategory | null;
  onContinue: () => void;
  onClose: () => void;
}

/**
 * Full-screen interceptor shown by the chat input when crisis-keywords
 * fires. Surfaces tap-to-call buttons for 911/988/741741 and gives the
 * user a small "continue anyway" escape that logs via Sentry.
 */
export function CrisisModal({ category, onContinue, onClose }: Props) {
  if (!category) return null;

  // Reorder so the most relevant helpline appears first per category.
  const ordered: Helpline[] = (() => {
    if (category === 'self_harm') {
      return [...CRISIS_HELPLINES].sort((a, b) => {
        if (a.number === '988' || a.number.startsWith('Text HOME')) return -1;
        if (b.number === '988' || b.number.startsWith('Text HOME')) return 1;
        return 0;
      });
    }
    return CRISIS_HELPLINES; // medical_emergency: 911 first (already the order)
  })();

  return (
    <Modal visible animationType="fade" transparent onRequestClose={onClose}>
      <View
        style={{
          flex: 1,
          backgroundColor: 'rgba(15,32,28,0.55)',
          justifyContent: 'flex-end',
        }}>
        <ScrollView
          style={{ maxHeight: '85%' }}
          contentContainerStyle={{
            backgroundColor: Colors.surface,
            borderTopLeftRadius: 20,
            borderTopRightRadius: 20,
            padding: 22,
            gap: 14,
          }}>
          <View style={{ alignItems: 'center', marginBottom: 4 }}>
            <View
              style={{
                width: 56,
                height: 56,
                borderRadius: 28,
                backgroundColor: Colors.emergencyBg,
                alignItems: 'center',
                justifyContent: 'center',
              }}>
              <AlertCircle size={28} color={Colors.danger} />
            </View>
          </View>

          <Text
            style={{
              fontFamily: Fonts.serifBold,
              fontSize: 22,
              color: Colors.textPrimary,
              textAlign: 'center',
            }}>
            {CRISIS_MODAL.title}
          </Text>

          <Text
            style={{
              color: Colors.textSecondary,
              fontSize: 14,
              lineHeight: 21,
              textAlign: 'center',
            }}>
            {CRISIS_MODAL.body}
          </Text>

          <View style={{ gap: 8 }}>
            {ordered.map((h) => (
              <Pressable
                key={h.name}
                onPress={() => Linking.openURL(h.tel).catch(() => {})}
                accessibilityRole="button"
                accessibilityLabel={`${h.name} — ${h.number}`}
                style={({ pressed }) => ({
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 12,
                  padding: 14,
                  borderRadius: Radius.md,
                  backgroundColor: pressed ? Colors.dangerPressed : Colors.danger,
                })}>
                <Phone size={18} color={Colors.surface} />
                <View style={{ flex: 1 }}>
                  <Text
                    style={{
                      color: Colors.surface,
                      fontFamily: Fonts.sansSemiBold,
                      fontSize: 14,
                    }}>
                    {h.name}
                  </Text>
                  <Text style={{ color: Colors.surface, fontSize: 12, opacity: 0.9 }}>
                    {h.number}
                  </Text>
                </View>
              </Pressable>
            ))}
          </View>

          <Button
            label={CRISIS_MODAL.continueButton}
            variant="ghost"
            fullWidth
            onPress={onContinue}
          />
          <Button label="Close" variant="ghost" fullWidth onPress={onClose} />
        </ScrollView>
      </View>
    </Modal>
  );
}
