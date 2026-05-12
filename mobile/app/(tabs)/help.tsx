import { Phone, ExternalLink, Sparkles } from 'lucide-react-native';
import { Linking, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Colors, Fonts, Radius } from '@/constants/theme';
import { CANCER_HELPLINES, CRISIS_HELPLINES, CONTACT, type Helpline } from '@shared/disclaimers';

export default function HelpScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 18, paddingBottom: 40 }}>
        <View>
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: 22, color: Colors.textPrimary }}>
            Get help
          </Text>
          <Text style={{ color: Colors.textMuted, fontSize: 13, marginTop: 4 }}>
            Tap any number to call directly.
          </Text>
        </View>

        <View style={{ gap: 8 }}>
          <SectionLabel>EMERGENCY · 24/7</SectionLabel>
          {CRISIS_HELPLINES.map((h) => (
            <HelplineCard key={h.name} h={h} variant="urgent" />
          ))}
        </View>

        <View style={{ gap: 8 }}>
          <SectionLabel>CANCER SUPPORT</SectionLabel>
          {CANCER_HELPLINES.map((h) => (
            <HelplineCard key={h.name} h={h} />
          ))}
        </View>

        <View style={{ gap: 8 }}>
          <SectionLabel>WONDRLINK</SectionLabel>
          <Pressable
            onPress={() => Linking.openURL(CONTACT.website).catch(() => {})}
            accessibilityRole="link"
            style={({ pressed }) => ({
              flexDirection: 'row',
              gap: 12,
              padding: 14,
              borderRadius: Radius.lg,
              borderWidth: 1,
              borderColor: Colors.border,
              backgroundColor: pressed ? Colors.sidebarBg : Colors.surface,
              alignItems: 'center',
            })}>
            <View
              style={{
                width: 40,
                height: 40,
                borderRadius: 20,
                backgroundColor: Colors.sidebarBg,
                alignItems: 'center',
                justifyContent: 'center',
              }}>
              <Sparkles size={18} color={Colors.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: 14 }}>
                Talk to a Personal Navigator
              </Text>
              <Text style={{ color: Colors.textSecondary, fontSize: 12, marginTop: 2 }}>
                WondrLink Foundation
              </Text>
            </View>
            <ExternalLink size={14} color={Colors.textMuted} />
          </Pressable>
        </View>

        <View
          style={{
            padding: 12,
            backgroundColor: Colors.sidebarBg,
            borderRadius: Radius.md,
          }}>
          <Text style={{ color: Colors.textSecondary, fontSize: 12, lineHeight: 18 }}>
            If you are experiencing a medical emergency, call 911 immediately. WondrChat is not
            equipped to handle emergencies.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <Text
      style={{
        color: Colors.textMuted,
        fontSize: 11,
        fontFamily: Fonts.sansMedium,
        letterSpacing: 0.5,
      }}>
      {children}
    </Text>
  );
}

function HelplineCard({ h, variant }: { h: Helpline; variant?: 'urgent' }) {
  const urgent = variant === 'urgent';
  return (
    <Pressable
      onPress={() => Linking.openURL(h.tel).catch(() => {})}
      accessibilityRole="button"
      accessibilityLabel={`${h.name} — ${h.number}`}
      style={({ pressed }) => ({
        flexDirection: 'row',
        gap: 12,
        padding: 14,
        borderRadius: Radius.lg,
        borderWidth: 1,
        borderColor: urgent ? Colors.danger : Colors.border,
        backgroundColor: urgent
          ? pressed
            ? '#8B1E18'
            : Colors.danger
          : pressed
            ? Colors.sidebarBg
            : Colors.surface,
        alignItems: 'center',
      })}>
      <View
        style={{
          width: 40,
          height: 40,
          borderRadius: 20,
          backgroundColor: urgent ? 'rgba(255,255,255,0.18)' : Colors.sidebarBg,
          alignItems: 'center',
          justifyContent: 'center',
        }}>
        <Phone size={18} color={urgent ? Colors.surface : Colors.primary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text
          style={{
            color: urgent ? Colors.surface : Colors.textPrimary,
            fontFamily: Fonts.sansSemiBold,
            fontSize: 14,
          }}>
          {h.name}
        </Text>
        <Text
          style={{
            color: urgent ? Colors.surface : Colors.textSecondary,
            fontSize: 12,
            marginTop: 2,
            opacity: urgent ? 0.9 : 1,
          }}>
          {h.number} · {h.desc}
        </Text>
      </View>
    </Pressable>
  );
}
