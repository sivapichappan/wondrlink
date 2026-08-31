/**
 * Whether the keyboard is currently up.
 *
 * Exists for one specific bug class: the bottom safe-area inset and the
 * keyboard both claim the same strip of screen. A composer that always
 * carries `marginBottom: insets.bottom` sits a home-indicator's height
 * (~34pt) above the keyboard once it opens, because KeyboardAvoidingView
 * has already padded by the full keyboard height and that height includes
 * the safe area. The inset is right when the keyboard is closed and wrong
 * when it is open, so something has to know which.
 *
 * `will` events on iOS so the layout moves in step with the keyboard rather
 * than a frame behind it; Android only emits the `did` pair.
 */

import { useEffect, useState } from 'react';
import { Keyboard, Platform } from 'react-native';

export function useKeyboardVisible(): boolean {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const show = Keyboard.addListener(showEvent, () => setVisible(true));
    const hide = Keyboard.addListener(hideEvent, () => setVisible(false));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  return visible;
}
