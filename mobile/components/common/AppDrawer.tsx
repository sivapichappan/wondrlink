/**
 * AppDrawer — the left navigation drawer (design screen 3).
 *
 * Mounted ONCE in the (app) group layout, floating above the Stack. Open/close
 * is driven by NavOverlay context (menu button in TopBar). Slides both ways via
 * Reanimated; scrim tap or Android back closes it.
 *
 * NativeWind rule: Pressable rows carry no visual style in a style-function;
 * their surfaces are plain Views.
 *
 * NOTE (Phase 1b interim): New chat + Recents currently route to Home ('/').
 * Phase 2 wires them to create a conversation and open /chat/[id].
 */

import { router } from 'expo-router';
import { Activity, HeartPulse, LayoutGrid, LifeBuoy, Search, Settings, SquarePen, Tag, User } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { BackHandler, Image, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { Easing, runOnJS, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Colors, FontSize, Fonts, Radius } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useCareSnapshot, useProfile } from '@/hooks/useCare';
import { useConversations } from '@/hooks/useConversations';
import { useWatchlist } from '@/hooks/useWatchlist';
import { useNavOverlay } from './NavOverlay';

const DRAWER_W = 310;
const LOGO = require('../../assets/images/icon.png');

export function AppDrawer() {
  const { drawerOpen, closeDrawer, openHelp } = useNavOverlay();
  const insets = useSafeAreaInsets();
  const progress = useSharedValue(0);
  const [query, setQuery] = useState('');

  const conversations = useConversations();
  const watchlist = useWatchlist();
  const snap = useCareSnapshot();
  const profile = useProfile();
  const ack = useAcknowledgement();

  const cancerDisplay = ack.data?.cancer_display ?? 'Pick cancer';
  const savedCount = watchlist.trials.length;
  const daysSince = snap.data?.days_since_symptom;
  const checkinDue = daysSince == null || daysSince >= 7;

  const patient = profile.data?.profile?.patient as { name?: string; firstName?: string } | undefined;
  const displayName = patient?.firstName || patient?.name || 'Your account';
  const initials = (displayName || 'You')
    .split(/\s+/)
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  useEffect(() => {
    progress.value = withTiming(drawerOpen ? 1 : 0, { duration: 240, easing: Easing.out(Easing.cubic) });
  }, [drawerOpen, progress]);

  // Android hardware back closes the drawer before popping the stack.
  useEffect(() => {
    if (!drawerOpen) return;
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      closeDrawer();
      return true;
    });
    return () => sub.remove();
  }, [drawerOpen, closeDrawer]);

  const scrimStyle = useAnimatedStyle(() => ({ opacity: progress.value }));
  const panelStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: -DRAWER_W + progress.value * DRAWER_W }],
  }));

  // Drag the open drawer left to close it (follows the finger; snaps on release).
  const dragClose = Gesture.Pan()
    .activeOffsetX([-12, 12])
    .onUpdate((e) => {
      progress.value = Math.min(1, Math.max(0, 1 + e.translationX / DRAWER_W));
    })
    .onEnd((e) => {
      if (progress.value < 0.6 || e.velocityX < -400) {
        progress.value = withTiming(0, { duration: 200, easing: Easing.out(Easing.cubic) });
        runOnJS(closeDrawer)();
      } else {
        progress.value = withTiming(1, { duration: 200, easing: Easing.out(Easing.cubic) });
      }
    });

  const go = (path: string) => {
    // Navigate FIRST (while the drawer still covers the screen), then close — so
    // you don't see a flash of Home between closing the drawer and the push.
    router.push(path as never);
    closeDrawer();
  };

  return (
    <View
      pointerEvents={drawerOpen ? 'auto' : 'none'}
      style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
      <Animated.View style={[{ flex: 1, backgroundColor: Colors.scrim }, scrimStyle]}>
        <Pressable style={{ flex: 1 }} onPress={closeDrawer} accessibilityLabel="Close menu" />
      </Animated.View>

      <GestureDetector gesture={dragClose}>
      <Animated.View
        style={[
          {
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: 0,
            width: DRAWER_W,
            backgroundColor: Colors.sidebarBg,
            paddingTop: insets.top + 8,
            shadowColor: '#0F201C',
            shadowOpacity: 0.22,
            shadowRadius: 34,
            shadowOffset: { width: 10, height: 0 },
            elevation: 16,
          },
          panelStyle,
        ]}>
        <ScrollView
          contentContainerStyle={{ paddingHorizontal: 12, paddingBottom: insets.bottom + 16 }}
          showsVerticalScrollIndicator={false}>
          {/* Brand */}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 9, paddingHorizontal: 8, paddingVertical: 10 }}>
            <Image source={LOGO} style={{ width: 24, height: 24, borderRadius: 6 }} />
            <Text style={{ fontFamily: Fonts.serifBold, fontSize: FontSize.h3, color: Colors.textPrimary }}>WondrChat</Text>
          </View>

          <DrawerRow icon={<SquarePen size={17} color={Colors.primary} />} label="New chat" tint onPress={() => go('/chat/new')} />

          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              gap: 9,
              height: 38,
              paddingHorizontal: 12,
              borderRadius: Radius.pill,
              backgroundColor: Colors.surface,
              borderWidth: 1,
              borderColor: Colors.border,
              marginVertical: 4,
            }}>
            <Search size={15} color={Colors.textMuted} />
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Search chats"
              placeholderTextColor={Colors.textMuted}
              style={{ flex: 1, fontSize: 13, color: Colors.textPrimary, paddingVertical: 0 }}
            />
          </View>

          {/* Recents */}
          <SectionLabel>RECENTS</SectionLabel>
          {(() => {
            const q = query.trim().toLowerCase();
            const list = q
              ? conversations.conversations.filter((c) => c.title.toLowerCase().includes(q))
              : conversations.conversations;
            if (list.length === 0) {
              return (
                <Text style={{ fontSize: 12, color: Colors.textMuted, paddingHorizontal: 10, paddingVertical: 6 }}>
                  {conversations.isLoading ? 'Loading…' : q ? 'No matches.' : 'No conversations yet.'}
                </Text>
              );
            }
            return list.slice(0, 5).map((c) => (
              <Pressable key={c.id} onPress={() => go(`/chat/${c.id}`)} accessibilityRole="button" accessibilityLabel={c.title}>
                <View style={{ height: 36, justifyContent: 'center', paddingHorizontal: 10, borderRadius: 10 }}>
                  <Text numberOfLines={1} style={{ fontSize: FontSize.base, color: Colors.textPrimary }}>
                    {c.title}
                  </Text>
                </View>
              </Pressable>
            ));
          })()}

          {/* My Care */}
          <SectionLabel>MY CARE</SectionLabel>
          <DrawerRow
            icon={<Tag size={17} color={Colors.textSecondary} />}
            label="Cancer focus"
            hint={cancerDisplay}
            onPress={() => go('/profile/cancer-switcher')}
          />
          <DrawerRow icon={<User size={17} color={Colors.textSecondary} />} label="Profile" onPress={() => go('/profile')} />
          <DrawerRow icon={<HeartPulse size={17} color={Colors.textSecondary} />} label="Care snapshot" onPress={() => go('/care')} />
          <DrawerRow
            icon={<Activity size={17} color={Colors.textSecondary} />}
            label="Check-ins & trends"
            badge={checkinDue ? 'DUE' : undefined}
            onPress={() => go('/tools/trends')}
          />

          {/* Tools — one entry into the full launcher (deduped) */}
          <SectionLabel>TOOLS</SectionLabel>
          <DrawerRow
            icon={<LayoutGrid size={17} color={Colors.textSecondary} />}
            label="All tools"
            hint={savedCount > 0 ? `${savedCount} saved` : undefined}
            onPress={() => go('/tools')}
          />

          <DrawerRow
            icon={<LifeBuoy size={17} color={Colors.warning} />}
            label="Help & helplines"
            labelColor={Colors.warning}
            onPress={() => {
              openHelp();
              closeDrawer();
            }}
          />

          {/* Account card */}
          <Pressable onPress={() => go('/settings')} accessibilityRole="button" accessibilityLabel="Profile and settings">
            <View
              style={{
                marginTop: 14,
                flexDirection: 'row',
                alignItems: 'center',
                gap: 10,
                backgroundColor: Colors.surface,
                borderWidth: 1,
                borderColor: Colors.border,
                borderRadius: Radius.lg,
                padding: 10,
              }}>
              <View
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 17,
                  backgroundColor: Colors.primarySoft,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                <Text style={{ color: Colors.primaryPressed, fontSize: 12, fontFamily: Fonts.sansBold }}>{initials}</Text>
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text numberOfLines={1} style={{ fontSize: FontSize.base, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
                  {displayName}
                </Text>
                <Text style={{ fontSize: 11, color: Colors.textMuted }}>Profile & settings</Text>
              </View>
              <Settings size={16} color={Colors.textMuted} />
            </View>
          </Pressable>
        </ScrollView>
      </Animated.View>
      </GestureDetector>
    </View>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <Text
      style={{
        fontSize: FontSize.xs,
        fontFamily: Fonts.sansSemiBold,
        letterSpacing: 0.6,
        color: Colors.textMuted,
        paddingHorizontal: 10,
        paddingTop: 12,
        paddingBottom: 5,
      }}>
      {children}
    </Text>
  );
}

function DrawerRow({
  icon,
  label,
  onPress,
  tint,
  badge,
  hint,
  labelColor,
}: {
  icon: React.ReactNode;
  label: string;
  onPress: () => void;
  tint?: boolean;
  badge?: string;
  hint?: string;
  labelColor?: string;
}) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, height: 40, paddingHorizontal: 10, borderRadius: 10 }}>
        {icon}
        <Text
          style={{
            flex: 1,
            fontSize: FontSize.base,
            color: labelColor ?? (tint ? Colors.primary : Colors.textPrimary),
            fontFamily: tint ? Fonts.sansSemiBold : Fonts.sans,
          }}>
          {label}
        </Text>
        {hint ? <Text style={{ fontSize: 11, color: Colors.textMuted }}>{hint}</Text> : null}
        {badge ? (
          <View style={{ backgroundColor: Colors.sosBg, borderRadius: Radius.pill, paddingHorizontal: 7, paddingVertical: 2 }}>
            <Text style={{ fontSize: FontSize.xs, fontFamily: Fonts.sansBold, color: Colors.warning }}>{badge}</Text>
          </View>
        ) : null}
      </View>
    </Pressable>
  );
}
