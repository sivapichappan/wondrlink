import { AlertCircle, Phone } from 'lucide-react-native';
import { Linking, Pressable, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';
import { stripEmoji } from '@/lib/answer-text';
import type { ChatUrgency } from '@shared/types';

interface Props {
  urgency?: ChatUrgency | null;
}

export function UrgencyBanner({ urgency }: Props) {
  if (!urgency || !urgency.detected) return null;

  const isEmergency = (urgency.level || '').toLowerCase().includes('emergency');
  const bg = isEmergency ? Colors.emergencyBg : Colors.warningBg;
  const fg = isEmergency ? Colors.danger : Colors.warning;

  return (
    <View
      style={{
        flexDirection: 'row',
        gap: 10,
        padding: 12,
        borderRadius: Radius.md,
        backgroundColor: bg,
        borderWidth: 1,
        borderColor: fg,
      }}>
      <AlertCircle size={20} color={fg} />
      <View style={{ flex: 1, gap: 8 }}>
        <Text style={{ color: fg, fontFamily: Fonts.sansSemiBold, fontSize: 13, lineHeight: 18 }}>
          {urgency.level ?? 'Urgent'}
        </Text>
        <Text style={{ color: Colors.textPrimary, fontSize: 13, lineHeight: 19 }}>
          {/* The server's guidance string carries the same injected siren
              emoji the answer body does, and this banner IS the designed
              urgency marker — it does not need a cartoon of one. */}
          {stripEmoji(urgency.guidance || '') ||
            'Please contact your care team or seek emergency help if symptoms are severe.'}
        </Text>
        {isEmergency && (
          <Pressable
            onPress={() => Linking.openURL('tel:911').catch(() => {})}
            accessibilityRole="button"
            style={({ pressed }) => ({
              alignSelf: 'flex-start',
              opacity: pressed ? 0.85 : 1,
            })}>
            {/* Visuals live on a static inner View — NativeWind strips
                visual styles from Pressable style FUNCTIONS. */}
            <View
              style={{
                flexDirection: 'row',
                gap: 6,
                alignItems: 'center',
                paddingHorizontal: 12,
                paddingVertical: 6,
                borderRadius: 999,
                backgroundColor: Colors.danger,
              }}>
              <Phone size={14} color={Colors.surface} />
              <Text style={{ color: Colors.surface, fontFamily: Fonts.sansSemiBold, fontSize: 12 }}>
                Call 911
              </Text>
            </View>
          </Pressable>
        )}
      </View>
    </View>
  );
}
