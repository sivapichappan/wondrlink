import { AlertOctagon, ChevronRight, ExternalLink, Phone, Sparkles } from 'lucide-react-native';
import { Linking, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Colors, Fonts, Radius } from '@/constants/theme';
import { CANCER_HELPLINES, CRISIS_HELPLINES, CONTACT, type Helpline } from '@shared/disclaimers';

export default function HelpScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 20, paddingBottom: 40 }}>
        <View>
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: 24, color: Colors.textPrimary }}>
            Get help
          </Text>
          <Text style={{ color: Colors.textMuted, fontSize: 13, marginTop: 4 }}>
            Tap any number to call directly.
          </Text>
        </View>

        <EmergencyBanner />

        <Section title="Crisis support · 24/7" tone="urgent">
          {CRISIS_HELPLINES.map((h, i, arr) => (
            <HelplineRow key={h.name} h={h} urgent showDivider={i < arr.length - 1} />
          ))}
        </Section>

        <Section title="Cancer support">
          {CANCER_HELPLINES.map((h, i, arr) => (
            <HelplineRow key={h.name} h={h} showDivider={i < arr.length - 1} />
          ))}
        </Section>

        <Section title="WondrLink">
          <Pressable
            onPress={() => Linking.openURL(CONTACT.website).catch(() => {})}
            accessibilityRole="link"
            accessibilityLabel="Talk to a Personal Navigator"
            style={({ pressed }) => ({
              backgroundColor: pressed ? Colors.sidebarBg : Colors.surface,
            })}>
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                padding: 14,
              }}>
              <View
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 20,
                  backgroundColor: Colors.sidebarBg,
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginRight: 12,
                }}>
                <Sparkles size={18} color={Colors.primary} />
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text
                  style={{
                    color: Colors.textPrimary,
                    fontFamily: Fonts.sansSemiBold,
                    fontSize: 15,
                  }}>
                  Talk to a Personal Navigator
                </Text>
                <Text style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>
                  wondrlinkfoundation.org
                </Text>
              </View>
              <ExternalLink size={16} color={Colors.primary} style={{ marginLeft: 8 }} />
            </View>
          </Pressable>
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}

function EmergencyBanner() {
  return (
    <View
      style={{
        flexDirection: 'row',
        gap: 10,
        padding: 14,
        borderRadius: Radius.md,
        backgroundColor: Colors.dangerLight,
        borderWidth: 1,
        borderColor: Colors.danger,
      }}>
      <AlertOctagon size={18} color={Colors.danger} style={{ marginTop: 1 }} />
      <Text
        style={{
          flex: 1,
          color: Colors.textPrimary,
          fontSize: 13,
          lineHeight: 19,
        }}>
        <Text style={{ fontFamily: Fonts.sansSemiBold }}>Medical emergency?</Text>{' '}
        Call 911 immediately. WondrChat is not built to handle emergencies.
      </Text>
    </View>
  );
}

function Section({
  title,
  tone,
  children,
}: {
  title: string;
  tone?: 'urgent';
  children: React.ReactNode;
}) {
  return (
    <View style={{ gap: 8 }}>
      <Text
        style={{
          color: tone === 'urgent' ? Colors.danger : Colors.textMuted,
          fontSize: 11,
          fontFamily: Fonts.sansMedium,
          letterSpacing: 0.5,
        }}>
        {title.toUpperCase()}
      </Text>
      <View
        style={{
          borderWidth: 1,
          borderColor: tone === 'urgent' ? Colors.danger : Colors.border,
          borderRadius: Radius.lg,
          backgroundColor: Colors.surface,
          overflow: 'hidden',
        }}>
        {children}
      </View>
    </View>
  );
}

function HelplineRow({
  h,
  urgent,
  showDivider,
}: {
  h: Helpline;
  urgent?: boolean;
  showDivider: boolean;
}) {
  return (
    <Pressable
      onPress={() => Linking.openURL(h.tel).catch(() => {})}
      accessibilityRole="button"
      accessibilityLabel={`Call ${h.name} at ${h.number}`}
      style={({ pressed }) => ({
        backgroundColor: pressed
          ? urgent
            ? Colors.dangerLight
            : Colors.sidebarBg
          : Colors.surface,
        borderBottomWidth: showDivider ? 1 : 0,
        borderBottomColor: urgent ? '#FCA5A5' : Colors.border,
      })}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          padding: 14,
        }}>
        <View
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            backgroundColor: urgent ? Colors.dangerLight : Colors.sidebarBg,
            alignItems: 'center',
            justifyContent: 'center',
            marginRight: 12,
          }}>
          <Phone size={18} color={urgent ? Colors.danger : Colors.primary} />
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text
            numberOfLines={1}
            ellipsizeMode="tail"
            style={{
              color: Colors.textPrimary,
              fontFamily: Fonts.sansSemiBold,
              fontSize: 15,
            }}>
            {h.name}
          </Text>
          <Text
            numberOfLines={1}
            ellipsizeMode="tail"
            style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>
            {h.number} · {h.desc}
          </Text>
        </View>
        <ChevronRight
          size={18}
          color={urgent ? Colors.danger : Colors.primary}
          style={{ marginLeft: 8 }}
        />
      </View>
    </Pressable>
  );
}
