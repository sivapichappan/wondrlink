/**
 * All tools (design screen 5) — the full launcher backing the Home chips.
 *
 * Searchable 2-col grid. Deduped: Trends now lives under My Care's check-ins,
 * and Saved trials is a tab inside Clinical trials — neither appears here.
 */

import { router } from 'expo-router';
import {
  Activity,
  CalendarClock,
  ClipboardList,
  FileText,
  Microscope,
  NotebookPen,
  Search,
  Sparkles,
} from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { TopBar } from '@/components/common/TopBar';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { useWatchlist } from '@/hooks/useWatchlist';

interface Tool {
  href: string;
  title: string;
  blurb: string;
  Icon: typeof Activity;
}

const TOOLS: Tool[] = [
  { href: '/tools/clinical-trials', title: 'Clinical trials', blurb: 'Matched to your profile', Icon: Microscope },
  { href: '/tools/screening', title: 'Wellness check-in', blurb: 'Symptom, PHQ-9, GAD-7, PSS-10, ISI', Icon: Activity },
  { href: '/tools/previsit', title: 'Pre-visit questions', blurb: 'Tailored asks for your next visit', Icon: ClipboardList },
  { href: '/tools/visit-recap', title: 'Visit recap', blurb: 'Record an appointment, get a summary', Icon: NotebookPen },
  { href: '/tools/surveillance', title: 'Surveillance', blurb: 'Follow-up timeline after treatment', Icon: CalendarClock },
  { href: '/tools/deep-research', title: 'Deep research', blurb: 'Multi-pass research on one question', Icon: Search },
  { href: '/tools/insurance-appeal', title: 'Insurance appeal', blurb: 'Draft an appeal from a denial letter', Icon: FileText },
];

export default function AllToolsScreen() {
  const [query, setQuery] = useState('');
  const watchlist = useWatchlist();
  const savedCount = watchlist.trials.length;

  const q = query.trim().toLowerCase();
  const shown = q ? TOOLS.filter((t) => t.title.toLowerCase().includes(q) || t.blurb.toLowerCase().includes(q)) : TOOLS;

  return (
    <View style={{ flex: 1, backgroundColor: Colors.surface }}>
      <TopBar leading="back" backLabel="Home" onBack={() => router.replace('/')} title="All tools" />

      <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }} keyboardShouldPersistTaps="handled">
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 9, height: 42, paddingHorizontal: 14, borderRadius: Radius.pill, backgroundColor: Colors.surfaceMuted, borderWidth: 1, borderColor: Colors.border }}>
          <Search size={16} color={Colors.textMuted} />
          <TextInput value={query} onChangeText={setQuery} placeholder="Search tools" placeholderTextColor={Colors.textMuted} style={{ flex: 1, fontSize: 14, color: Colors.textPrimary, paddingVertical: 0 }} />
        </View>

        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          {shown.map((t) => (
            <Pressable key={t.href} onPress={() => router.push(t.href as never)} accessibilityRole="button" accessibilityLabel={t.title} style={{ width: '48%' }}>
              <View style={{ backgroundColor: Colors.surfaceMuted, borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.lg, padding: 13, gap: 8, minHeight: 104 }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: Colors.sidebarBg, alignItems: 'center', justifyContent: 'center' }}>
                    <t.Icon size={19} color={Colors.primary} />
                  </View>
                  {t.href === '/tools/clinical-trials' && savedCount > 0 && (
                    <View style={{ backgroundColor: Colors.primarySoft, borderRadius: Radius.pill, paddingHorizontal: 7, paddingVertical: 2 }}>
                      <Text style={{ fontSize: 9.5, fontFamily: Fonts.sansBold, color: Colors.primaryPressed }}>{savedCount} SAVED</Text>
                    </View>
                  )}
                </View>
                <View>
                  <Text style={{ fontSize: 14, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>{t.title}</Text>
                  <Text numberOfLines={2} style={{ fontSize: 11, lineHeight: 15, color: Colors.textSecondary, marginTop: 2 }}>{t.blurb}</Text>
                </View>
              </View>
            </Pressable>
          ))}

          {/* Ask-in-chat helper */}
          <Pressable onPress={() => router.push('/chat/new' as never)} accessibilityRole="button" accessibilityLabel="Ask in chat" style={{ width: '48%' }}>
            <View style={{ borderWidth: 1.5, borderColor: Colors.primarySoft, borderStyle: 'dashed', borderRadius: Radius.lg, padding: 13, gap: 6, minHeight: 104, justifyContent: 'center', backgroundColor: Colors.sidebarBg }}>
              <Sparkles size={18} color={Colors.primary} />
              <Text style={{ fontSize: 11.5, lineHeight: 16, color: Colors.textSecondary }}>
                Not sure which tool? <Text style={{ fontFamily: Fonts.sansSemiBold, color: Colors.primary }}>Just ask in chat</Text> — it routes you.
              </Text>
            </View>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}
