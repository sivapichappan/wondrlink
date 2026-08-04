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
// BOTH rules need it: `textgroup` wraps a paragraph's inline runs and `text` is
// each run. Marking only the outer one leaves bold and linked spans
// unselectable, which reads as a selection that keeps breaking apart.
const selectableRules = {
  text: (node: any, _children: any, _parent: any, s: any, inherited: any = {}) => (
    <Text key={node.key} selectable style={[inherited, s.text]}>
      {node.content}
    </Text>
  ),
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
