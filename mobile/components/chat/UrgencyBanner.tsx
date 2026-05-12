import { AlertCircle, Phone } from 'lucide-react-native';
import { Linking, Pressable, Text, View } from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';
import type { ChatUrgency } from '@shared/types';

interface Props {
  urgency?: ChatUrgency | null;
}

export function UrgencyBanner({ urgency }: Props) {
  if (!urgency || !urgency.detected) return null;

  const isEmergency = (urgency.level || '').toLowerCase().includes('emergency');
  const bg = isEmergency ? '#FFEDEC' : Colors.warningBg;
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
          {urgency.guidance || 'Please contact your care team or seek emergency help if symptoms are severe.'}
        </Text>
        {isEmergency && (
          <Pressable
            onPress={() => Linking.openURL('tel:911').catch(() => {})}
            accessibilityRole="button"
            style={({ pressed }) => ({
              flexDirection: 'row',
              gap: 6,
              alignItems: 'center',
              alignSelf: 'flex-start',
              paddingHorizontal: 12,
              paddingVertical: 6,
              borderRadius: 999,
              backgroundColor: pressed ? '#8B1E18' : Colors.danger,
            })}>
            <Phone size={14} color={Colors.surface} />
            <Text style={{ color: Colors.surface, fontFamily: Fonts.sansSemiBold, fontSize: 12 }}>
              Call 911
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}
