import { useQueryClient } from '@tanstack/react-query';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import {
  AlertOctagon,
  ChevronRight,
  FileLock,
  FileText,
  Info,
  LogOut,
  MessageSquareWarning,
  ShieldCheck,
  Trash2,
  UserCog,
} from 'lucide-react-native';
import { Alert, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

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
          title: 'Consumer Health Data Privacy Notice',
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
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 18, paddingBottom: 40 }}>
        <View>
          <Text style={{ fontFamily: Fonts.serifBold, fontSize: 22, color: Colors.textPrimary }}>
            Settings
          </Text>
          {session?.user.email && (
            <Text style={{ color: Colors.textMuted, fontSize: 13, marginTop: 4 }}>
              Signed in as {session.user.email}
            </Text>
          )}
        </View>

        {sections.map((sec) => (
          <View key={sec.title} style={{ gap: 8 }}>
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
    </SafeAreaView>
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
        flexDirection: 'row',
        alignItems: 'center',
        gap: 12,
        padding: 14,
        backgroundColor: pressed ? Colors.sidebarBg : Colors.surface,
        borderBottomWidth: showDivider ? 1 : 0,
        borderBottomColor: Colors.border,
      })}>
      <row.Icon size={18} color={row.destructive ? Colors.danger : Colors.primary} />
      <View style={{ flex: 1 }}>
        <Text style={{ color: fg, fontFamily: Fonts.sansMedium, fontSize: 14 }}>{row.title}</Text>
        {row.blurb && (
          <Text style={{ color: Colors.textMuted, fontSize: 12, marginTop: 2 }}>{row.blurb}</Text>
        )}
      </View>
      {row.href && <ChevronRight size={16} color={Colors.textMuted} />}
    </Pressable>
  );
}
