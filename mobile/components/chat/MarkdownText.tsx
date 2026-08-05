import Markdown from 'react-native-markdown-display';
import { Text } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';

interface Props {
  children: string;
}

const styles = {
  body: { color: Colors.textPrimary, fontSize: 15, lineHeight: 20, fontFamily: Fonts.sans },
  paragraph: { marginTop: 0, marginBottom: 6 },
  strong: { fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary },
  em: { fontStyle: 'italic' as const },
  bullet_list: { marginTop: 2, marginBottom: 6 },
  ordered_list: { marginTop: 2, marginBottom: 6 },
  list_item: { marginBottom: 2 },
  heading1: { fontFamily: Fonts.serifBold, fontSize: 19, marginTop: 8, marginBottom: 4, color: Colors.textPrimary },
  heading2: { fontFamily: Fonts.sansSemiBold, fontSize: 16, marginTop: 8, marginBottom: 4, color: Colors.textPrimary },
  heading3: { fontFamily: Fonts.sansSemiBold, fontSize: 15, marginTop: 6, marginBottom: 2, color: Colors.textPrimary },
  link: { color: Colors.primary, textDecorationLine: 'underline' as const },
  code_inline: { fontFamily: 'Courier', backgroundColor: Colors.sidebarBg, paddingHorizontal: 4, borderRadius: 4 },
  blockquote: {
    backgroundColor: Colors.sidebarBg,
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginVertical: 4,
  },
};

// react-native-markdown-display 7.0.2 has NO `selectable` prop, and its default
// rules render plain <Text>, which on iOS cannot be long-pressed or copied. So
// an answer someone wanted to paste into an email, or read out to their
// oncologist, was trapped in the app.
//
// ONLY THE OUTER NODE IS MARKED. A first attempt set `selectable` on both
// `textgroup` (the paragraph) and `text` (each inline run) on the reasoning
// that bold and linked spans would otherwise be skipped. That is backwards:
// on iOS a nested <Text> is a RUN inside its parent's text view, not a view of
// its own, so marking each run makes every run its own selection unit and the
// long press selects a whole node instead of letting you drag a highlight
// across the sentence. Which is exactly what was reported: "I can only copy
// the whole message."
//
// One selectable ancestor per block, plain children inside it, is the pattern
// that gives word-level highlighting.
const selectableRules = {
  textgroup: (node: any, children: any, _parent: any, s: any) => (
    <Text key={node.key} selectable style={s.textgroup}>
      {children}
    </Text>
  ),
};

export function MarkdownText({ children }: Props) {
  return (
    <Markdown style={styles} rules={selectableRules}>
      {children}
    </Markdown>
  );
}
