/**
 * ChatInput — composer spec "2a".
 *
 * Row: [ + ] [ input with inline mic (one-tap dictation) ] [ send ].
 * Tapping "+" dims the screen and raises a QUICK ACTIONS sheet; "+" becomes a
 * filled teal "✕". Dictation stays one tap for older users — the mic lives
 * inside the field and drives on-device (never-uploaded) speech recognition.
 *
 * NativeWind rule: Pressable visuals live on static inner Views.
 */

import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from 'expo-speech-recognition';
import { router } from 'expo-router';
import { AudioLines, ClipboardList, Mic, Plus, ScanLine, Send, Square, X } from 'lucide-react-native';
import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { IconCircle } from '@/components/ui/IconCircle';
import { Colors, FontSize, Fonts, Radius, Spacing } from '@/constants/theme';
import { APP_NAME } from '@shared/branding';

const MAX_CHARS = 2000;

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
  /** Pre-fill the composer (e.g. "My ZIP code is ") without sending. */
  prefill?: string;
}

function joinParts(...parts: string[]): string {
  return parts.map((p) => p.trim()).filter(Boolean).join(' ');
}

export function ChatInput({ onSend, disabled, placeholder = "Let's talk", prefill }: Props) {
  const insets = useSafeAreaInsets();
  const [text, setText] = useState('');
  const [recording, setRecording] = useState(false);
  const [actionsOpen, setActionsOpen] = useState(false);
  const overflow = text.length > MAX_CHARS;
  const canSend = !disabled && text.trim().length > 0 && !overflow;

  // Prefill the composer (never sends) — used by the trials "one quick
  // question" hand-off. Only applies over an empty composer.
  useEffect(() => {
    if (prefill && !text) setText(prefill);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  const baseRef = useRef('');
  const finalRef = useRef('');

  useSpeechRecognitionEvent('result', (e) => {
    const latest = e.results[0]?.transcript ?? '';
    if (e.isFinal) {
      finalRef.current = joinParts(finalRef.current, latest);
      setText(joinParts(baseRef.current, finalRef.current));
    } else {
      setText(joinParts(baseRef.current, finalRef.current, latest));
    }
  });

  useSpeechRecognitionEvent('end', () => setRecording(false));

  useSpeechRecognitionEvent('error', (e) => {
    setRecording(false);
    if (e.error === 'no-speech' || e.error === 'aborted') return;
    if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
      Alert.alert(
        'Microphone access needed',
        `Enable Microphone and Speech Recognition for ${APP_NAME} in Settings to use voice input.`,
      );
      return;
    }
    Alert.alert('Voice input unavailable', e.message || 'Could not transcribe. Please type instead.');
  });

  const startListening = async () => {
    try {
      const perm = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!perm.granted) {
        Alert.alert(
          'Microphone access needed',
          `Enable Microphone and Speech Recognition for ${APP_NAME} in Settings to use voice input.`,
        );
        return;
      }
      baseRef.current = text;
      finalRef.current = '';
      setRecording(true);
      ExpoSpeechRecognitionModule.start({
        lang: 'en-US',
        interimResults: true,
        continuous: true,
        // Keep the patient's audio on the device — never sent to Apple's servers.
        requiresOnDeviceRecognition: true,
      });
    } catch (err) {
      setRecording(false);
      Alert.alert('Voice input unavailable', err instanceof Error ? err.message : 'Could not start voice input.');
    }
  };

  const stopListening = () => {
    ExpoSpeechRecognitionModule.stop();
    setRecording(false);
  };

  const toggleMic = () => {
    if (recording) stopListening();
    else startListening();
  };

  const submit = () => {
    if (!canSend) return;
    if (recording) stopListening();
    onSend(text.trim());
    setText('');
    finalRef.current = '';
    baseRef.current = '';
  };

  return (
    <View style={[styles.bar, { marginBottom: insets.bottom }]}>
      <View style={styles.row}>
        {/* + / quick actions */}
        <Pressable onPress={() => setActionsOpen(true)} disabled={disabled} accessibilityRole="button" accessibilityLabel="Quick actions" hitSlop={8}>
          <View style={styles.plusCircle}>
            <Plus size={21} color={Colors.primary} strokeWidth={2} />
          </View>
        </Pressable>

        {/* Input */}
        <View style={styles.inputCol}>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder={recording ? 'Listening…' : placeholder}
            placeholderTextColor={recording ? Colors.primary : Colors.textMuted}
            multiline
            editable={!disabled}
            blurOnSubmit={false}
            returnKeyType={Platform.OS === 'ios' ? 'default' : 'send'}
            onSubmitEditing={Platform.OS === 'android' ? submit : undefined}
            style={styles.input}
          />
          {overflow && (
            <View style={styles.overflowChip}>
              <Text style={styles.overflowText}>
                {text.length} / {MAX_CHARS}
              </Text>
            </View>
          )}
        </View>

        {/* Mic (one-tap dictation) + send */}
        <MicButton recording={recording} disabled={disabled} onPress={toggleMic} />
        <SendButton canSend={canSend} onPress={submit} />
      </View>

      <QuickActionsSheet open={actionsOpen} onClose={() => setActionsOpen(false)} />
    </View>
  );
}

function MicButton({ recording, disabled, onPress }: { recording: boolean; disabled?: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={recording ? 'Stop voice input' : 'Start voice input'}
      accessibilityState={{ disabled: !!disabled }}
      hitSlop={8}
      style={styles.micInline}>
      {recording ? (
        <Square size={15} color={Colors.primary} fill={Colors.primary} strokeWidth={2} />
      ) : (
        <Mic size={18} color={Colors.textMuted} strokeWidth={2} />
      )}
    </Pressable>
  );
}

