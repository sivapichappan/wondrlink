import Markdown, { MarkdownIt } from 'react-native-markdown-display';

import { Colors, Fonts, Radius, Spacing } from '@/constants/theme';

interface Props {
  children: string;
  /** `lead` is the direct-answer sentence at the top of a response. */
  variant?: 'body' | 'lead';
}

// TYPOGRAPHER OFF, DELIBERATELY.
//
// The library's default is `MarkdownIt({typographer: true})`, whose
// `replacements` rule rewrites "--" as an en dash and "---" as an em dash. That
// runs on the phone, AFTER enforce_voice() has scrubbed the answer server-side,
// so the guarantee that no patient ever sees an em dash had a hole in it on the
// only surface that matters. It is also a fresh parser per render as a default
// argument; hoisting it here keeps one.
//
// MarkdownIt comes from the display library's own re-export, not from a direct
// `markdown-it` import: that package is only present through npm hoisting here,
// and depending on a hoisted package is what broke EAS bundling once already
// (babel-preset-expo, build #31).
const markdownEngine = MarkdownIt({ typographer: false });

// Every node type the model can emit is styled. The unstyled ones fall through
// to the library's own defaults, which are hardcoded off-theme values: `hr` is
// pure black, tables draw black borders, code blocks are a #CCCCCC/#f5f5f5 box,
// and `heading4` is 16px — LARGER than the heading3 above it.
const base = {
  // Sage speaking — serif is the voice (semantic typography, redesign
  // 2026-08-24). Labels/headings stay sans: they are interface, not voice.
  body: { color: Colors.textPrimary, fontSize: 16, lineHeight: 25, fontFamily: Fonts.serif },
  paragraph: { marginTop: 0, marginBottom: 8 },
  strong: { fontFamily: Fonts.serifSemiBold, color: Colors.textPrimary },
  em: { fontStyle: 'italic' as const },
  s: { textDecorationLine: 'line-through' as const },

  bullet_list: { marginTop: 2, marginBottom: 8 },
  ordered_list: { marginTop: 2, marginBottom: 8 },
  list_item: { marginBottom: 5 },
  bullet_list_icon: { marginLeft: 2, marginRight: 8, color: Colors.textSecondary },
  ordered_list_icon: { marginLeft: 2, marginRight: 8, color: Colors.textSecondary },
  bullet_list_content: { flex: 1 },
  ordered_list_content: { flex: 1 },

  heading1: { fontFamily: Fonts.serifSemiBold, fontSize: 19, marginTop: 8, marginBottom: 4, color: Colors.textPrimary },
  heading2: { fontFamily: Fonts.sansSemiBold, fontSize: 16, marginTop: 8, marginBottom: 4, color: Colors.textPrimary },
  heading3: { fontFamily: Fonts.sansSemiBold, fontSize: 15, marginTop: 6, marginBottom: 2, color: Colors.textPrimary },
  heading4: { fontFamily: Fonts.sansSemiBold, fontSize: 14, marginTop: 6, marginBottom: 2, color: Colors.textPrimary },
  heading5: { fontFamily: Fonts.sansSemiBold, fontSize: 13, marginTop: 6, marginBottom: 2, color: Colors.textSecondary },
  heading6: { fontFamily: Fonts.sansSemiBold, fontSize: 13, marginTop: 6, marginBottom: 2, color: Colors.textSecondary },

  link: { color: Colors.primary, textDecorationLine: 'underline' as const },
  blocklink: { borderBottomWidth: 0 },
  code_inline: {
    fontFamily: 'Courier',
    backgroundColor: Colors.sidebarBg,
    color: Colors.textPrimary,
    paddingHorizontal: 4,
    borderRadius: Radius.sm,
  },
  code_block: {
    fontFamily: 'Courier',
    backgroundColor: Colors.surfaceMuted,
    borderColor: Colors.border,
    borderWidth: 1,
    borderRadius: Radius.sm,
    padding: Spacing.sm,
    color: Colors.textPrimary,
  },
  fence: {
    fontFamily: 'Courier',
    backgroundColor: Colors.surfaceMuted,
    borderColor: Colors.border,
    borderWidth: 1,
    borderRadius: Radius.sm,
    padding: Spacing.sm,
    color: Colors.textPrimary,
  },
  blockquote: {
    backgroundColor: Colors.sidebarBg,
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginVertical: 4,
  },
  hr: { backgroundColor: Colors.border, height: 1, marginVertical: Spacing.sm },
  table: { borderColor: Colors.border, borderWidth: 1, borderRadius: Radius.sm },
  thead: { backgroundColor: Colors.surfaceMuted },
  th: { borderColor: Colors.border, padding: Spacing.xs },
  tr: { borderColor: Colors.border },
  td: { borderColor: Colors.border, padding: Spacing.xs },
  hardbreak: { width: '100%' as const, height: 1 },
  image: { flex: 1 },
};

// The lead is the one sentence that answers the question. It reads a step
// larger so the eye lands on it before anything else on the card.
const leadStyles = {
  ...base,
  body: { ...base.body, fontSize: 17, lineHeight: 26 },
  paragraph: { marginTop: 0, marginBottom: 6 },
};

export function MarkdownText({ children, variant = 'body' }: Props) {
  return (
    <Markdown style={variant === 'lead' ? leadStyles : base} markdownit={markdownEngine}>
      {children}
    </Markdown>
  );
}
