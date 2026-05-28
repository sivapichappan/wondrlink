import Markdown from 'react-native-markdown-display';

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

export function MarkdownText({ children }: Props) {
  return <Markdown style={styles}>{children}</Markdown>;
}
