import { ChevronDown, ChevronUp, FileText } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';
import type { ChatSource } from '@shared/types';

interface Props {
  sources?: ChatSource[];
}

export function SourceCitations({ sources }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  if (!sources || sources.length === 0) return null;

  return (
    <View>
      <Pressable
        onPress={() => setExpanded((v) => !v)}
        accessibilityRole="button"
        style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 6 }}>
        <FileText size={14} color={Colors.textMuted} />
        <Text
          style={{
            color: Colors.textSecondary,
            fontFamily: Fonts.sansMedium,
            fontSize: 12,
            letterSpacing: 0.4,
          }}>
          {sources.length} {sources.length === 1 ? 'source' : 'sources'}
        </Text>
        {expanded ? (
          <ChevronUp size={14} color={Colors.textMuted} />
        ) : (
          <ChevronDown size={14} color={Colors.textMuted} />
        )}
      </Pressable>

      {expanded && (
        <View style={{ gap: 6, paddingTop: 4 }}>
          {sources.map((s, i) => {
            const isOpen = openIdx === i;
            return (
              <Pressable
                key={`${s.title}-${i}`}
                onPress={() => setOpenIdx(isOpen ? null : i)}
                style={{
                  borderWidth: 1,
                  borderColor: Colors.border,
                  borderLeftWidth: 3,
                  borderLeftColor: Colors.primary,
                  borderRadius: 8,
                  paddingHorizontal: 12,
                  paddingVertical: 10,
                  backgroundColor: Colors.surface,
                }}>
                <Text style={{ color: Colors.textPrimary, fontSize: 13, fontFamily: Fonts.sansMedium }}>
                  {s.display_name || s.title}
                  {s.is_featured ? ' ★' : ''}
                </Text>
                {isOpen && s.preview ? (
                  <Text
                    style={{
                      color: Colors.textSecondary,
                      fontSize: 12,
                      lineHeight: 18,
                      marginTop: 6,
                      fontStyle: 'italic',
                    }}>
                    {s.preview}
                  </Text>
                ) : null}
              </Pressable>
            );
          })}
        </View>
      )}
    </View>
  );
}
