import { useQueryClient } from '@tanstack/react-query';
import Constants from 'expo-constants';
import { Stack, router } from 'expo-router';
import {
  AlertOctagon,
  ChevronRight,
  FileLock,
  FileText,
  Info,
  Lock,
  LogOut,
  MessageSquareWarning,
  ShieldCheck,
  ShieldOff,
  SlidersHorizontal,
  Tag,
  Trash2,
  UserCog,
} from 'lucide-react-native';
import { Alert, Pressable, ScrollView, Text, View } from 'react-native';

import { HeaderBack } from '@/components/common/HeaderBack';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useAuth } from '@/hooks/useAuth';
import { logout } from '@/lib/api/auth';

interface Row {
  href?: string;
  onPress?: () => void;
  Icon: typeof FileLock;
  title: string;
  blurb?: string;
  destructive?: boolean;
}

export default function SettingsScreen() {
  const { session } = useAuth();
  const qc = useQueryClient();

  const signOut = () => {
    Alert.alert('Sign out?', 'You can sign back in any time.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign out',
        style: 'destructive',
        onPress: async () => {
          await logout();
          qc.clear();
        },
      },
    ]);
  };

  const sections: { title: string; rows: Row[] }[] = [
    {
      title: 'Account',
      rows: [
        {
          href: '/profile',
          Icon: UserCog,
          title: 'Profile',
          blurb: 'View and reset the personalization data WondrChat uses',
        },
        {
          href: '/profile/cancer-switcher',
          Icon: Tag,
          title: 'Cancer focus',
          blurb: 'Switch which cancer WondrChat is tailored to',
        },
        {
          href: '/settings/detail-level',
          Icon: SlidersHorizontal,
          title: 'Detail level',
          blurb: 'Brief, normal, or detailed answers',
        },
        { onPress: signOut, Icon: LogOut, title: 'Sign out' },
      ],
    },
    {
      title: 'Privacy & compliance',
      rows: [
        {
          href: '/settings/privacy',
          Icon: ShieldCheck,
          title: 'Privacy Policy',
          blurb: 'How WondrLink handles your data',
        },
        {
          href: '/settings/terms',
          Icon: FileText,
          title: 'Terms of Use',
        },
        {
          href: '/settings/health-notice',
          Icon: FileLock,
          title: 'Consumer Health Notice',
          blurb: 'MHMDA-compliant disclosure',
        },
        {
          href: '/settings/consent-management',
          Icon: ShieldOff,
          title: 'Consent Management',
          blurb: 'Withdraw any signup consent without deleting your account',
        },
        {
          href: '/settings/limit-spi',
          Icon: Lock,
          title: 'Do Not Sell · Limit Sensitive PI',
          blurb: 'CCPA / CPRA opt-out preferences',
        },
        {
          href: '/settings/privacy-appeal',
          Icon: AlertOctagon,
          title: 'Submit a privacy appeal',
          blurb: '45-day SLA per MHMDA',
        },
      ],
    },
    {
      title: 'Help WondrChat improve',
      rows: [
        {
          href: '/settings/feedback',
          Icon: MessageSquareWarning,
          title: 'Send feedback',
        },
      ],
    },
    {
      title: 'Danger zone',
      rows: [
        {
          href: '/settings/delete-account',
          Icon: Trash2,
          title: 'Delete account',
          blurb: 'Permanently remove your account and data',
          destructive: true,
        },
      ],
    },
    {
      title: 'About',
      rows: [
        {
          href: '/settings/about',
          Icon: Info,
          title: 'About WondrChat',
          blurb: `Version ${Constants.expoConfig?.version ?? '—'}`,
        },
      ],
    },
  ];

  return (
    <View style={{ flex: 1, backgroundColor: Colors.surface }}>
      <Stack.Screen options={{ title: 'Settings', headerLeft: () => <HeaderBack label="Home" /> }} />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 14, paddingBottom: 40 }}>
        {session?.user.email && (
          <Text
            numberOfLines={1}
            ellipsizeMode="middle"
            style={{ color: Colors.textMuted, fontSize: 13 }}>
            {session.user.email}
          </Text>
        )}

        {sections.map((sec) => (
          <View
            key={sec.title}
            style={{ gap: 8, marginTop: sec.title === 'Danger zone' ? 8 : 0 }}>
            <Text
              style={{
                color: Colors.textMuted,
                fontSize: 11,
                fontFamily: Fonts.sansMedium,
                letterSpacing: 0.5,
              }}>
              {sec.title.toUpperCase()}
            </Text>
            <View
              style={{
                borderWidth: 1,
                borderColor: Colors.border,
                borderRadius: Radius.lg,
                backgroundColor: Colors.surface,
                overflow: 'hidden',
              }}>
              {sec.rows.map((r, i) => (
                <SettingsRow
                  key={`${sec.title}-${i}`}
                  row={r}
                  showDivider={i < sec.rows.length - 1}
                />
              ))}
            </View>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

function SettingsRow({ row, showDivider }: { row: Row; showDivider: boolean }) {
  const fg = row.destructive ? Colors.danger : Colors.textPrimary;
  const onPress = row.onPress ?? (row.href ? () => router.push(row.href as never) : undefined);
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole="button"
      style={({ pressed }) => ({
        backgroundColor: pressed ? Colors.sidebarBg : Colors.surface,
        borderBottomWidth: showDivider ? 1 : 0,
        borderBottomColor: Colors.border,
      })}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          paddingVertical: 12,
          paddingHorizontal: 14,
        }}>
        <row.Icon
          size={20}
          color={row.destructive ? Colors.danger : Colors.primary}
          style={{ marginRight: 12 }}
        />
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text
            numberOfLines={1}
            ellipsizeMode="tail"
            style={{ color: fg, fontFamily: Fonts.sansMedium, fontSize: 15 }}>
            {row.title}
          </Text>
          {row.blurb && (
            <Text
              numberOfLines={2}
              ellipsizeMode="tail"
              style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2, lineHeight: 16 }}>
              {row.blurb}
            </Text>
          )}
        </View>
        {row.href && (
          <ChevronRight size={18} color={Colors.textMuted} style={{ marginLeft: 8 }} />
        )}
      </View>
    </Pressable>
  );
}
