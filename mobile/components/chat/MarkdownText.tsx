import Markdown from 'react-native-markdown-display';

import { Colors, Fonts } from '@/constants/theme';

interface Props {
  children: string;
}

const styles = {
  body: { color: Colors.textPrimary, fontSize: 15, lineHeight: 22, fontFamily: Fonts.sans },
  paragraph: { marginTop: 0, marginBottom: 8 },
  strong: { fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary },
  em: { fontStyle: 'italic' as const },
  bullet_list: { marginTop: 4, marginBottom: 8 },
  ordered_list: { marginTop: 4, marginBottom: 8 },
  list_item: { marginBottom: 4 },
  heading1: { fontFamily: Fonts.serifBold, fontSize: 20, marginTop: 12, marginBottom: 6, color: Colors.textPrimary },
  heading2: { fontFamily: Fonts.sansSemiBold, fontSize: 17, marginTop: 12, marginBottom: 6, color: Colors.textPrimary },
  heading3: { fontFamily: Fonts.sansSemiBold, fontSize: 15, marginTop: 10, marginBottom: 4, color: Colors.textPrimary },
  link: { color: Colors.primary, textDecorationLine: 'underline' as const },
  code_inline: { fontFamily: 'Courier', backgroundColor: Colors.sidebarBg, paddingHorizontal: 4, borderRadius: 4 },
  blockquote: {
    backgroundColor: Colors.sidebarBg,
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginVertical: 6,
  },
};

export function MarkdownText({ children }: Props) {
  return <Markdown style={styles}>{children}</Markdown>;
}
