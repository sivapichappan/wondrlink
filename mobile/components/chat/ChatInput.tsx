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
import {
  Activity,
  AudioLines,
  ClipboardList,
  Microscope,
  Mic,
  NotebookPen,
  Paperclip,
  Plus,
  Send,
  Square,
  X,
} from 'lucide-react-native';
import { useRef, useState } from 'react';
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

import { Colors, Fonts, Radius } from '@/constants/theme';
import { useCareSnapshot } from '@/hooks/useCare';

const MAX_CHARS = 2000;

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

function joinParts(...parts: string[]): string {
  return parts.map((p) => p.trim()).filter(Boolean).join(' ');
}

export function ChatInput({ onSend, disabled, placeholder = 'Ask anything…' }: Props) {
  const [text, setText] = useState('');
  const [recording, setRecording] = useState(false);
  const [actionsOpen, setActionsOpen] = useState(false);
  const overflow = text.length > MAX_CHARS;
  const canSend = !disabled && text.trim().length > 0 && !overflow;

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
        'Enable Microphone and Speech Recognition for WondrChat in Settings to use voice input.',
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
          'Enable Microphone and Speech Recognition for WondrChat in Settings to use voice input.',
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
    <View style={styles.bar}>
      <View style={styles.row}>
        {/* Plus / quick actions */}
        <Pressable
          onPress={() => setActionsOpen(true)}
          disabled={disabled}
          accessibilityRole="button"
          accessibilityLabel="Quick actions"
          hitSlop={8}>
          <View style={styles.plusCircle}>
            <Plus size={21} color={Colors.primary} strokeWidth={2} />
          </View>
        </Pressable>

        {/* Input with inline mic */}
        <View style={styles.inputCol}>
          <View style={styles.inputPill}>
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
            <MicButton recording={recording} disabled={disabled} onPress={toggleMic} />
          </View>
          {overflow && (
            <View style={styles.overflowChip}>
              <Text style={styles.overflowText}>
                {text.length} / {MAX_CHARS}
              </Text>
            </View>
          )}
        </View>

        <SendButton canSend={canSend} onPress={submit} />
      </View>

      <QuickActionsSheet
        open={actionsOpen}
        onClose={() => setActionsOpen(false)}
        onVoice={() => {
          setActionsOpen(false);
          startListening();
        }}
      />
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

function QuickActionsSheet({ open, onClose, onVoice }: { open: boolean; onClose: () => void; onVoice: () => void }) {
  const insets = useSafeAreaInsets();
  const snap = useCareSnapshot();
  const days = snap.data?.days_since_symptom;
  const checkinDue = days == null || days >= 7;

  const go = (path: string) => {
    onClose();
    setTimeout(() => router.push(path as never), 60);
  };

  const items: {
    key: string;
    icon: React.ReactNode;
    title: string;
    sub: string;
    subUrgent?: boolean;
    onPress: () => void;
    tintBg?: string;
  }[] = [
    {
      key: 'attach',
      icon: <Paperclip size={16} color={Colors.primary} />,
      title: 'Attach photo or file',
      sub: 'Lab result, scan, pill bottle',
      onPress: () => {
        onClose();
        setTimeout(() => Alert.alert('Coming soon', 'Attaching photos and files will be available in a future update.'), 60);
      },
    },
    {
      key: 'checkin',
      icon: <Activity size={16} color={Colors.warning} />,
      tintBg: Colors.sosBg,
      title: 'Wellness check-in',
      sub: checkinDue ? 'Check-in due today' : 'Symptom, PHQ-9, GAD-7…',
      subUrgent: checkinDue,
      onPress: () => go('/tools/screening'),
    },
    {
      key: 'trials',
      icon: <Microscope size={16} color={Colors.primary} />,
      title: 'Find clinical trials',
      sub: 'Matched to your profile',
      onPress: () => go('/tools/clinical-trials'),
    },
    {
      key: 'previsit',
      icon: <ClipboardList size={16} color={Colors.primary} />,
      title: 'Pre-visit questions',
      sub: 'For your next visit',
      onPress: () => go('/tools/previsit'),
    },
    {
      key: 'recap',
      icon: <NotebookPen size={16} color={Colors.primary} />,
      title: 'Visit recap',
      sub: 'Record your appointment',
      onPress: () => go('/tools/visit-recap'),
    },
    {
      key: 'voice',
      icon: <AudioLines size={16} color={Colors.primary} />,
      title: 'Voice conversation',
      sub: 'Talk it through aloud',
      onPress: onVoice,
    },
  ];

  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={onClose}>
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
          paddingHorizontal: 14,
          paddingTop: 14,
          paddingBottom: insets.bottom + 16,
          gap: 12,
        }}>
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <Text style={{ flex: 1, fontFamily: Fonts.sansSemiBold, fontSize: 11, letterSpacing: 0.6, color: Colors.textMuted }}>
            QUICK ACTIONS
          </Text>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" hitSlop={8}>
            <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: Colors.primary, alignItems: 'center', justifyContent: 'center' }}>
              <X size={17} color={Colors.surface} />
            </View>
          </Pressable>
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 9 }}>
          {items.map((it) => (
            <Pressable key={it.key} onPress={it.onPress} accessibilityRole="button" accessibilityLabel={it.title} style={{ width: '48%' }}>
              <View
                style={{
                  backgroundColor: Colors.surfaceMuted,
                  borderWidth: 1,
                  borderColor: Colors.border,
                  borderRadius: Radius.lg,
                  padding: 11,
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 10,
                }}>
                <View
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 17,
                    backgroundColor: it.tintBg ?? Colors.sidebarBg,
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                  {it.icon}
                </View>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <Text numberOfLines={1} style={{ fontSize: 13, fontFamily: Fonts.sansSemiBold, color: Colors.textPrimary }}>
                    {it.title}
                  </Text>
                  <Text
                    numberOfLines={1}
                    style={{
                      fontSize: 10.5,
                      marginTop: 1,
                      color: it.subUrgent ? Colors.warning : Colors.textMuted,
                      fontFamily: it.subUrgent ? Fonts.sansSemiBold : Fonts.sans,
                    }}>
                    {it.sub}
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
  bar: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: Colors.surface,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  plusCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  inputCol: {
    flex: 1,
    minWidth: 0,
    marginHorizontal: 8,
  },
  inputPill: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: Colors.surfaceMuted,
    borderRadius: Radius.md,
    paddingRight: 6,
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 140,
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 12,
    color: Colors.textPrimary,
    fontSize: 16,
    fontFamily: Fonts.sans,
    lineHeight: 22,
  },
  micInline: {
    width: 36,
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
    borderRadius: 22,
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
