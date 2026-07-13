/**
 * HelpSheet — the SOS/Help bottom sheet (design screen 7).
 *
 * Mounted ONCE in the (app) layout, opened from any TopBar's SOS pill via
 * NavOverlay. Crisis access must never depend on where you are, so the content
 * is identical everywhere. All helpline strings come VERBATIM from
 * shared/disclaimers.ts — do not paraphrase.
 *
 * Precedent: components/common/CrisisModal.tsx (core-RN <Modal> bottom sheet).
 */

import {
  AlertOctagon,
  ChevronRight,
  Headset,
  MessageSquare,
  Phone,
  X,
} from 'lucide-react-native';
import { Linking, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Colors, FontSize, Fonts, Radius } from '@/constants/theme';
import { CANCER_HELPLINES, CONTACT, CRISIS_HELPLINES, type Helpline } from '@shared/disclaimers';
import { useNavOverlay } from './NavOverlay';

export function HelpSheet() {
  const { helpOpen, closeHelp } = useNavOverlay();
  const insets = useSafeAreaInsets();

  return (
    <Modal visible={helpOpen} transparent animationType="slide" onRequestClose={closeHelp}>
      <Pressable style={{ flex: 1, backgroundColor: Colors.scrim }} onPress={closeHelp} accessibilityLabel="Close help" />
      <View
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          maxHeight: '88%',
          backgroundColor: Colors.surface,
          borderTopLeftRadius: Radius.xl,
          borderTopRightRadius: Radius.xl,
          paddingHorizontal: 20,
          paddingTop: 10,
          paddingBottom: insets.bottom + 20,
        }}>
        <View style={{ width: 36, height: 5, borderRadius: 3, backgroundColor: Colors.border, alignSelf: 'center', marginBottom: 12 }} />

        <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
          <View style={{ flex: 1 }}>
            <Text style={{ fontFamily: Fonts.serifBold, fontSize: FontSize.h2, color: Colors.textPrimary }}>Get help</Text>
            <Text style={{ fontSize: FontSize.base, color: Colors.textMuted, marginTop: 3 }}>Tap any number to call directly.</Text>
          </View>
          <Pressable onPress={closeHelp} accessibilityRole="button" accessibilityLabel="Close" hitSlop={8}>
            <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: Colors.surfaceMuted, alignItems: 'center', justifyContent: 'center' }}>
              <X size={18} color={Colors.textMuted} />
            </View>
          </Pressable>
        </View>

        <ScrollView style={{ marginTop: 13 }} contentContainerStyle={{ gap: 14 }} showsVerticalScrollIndicator={false}>
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
            <Text style={{ flex: 1, color: Colors.textPrimary, fontSize: FontSize.base, lineHeight: 19 }}>
              <Text style={{ fontFamily: Fonts.sansSemiBold }}>Medical emergency?</Text> Call 911 immediately. WondrChat is
              not built to handle emergencies.
            </Text>
          </View>

          <Section title="Crisis support · 24/7" urgent>
            {CRISIS_HELPLINES.map((h, i, arr) => (
              <HelplineRow key={h.name} h={h} urgent showDivider={i < arr.length - 1} />
            ))}
          </Section>

          <Section title="Cancer support">
            {CANCER_HELPLINES.map((h, i, arr) => (
              <HelplineRow key={h.name} h={h} showDivider={i < arr.length - 1} />
            ))}
          </Section>

          {/* Personal Navigator — link to the website only (no phone constant exists). */}
          <View style={{ backgroundColor: Colors.sidebarBg, borderRadius: Radius.lg, padding: 13, gap: 10 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: Colors.primarySoft, alignItems: 'center', justifyContent: 'center' }}>
                <Headset size={18} color={Colors.primaryPressed} />
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={{ fontSize: FontSize.md, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
                  Talk to a Personal Navigator
                </Text>
                <Text style={{ fontSize: FontSize.sm, color: Colors.textSecondary, marginTop: 1 }}>A real person from WondrLink</Text>
              </View>
            </View>
            <Pressable onPress={() => Linking.openURL(CONTACT.website).catch(() => {})} accessibilityRole="link" accessibilityLabel="Open WondrLink website">
              <View style={{ height: 42, borderRadius: Radius.md, backgroundColor: Colors.primary, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 7 }}>
                <MessageSquare size={15} color={Colors.surface} />
                <Text style={{ color: Colors.surface, fontSize: FontSize.md, fontFamily: Fonts.sansSemiBold }}>Visit wondrlinkfoundation.org</Text>
              </View>
            </Pressable>
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
}

function Section({ title, urgent, children }: { title: string; urgent?: boolean; children: React.ReactNode }) {
  return (
    <View style={{ gap: 8 }}>
      <Text style={{ color: urgent ? Colors.danger : Colors.textMuted, fontSize: FontSize.xs, fontFamily: Fonts.sansMedium, letterSpacing: 0.5 }}>
        {title.toUpperCase()}
      </Text>
      <View style={{ borderWidth: 1, borderColor: urgent ? Colors.danger : Colors.border, borderRadius: Radius.lg, backgroundColor: Colors.surface, overflow: 'hidden' }}>
        {children}
      </View>
    </View>
  );
}

function HelplineRow({ h, urgent, showDivider }: { h: Helpline; urgent?: boolean; showDivider: boolean }) {
  return (
    <Pressable onPress={() => Linking.openURL(h.tel).catch(() => {})} accessibilityRole="button" accessibilityLabel={`Call ${h.name} at ${h.number}`}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          padding: 14,
          borderBottomWidth: showDivider ? 1 : 0,
          borderBottomColor: urgent ? '#FCA5A5' : Colors.border,
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
          <Text numberOfLines={1} style={{ color: Colors.textPrimary, fontFamily: Fonts.sansSemiBold, fontSize: FontSize.lg }}>
            {h.name}
          </Text>
          <Text numberOfLines={1} style={{ color: Colors.textMuted, fontSize: FontSize.sm, marginTop: 2 }}>
            {h.number} · {h.desc}
          </Text>
        </View>
        <ChevronRight size={18} color={urgent ? Colors.danger : Colors.primary} style={{ marginLeft: 8 }} />
      </View>
    </Pressable>
  );
}
