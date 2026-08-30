/**
 * Per-session AI reminder. Required by CA chatbot law + Utah HB 452 +
 * Tennessee chatbot disclosure law. Parity with the web SESSION_META_HTML
 * shipped in commit 41b11b1.
 *
 * ── ON DISMISSING A LEGALLY REQUIRED DISCLOSURE ────────────────────────
 *
 * It is dismissible, and that needed care, because at the time of writing
 * this is the ONLY continuously visible AI disclosure in the chat: the
 * attorney-frozen PER_MESSAGE_FOOTER renders inside "Show details", which
 * most people never open.
 *
 * So dismissing does not remove the disclosure, it REDUCES it. The full
 * sentence shows at the start of every session and can only be closed by
 * an explicit tap, never by scrolling and never on a timer. What remains
 * afterwards is a permanent one-line marker in the same place. The
 * disclosure is therefore continuous either way, and the full text returns
 * on the next launch, because dismissal is remembered for the app session
 * and not for the install.
 *
 * WORDING IS UNCHANGED, deliberately. It carries an em dash, which the
 * house style forbids everywhere else, and it is left alone: it mirrors
 * the web disclosure verbatim, and quietly editing compliance copy to
 * satisfy a typography rule is the wrong trade. Changing it is an
 * attorney's call, not a designer's.
 */

import { X } from 'lucide-react-native';
import { useState } from 'react';
import { Platform, Pressable, Text } from 'react-native';
import Animated, { LinearTransition } from 'react-native-reanimated';

import { Duration, Ease, messageEnter } from '@/constants/motion';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';

const COPY =
  "Session started — you're chatting with an AI assistant, not a person. " +
  'AI can make mistakes. Verify anything important with your care team.';

/** What stays behind after the full notice is dismissed. */
const SHORT = 'AI assistant · verify anything important with your care team';

/**
 * Dismissal is remembered for the APP SESSION, not per mount and not per
 * install. Module scope rather than state because the conversation surface
 * remounts whenever someone opens an older thread, and re-serving the full
 * notice each time would make the close button look broken. A relaunch is a
 * new session and brings the full text back, which is the behaviour the
 * disclosure requirement is about.
 */
let dismissedThisSession = false;

export function SessionMeta() {
  const [dismissed, setDismissed] = useState(dismissedThisSession);

  if (dismissed) {
    return (
      <Animated.View entering={messageEnter()} style={{ paddingVertical: Spacing.xs }}>
        <Text
          accessibilityRole={Platform.OS === 'android' ? 'alert' : undefined}
          accessibilityLabel={COPY}
          style={{
            textAlign: 'center',
            color: Colors.textMuted,
            fontSize: FontSize.sm,
            lineHeight: 17,
            fontFamily: Fonts.sans,
            paddingHorizontal: Spacing.xl,
          }}>
          {SHORT}
        </Text>
      </Animated.View>
    );
  }

  return (
    <Animated.View
      layout={LinearTransition.duration(Duration.state).easing(Ease.out)}
      accessibilityRole={Platform.OS === 'android' ? 'alert' : undefined}
      accessibilityLiveRegion="polite"
      style={{
        marginHorizontal: Spacing.md,
        marginTop: Spacing.md,
        marginBottom: Spacing.xs,
        paddingVertical: Spacing.md,
        paddingLeft: Spacing.lg,
        paddingRight: Spacing.xs,
        borderRadius: Radius.lg,
        backgroundColor: Colors.surface,
        borderWidth: 1,
        borderColor: Colors.border,
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: Spacing.sm,
      }}>
      <Text
        style={{
          flex: 1,
          color: Colors.textSecondary,
          fontSize: FontSize.base,
          lineHeight: 19,
          fontFamily: Fonts.sans,
        }}>
        {COPY}
      </Text>
      <Pressable
        onPress={() => {
          dismissedThisSession = true;
          setDismissed(true);
        }}
        accessibilityRole="button"
        accessibilityLabel="Dismiss the AI notice"
        hitSlop={12}
        style={{ padding: Spacing.xs }}>
        <X size={16} color={Colors.textMuted} />
      </Pressable>
    </Animated.View>
  );
}
