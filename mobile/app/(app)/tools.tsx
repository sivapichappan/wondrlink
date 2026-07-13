/**
 * All tools (design screen 5) — the full launcher, calmer pass.
 *
 * Icon + title tiles (no per-card blurb, no search field for just 7 items).
 * Deduped: Trends lives under My Care; Saved trials is a tab inside Clinical
 * trials — neither appears here.
 */

import { router } from 'expo-router';
import { Activity, CalendarClock, ClipboardList, FileText, Microscope, NotebookPen, Search, Sparkles } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';

import { TopBar } from '@/components/common/TopBar';
import { IconCircle } from '@/components/ui/IconCircle';
import { Pill } from '@/components/ui/Pill';
import { Screen } from '@/components/ui/Screen';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { useWatchlist } from '@/hooks/useWatchlist';

interface Tool {
  href: string;
  title: string;
  Icon: typeof Activity;
}

const TOOLS: Tool[] = [
  { href: '/tools/clinical-trials', title: 'Clinical trials', Icon: Microscope },
  { href: '/tools/screening', title: 'Wellness check-in', Icon: Activity },
  { href: '/tools/previsit', title: 'Pre-visit questions', Icon: ClipboardList },
  { href: '/tools/visit-recap', title: 'Visit recap', Icon: NotebookPen },
  { href: '/tools/surveillance', title: 'Surveillance', Icon: CalendarClock },
  { href: '/tools/deep-research', title: 'Deep research', Icon: Search },
  { href: '/tools/insurance-appeal', title: 'Insurance appeal', Icon: FileText },
];

export default function AllToolsScreen() {
  const savedCount = useWatchlist().trials.length;

  return (
    <Screen header={<TopBar leading="back" backLabel="Home" title="All tools" />}>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.md }}>
        {TOOLS.map((t) => (
          <Pressable key={t.href} onPress={() => router.push(t.href as never)} accessibilityRole="button" accessibilityLabel={t.title} style={{ width: '48%' }}>
            <View style={{ backgroundColor: Colors.surfaceMuted, borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.lg, padding: Spacing.md, gap: Spacing.sm, minHeight: 96 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <IconCircle size={38}>
                  <t.Icon size={19} color={Colors.primary} />
                </IconCircle>
                {t.href === '/tools/clinical-trials' && savedCount > 0 && <Pill tone="brand">{savedCount} SAVED</Pill>}
              </View>
              <Text style={{ fontSize: FontSize.md, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>{t.title}</Text>
            </View>
          </Pressable>
        ))}

        {/* Ask-in-chat helper */}
        <Pressable onPress={() => router.push('/chat/new' as never)} accessibilityRole="button" accessibilityLabel="Ask in chat" style={{ width: '48%' }}>
          <View style={{ borderWidth: 1.5, borderColor: Colors.primarySoft, borderStyle: 'dashed', borderRadius: Radius.lg, padding: Spacing.md, gap: 6, minHeight: 96, justifyContent: 'center', backgroundColor: Colors.sidebarBg }}>
            <Sparkles size={18} color={Colors.primary} />
            <Text style={{ fontSize: FontSize.sm, lineHeight: 18, color: Colors.textSecondary }}>
              Not sure which tool? <Text style={{ fontFamily: Fonts.sansSemiBold, color: Colors.primary }}>Just ask in chat.</Text>
            </Text>
          </View>
        </Pressable>
      </View>
    </Screen>
  );
}
