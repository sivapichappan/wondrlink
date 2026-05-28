import { router } from 'expo-router';
import {
  Activity,
  Bookmark,
  CalendarClock,
  ChevronRight,
  ClipboardList,
  FileText,
  LineChart,
  Microscope,
  NotebookPen,
  Search,
} from 'lucide-react-native';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Colors, Fonts, Radius } from '@/constants/theme';

interface Tool {
  href: string;
  title: string;
  blurb: string;
  Icon: typeof Activity;
}

const TOOLS: Tool[] = [
  {
    href: '/tools/screening',
    title: 'Wellness check-in',
    blurb: 'Symptom, PHQ-9, GAD-7, PSS-10, ISI, PREMM5 — saved to your Care snapshot.',
    Icon: Activity,
  },
  {
    href: '/tools/trends',
    title: 'View trends',
    blurb: 'See how your check-ins are tracking over time.',
    Icon: LineChart,
  },
  {
    href: '/tools/clinical-trials',
    title: 'Clinical trials',
    blurb: 'Find trials matching your stage, biomarkers, and ZIP code.',
    Icon: Microscope,
  },
  {
    href: '/tools/watchlist',
    title: 'Saved trials',
    blurb: 'Trials you bookmarked from chat.',
    Icon: Bookmark,
  },
  {
    href: '/tools/previsit',
    title: 'Pre-visit questions',
    blurb: 'Generate tailored questions for your next oncology visit.',
    Icon: ClipboardList,
  },
  {
    href: '/tools/visit-recap',
    title: 'Visit recap',
    blurb: 'Turn freeform visit notes into a structured recap.',
    Icon: NotebookPen,
  },
  {
    href: '/tools/surveillance',
    title: 'Surveillance schedule',
    blurb: 'Personalized follow-up timeline post-treatment.',
    Icon: CalendarClock,
  },
  {
    href: '/tools/deep-research',
    title: 'Deep research',
    blurb: 'Longer-form, multi-pass research on a specific question.',
    Icon: Search,
  },
  {
    href: '/tools/insurance-appeal',
    title: 'Insurance appeal',
    blurb: 'Draft an appeal letter from a denial reason or PDF.',
    Icon: FileText,
  },
];

export default function ToolsScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.surface }} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 10 }}>
        <Text
          style={{
            fontFamily: Fonts.serifBold,
            fontSize: 22,
            color: Colors.textPrimary,
            marginBottom: 6,
          }}>
          Care tools
        </Text>

        {TOOLS.map((t) => (
          <Pressable
            key={t.href}
            onPress={() => router.push(t.href as never)}
            accessibilityRole="button"
            accessibilityLabel={t.title}
            style={({ pressed }) => ({
              borderRadius: Radius.lg,
              backgroundColor: pressed ? Colors.sidebarBg : Colors.surface,
              borderWidth: 1,
              borderColor: Colors.border,
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
                <t.Icon size={20} color={Colors.primary} />
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
                  {t.title}
                </Text>
                <Text
                  numberOfLines={2}
                  ellipsizeMode="tail"
                  style={{
                    color: Colors.textSecondary,
                    fontSize: 12,
                    lineHeight: 18,
                    marginTop: 2,
                  }}>
                  {t.blurb}
                </Text>
              </View>
              <ChevronRight size={18} color={Colors.primary} style={{ marginLeft: 8 }} />
            </View>
          </Pressable>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
