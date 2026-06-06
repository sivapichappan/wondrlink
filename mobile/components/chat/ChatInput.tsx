import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from 'expo-speech-recognition';
import { Mic, Send, Square } from 'lucide-react-native';
import { useRef, useState } from 'react';
import {
  Alert,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { Colors, Fonts, Radius } from '@/constants/theme';

const MAX_CHARS = 2000;

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

function joinParts(...parts: string[]): string {
  return parts.map((p) => p.trim()).filter(Boolean).join(' ');
}

export function ChatInput({ onSend, disabled, placeholder = 'Ask about colon cancer…' }: Props) {
  const [text, setText] = useState('');
  const [recording, setRecording] = useState(false);
  const overflow = text.length > MAX_CHARS;
  const canSend = !disabled && text.trim().length > 0 && !overflow;

  // Snapshot of typed text when dictation starts, plus accumulated final
  // segments. Live (interim) text is rendered on top without committing.
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
    // "no-speech" / "aborted" are benign (user paused or tapped stop).
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
      Alert.alert(
        'Voice input unavailable',
        err instanceof Error ? err.message : 'Could not start voice input.',
      );
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
        <MicButton recording={recording} disabled={disabled} onPress={toggleMic} />

        <View style={styles.inputCol}>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder={recording ? 'Listening…' : placeholder}
            placeholderTextColor={recording ? Colors.accent : Colors.textMuted}
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

        <SendButton canSend={canSend} onPress={submit} />
      </View>
    </View>
  );
}

function MicButton({
  recording,
  disabled,
  onPress,
}: {
  recording: boolean;
  disabled?: boolean;
  onPress: () => void;
}) {
  return (
    <View
      style={[
        styles.micCircle,
        recording && { backgroundColor: Colors.accent, borderColor: Colors.accent },
      ]}>
      <View style={styles.iconCenter} pointerEvents="none">
        {recording ? (
          <Square size={16} color={Colors.surface} fill={Colors.surface} strokeWidth={2} />
        ) : (
          <Mic size={20} color={Colors.primary} strokeWidth={2} />
        )}
      </View>
      <Pressable
        onPress={onPress}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel={recording ? 'Stop voice input' : 'Start voice input'}
        accessibilityState={{ disabled: !!disabled }}
        hitSlop={8}
        style={styles.pressOverlay}
        android_ripple={{ color: Colors.sidebarBg, borderless: true }}
      />
    </View>
  );
}

function SendButton({ canSend, onPress }: { canSend: boolean; onPress: () => void }) {
  return (
    <View
      style={[
        styles.sendCircle,
        {
          backgroundColor: canSend ? Colors.accent : Colors.sidebarBg,
          borderColor: canSend ? Colors.accent : Colors.border,
          shadowOpacity: canSend ? 0.3 : 0,
          elevation: canSend ? 4 : 0,
        },
      ]}>
      <View style={styles.iconCenter} pointerEvents="none">
        <Send
          size={20}
          color={canSend ? Colors.surface : Colors.textMuted}
          strokeWidth={2.4}
          style={{ marginLeft: -2 }}
        />
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
  inputCol: {
    flex: 1,
    minWidth: 0,
    marginHorizontal: 8,
  },
  input: {
    minHeight: 44,
    maxHeight: 140,
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 12,
    backgroundColor: Colors.surfaceMuted,
    borderRadius: Radius.md,
    color: Colors.textPrimary,
    fontSize: 16,
    fontFamily: Fonts.sans,
    lineHeight: 22,
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
  micCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    overflow: 'hidden',
    position: 'relative',
  },
  sendCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 1,
    overflow: 'hidden',
    position: 'relative',
    shadowColor: Colors.accent,
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
