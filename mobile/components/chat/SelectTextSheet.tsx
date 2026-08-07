/**
 * Select any part of a message.
 *
 * React Native cannot do this inline, and no amount of prop placement changes
 * that. On iOS `<Text selectable>` installs a UILongPressGestureRecognizer and
 * a UIEditMenuInteraction whose copy: uses NSMakeRange(0, length) — the whole
 * node, every time (RCTParagraphComponentView.mm). There is no UITextInteraction
 * and no selectedRange anywhere in that view, at any nesting level. Two earlier
 * attempts moved `selectable` between the markdown `text` and `textgroup` rules
 * on the theory that nesting was the variable; it never was, and both shipped
 * as "I can only copy the whole message".
 *
 * A read-only multiline TextInput is backed by a real UITextView
 * (RCTTextInputComponentView sets only `.editable`, leaving isSelectable true),
 * which gives drag selection, grab handles, and the system Copy / Share / Look
 * Up menu. So selection happens here, in a sheet, on de-marked text.
 */

import { X } from 'lucide-react-native';
import { Modal, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { IconCircle } from '@/components/ui/IconCircle';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { toPlainText } from '@/lib/answer-text';

import { MessageActions } from './MessageActions';

interface Props {
  /** The markdown to select from; null closes the sheet. */
  content: string | null;
  onClose: () => void;
  /** Feedback buttons are for Sage's answers, never for a crisis card. */
  showFeedback?: boolean;
}

// A very long answer measures its full height on the UI thread when the input
// does not scroll itself. Nothing in the corpus comes close, but a runaway
// generation should degrade to a truncated sheet rather than a frozen one.
const MAX_CHARS = 8000;

const sheetStyle = {
  position: 'absolute' as const,
  left: 0,
  right: 0,
  bottom: 0,
  maxHeight: '80%' as const,
  backgroundColor: Colors.surface,
  borderTopLeftRadius: Radius.xl,
  borderTopRightRadius: Radius.xl,
  paddingHorizontal: Spacing.md,
  paddingTop: Spacing.md,
  gap: Spacing.sm,
};

const inputStyle = {
  color: Colors.textPrimary,
  fontFamily: Fonts.sans,
  fontSize: FontSize.lg,
  lineHeight: 22,
  padding: 0,
};

export function SelectTextSheet({ content, onClose, showFeedback = false }: Props) {
  const insets = useSafeAreaInsets();
  const plain = content ? toPlainText(content).slice(0, MAX_CHARS) : '';

  return (
    <Modal visible={content !== null} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable
        style={{ flex: 1, backgroundColor: Colors.scrim }}
        onPress={onClose}
        accessibilityLabel="Close"
      />
      <View style={{ ...sheetStyle, paddingBottom: insets.bottom + Spacing.lg }}>
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <Text
            style={{
              flex: 1,
              fontFamily: Fonts.sansSemiBold,
              fontSize: FontSize.xs,
              letterSpacing: 0.6,
              color: Colors.textMuted,
            }}>
            SELECT TEXT
          </Text>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" hitSlop={8}>
            <IconCircle size={30} bg={Colors.primary}>
              <X size={17} color={Colors.surface} />
            </IconCircle>
          </Pressable>
        </View>

        <ScrollView contentContainerStyle={{ paddingBottom: Spacing.sm }}>
          {/* editable={false} is the whole trick: still a UITextView, so it
              selects, but it cannot be typed into and raises no keyboard. */}
          <TextInput
            multiline
            editable={false}
            scrollEnabled={false}
            value={plain}
            style={inputStyle}
            accessibilityLabel="Message text, selectable"
          />
        </ScrollView>

        {showFeedback && <MessageActions messageText={plain} />}

        <Text style={{ fontSize: FontSize.xs, color: Colors.textMuted, lineHeight: 16 }}>
          Press and hold to select part of this, or use Copy to take all of it.
        </Text>
      </View>
    </Modal>
  );
}