function SendButton({ canSend, onPress }: { canSend: boolean; onPress: () => void }) {
  return (
    <View
      style={[
        styles.sendCircle,
        {
          backgroundColor: canSend ? Colors.primary : Colors.sidebarBg,
          borderColor: canSend ? Colors.primary : Colors.border,
          shadowOpacity: canSend ? 0.3 : 0,
          elevation: canSend ? 4 : 0,
        },
      ]}>
      <View style={styles.iconCenter} pointerEvents="none">
        <Send size={19} color={canSend ? Colors.surface : Colors.textMuted} strokeWidth={2.4} style={{ marginLeft: -2 }} />
      </View>
      <Pressable
        onPress={onPress}
        disabled={!canSend}
        accessibilityRole="button"
        accessibilityLabel="Send message"
        accessibilityState={{ disabled: !canSend }}
        hitSlop={8}
        style={styles.pressOverlay}
        android_ripple={{ color: 'rgba(255,255,255,0.25)', borderless: true }}
      />
    </View>
  );
}

function QuickActionsSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const insets = useSafeAreaInsets();

  const go = (path: string) => {
    onClose();
    setTimeout(() => router.push(path as never), 60);
  };

  // EXACTLY THREE (mockup screen 06). Trials and pre-visit questions are
  // never listed here — they arrive as cards Sage deals when they are
  // relevant, which is the whole point of killing the tool grid. The
  // wellness check-in is not a tool either: it becomes questions asked in
  // chat (change 4). Voice is the composer's own mic; "Sources used" moved
  // to the session line at the top of the thread, where the question
  // ("what is this built on?") actually gets asked.
  const items: { key: string; icon: React.ReactNode; title: string; body: string; onPress: () => void }[] = [
    {
      key: 'scan',
      icon: <ScanLine size={20} color={Colors.primary} />,
      title: 'Scan a report',
      body: 'A photo of any paper from your doctor',
      onPress: () => go('/tools/report-scan'),
    },
    {
      key: 'record',
      icon: <AudioLines size={20} color={Colors.primary} />,
      title: 'Record a visit',
      body: `${APP_NAME} listens and writes a plain summary`,
      onPress: () => go('/tools/visit-recap'),
    },
    {
      key: 'since',
      icon: <ClipboardList size={20} color={Colors.primary} />,
      title: 'Since your last visit',
      body: "What's changed, ready for your next appointment",
      // The compiler this row is named for is not built yet (it is below
      // the brief's top five). Pre-visit questions is the surface that
      // actually answers "what do I bring to the appointment", so the row
      // opens something that keeps its promise rather than the My Care hub,
      // which does not.
      onPress: () => go('/tools/previsit'),
    },
  ];

  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={{ flex: 1, backgroundColor: Colors.scrim }} onPress={onClose} accessibilityLabel="Close quick actions" />
      <View
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: Colors.surface,
          borderTopLeftRadius: Radius.xl,
          borderTopRightRadius: Radius.xl,
          paddingHorizontal: Spacing.md,
          paddingTop: Spacing.md,
          paddingBottom: insets.bottom + Spacing.lg,
          gap: Spacing.md,
        }}>
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <View style={{ flex: 1 }} />
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" hitSlop={8}>
            <IconCircle size={30} bg={Colors.primary}>
              <X size={17} color={Colors.surface} />
            </IconCircle>
          </Pressable>
        </View>
        <View>
          {items.map((it, i) => (
            <Pressable key={it.key} onPress={it.onPress} accessibilityRole="button" accessibilityLabel={it.title}>
              <View
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: Spacing.md,
                  paddingVertical: Spacing.lg,
                  paddingHorizontal: Spacing.sm,
                  borderTopWidth: i === 0 ? 0 : 1,
                  borderTopColor: Colors.border,
                }}>
                <IconCircle size={38} bg={Colors.sidebarBg}>
                  {it.icon}
                </IconCircle>
                <View style={{ flex: 1, gap: 2 }}>
                  <Text style={{ fontSize: FontSize.lg, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
                    {it.title}
                  </Text>
                  <Text style={{ fontSize: FontSize.base, color: Colors.textSecondary, lineHeight: 19 }}>
                    {it.body}
                  </Text>
                </View>
              </View>
            </Pressable>
          ))}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  // Floating rounded bar, lifted off the bottom edge.
  bar: {
    marginHorizontal: Spacing.md,
    marginTop: Spacing.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.surface,
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
    shadowColor: '#0F201C',
    shadowOpacity: 0.06,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  plusCircle: {
    width: 44,
    height: 44,
    borderRadius: Radius.pill,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  inputCol: {
    flex: 1,
    minWidth: 0,
    marginHorizontal: Spacing.xs,
  },
  input: {
    minHeight: 40,
    maxHeight: 120,
    paddingHorizontal: Spacing.md,
    paddingVertical: 9,
    backgroundColor: Colors.surfaceMuted,
    borderRadius: Radius.md,
    color: Colors.textPrimary,
    fontSize: 16,
    fontFamily: Fonts.sans,
    lineHeight: 20,
  },
  micInline: {
    width: 40,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  overflowChip: {
    alignSelf: 'flex-end',
    marginTop: 4,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
    backgroundColor: Colors.danger,
  },
  overflowText: {
    color: Colors.surface,
    fontSize: 11,
    fontFamily: Fonts.sansSemiBold,
  },
  sendCircle: {
    width: 44,
    height: 44,
    borderRadius: Radius.pill,
    borderWidth: 1,
    overflow: 'hidden',
    position: 'relative',
    shadowColor: Colors.primary,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
  },
  iconCenter: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pressOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
});
