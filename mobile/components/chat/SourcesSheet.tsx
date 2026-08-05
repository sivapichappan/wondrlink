/**
 * Every source used in this conversation, in one place.
 *
 * Sources used to hang off each individual answer, behind "Show details". Two
 * problems with that. It put a research artifact in the middle of a
 * conversation someone is having about their own cancer, on every single
 * message. And it answered the wrong question: nobody wonders "what backed
 * sentence four" — they wonder "what is this thing built on", which is a
 * question about the whole thread.
 *
 * So it moves to the composer's "+" menu, where it sits with the other things
 * you go looking for rather than things that interrupt you. Grouped by the
 * question each source answered, so the link back to a specific message is
 * kept rather than lost.
 */

import { FileText, X } from 'lucide-react-native';
import { Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { IconCircle } from '@/components/ui/IconCircle';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import type { ChatHistoryMessage, ChatSource } from '@shared/types';

interface Props {
  open: boolean;
  onClose: () => void;
  messages: ChatHistoryMessage[];
}

interface Group {
  question: string;
  sources: ChatSource[];
}

/** Pair each answer's sources with the question that produced them. */
function groupByQuestion(messages: ChatHistoryMessage[]): Group[] {
  const groups: Group[] = [];
  messages.forEach((m, i) => {
    if (m.role !== 'assistant') return;
    const sources = m.metadata?.sources ?? [];
    if (!sources.length) return;
    // The question is the user turn immediately before this answer.
    const prior = messages[i - 1];
    groups.push({
      question: prior?.role === 'user' ? prior.content : 'Earlier in this chat',
      sources,
    });
  });
  return groups;
}

export function SourcesSheet({ open, onClose, messages }: Props) {
  const insets = useSafeAreaInsets();
  const groups = groupByQuestion(messages);
  const total = groups.reduce((n, g) => n + g.sources.length, 0);

  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable
        style={{ flex: 1, backgroundColor: Colors.scrim }}
        onPress={onClose}
        accessibilityLabel="Close sources"
      />
      <View
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          maxHeight: '80%',
          backgroundColor: Colors.surface,
          borderTopLeftRadius: Radius.xl,
          borderTopRightRadius: Radius.xl,
          paddingHorizontal: Spacing.md,
          paddingTop: Spacing.md,
          paddingBottom: insets.bottom + Spacing.lg,
          gap: Spacing.sm,
        }}>
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <Text
            style={{
              flex: 1,
              fontFamily: Fonts.sansSemiBold,
              fontSize: FontSize.xs,
              letterSpacing: 0.6,
              color: Colors.textMuted,
            }}>
            {total > 0 ? `SOURCES USED IN THIS CHAT` : 'SOURCES'}
          </Text>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" hitSlop={8}>
            <IconCircle size={30} bg={Colors.primary}>
              <X size={17} color={Colors.surface} />
            </IconCircle>
          </Pressable>
        </View>

        {groups.length === 0 ? (
          <Text
            style={{
              fontSize: FontSize.sm,
              lineHeight: 20,
              color: Colors.textMuted,
              paddingVertical: Spacing.lg,
            }}>
            Nothing yet. When Sage answers using a medical guideline, the document shows up here.
          </Text>
        ) : (
          <ScrollView contentContainerStyle={{ gap: Spacing.lg, paddingBottom: Spacing.md }}>
            {groups.map((g, gi) => (
              <View key={gi} style={{ gap: Spacing.xs }}>
                <Text
                  numberOfLines={2}
                  style={{
                    fontSize: FontSize.sm,
                    fontFamily: Fonts.sansSemiBold,
                    color: Colors.textPrimary,
                  }}>
                  {g.question}
                </Text>
                {g.sources.map((s, si) => (
                  <View
                    key={`${gi}-${si}`}
                    style={{
                      flexDirection: 'row',
                      alignItems: 'flex-start',
                      gap: Spacing.sm,
                      backgroundColor: Colors.surfaceMuted,
                      borderRadius: Radius.md,
                      borderLeftWidth: 3,
                      borderLeftColor: Colors.primary,
                      paddingHorizontal: Spacing.md,
                      paddingVertical: Spacing.sm,
                    }}>
                    <FileText size={13} color={Colors.textMuted} style={{ marginTop: 2 }} />
                    <View style={{ flex: 1, gap: 2 }}>
                      <Text
                        style={{
                          fontSize: FontSize.sm,
                          fontFamily: Fonts.sansMedium,
                          color: Colors.textPrimary,
                        }}>
                        {s.display_name || s.title}
                      </Text>
                      {!!s.preview && (
                        <Text
                          numberOfLines={3}
                          style={{ fontSize: FontSize.xs, lineHeight: 16, color: Colors.textMuted }}>
                          {s.preview}
                        </Text>
                      )}
                    </View>
                  </View>
                ))}
              </View>
            ))}
          </ScrollView>
        )}

        <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted, lineHeight: 16 }}>
          These are the medical guidelines Sage read to answer. Informational only, and worth
          checking with your care team.
        </Text>
      </View>
    </Modal>
  );
}
