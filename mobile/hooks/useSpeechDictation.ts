/**
 * useSpeechDictation — on-device speech-to-text for longer-form capture
 * (e.g. recording a doctor's appointment into the Visit Recap tool).
 *
 * Transcription runs on the device via the native Speech framework
 * (`requiresOnDeviceRecognition: true`) — the audio is never recorded to a
 * file or uploaded anywhere. iOS will sometimes end a recognition session on
 * its own after a pause; while the user still intends to be recording we
 * transparently resume so a long visit keeps transcribing.
 */

import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from 'expo-speech-recognition';
import { useCallback, useRef, useState } from 'react';
import { Alert } from 'react-native';

const RECOGNITION_OPTS = {
  lang: 'en-US',
  interimResults: true,
  continuous: true,
  requiresOnDeviceRecognition: true,
} as const;

function join(...parts: string[]): string {
  return parts.map((p) => p.trim()).filter(Boolean).join(' ');
}

export function useSpeechDictation() {
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  // Committed (final) text; interim results are layered on top for display.
  const finalRef = useRef('');
  // True only when the user explicitly stops — distinguishes a real stop from
  // iOS auto-ending the session so we know whether to resume.
  const userStoppedRef = useRef(false);

  useSpeechRecognitionEvent('result', (e) => {
    const latest = e.results[0]?.transcript ?? '';
    if (e.isFinal) {
      finalRef.current = join(finalRef.current, latest);
      setTranscript(finalRef.current);
    } else {
      setTranscript(join(finalRef.current, latest));
    }
  });

  useSpeechRecognitionEvent('end', () => {
    if (!userStoppedRef.current) {
      try {
        ExpoSpeechRecognitionModule.start(RECOGNITION_OPTS);
        return;
      } catch {
        // fall through to stop if resume fails
      }
    }
    setRecording(false);
  });

  useSpeechRecognitionEvent('error', (e) => {
    // "no-speech" just means a silent stretch — keep listening (the 'end'
    // handler will resume), don't surface anything.
    if (e.error === 'no-speech') return;
    userStoppedRef.current = true;
    setRecording(false);
    if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
      Alert.alert(
        'Microphone access needed',
        'Enable Microphone and Speech Recognition for Sage in Settings to record a visit.',
      );
      return;
    }
    Alert.alert(
      'Voice capture unavailable',
      e.message || 'Could not transcribe right now. You can type your notes instead.',
    );
  });

  const start = useCallback(async (seed = '') => {
    try {
      const perm = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!perm.granted) {
        Alert.alert(
          'Microphone access needed',
          'Enable Microphone and Speech Recognition for Sage in Settings to record a visit.',
        );
        return;
      }
      finalRef.current = seed.trim();
      setTranscript(finalRef.current);
      userStoppedRef.current = false;
      setRecording(true);
      ExpoSpeechRecognitionModule.start(RECOGNITION_OPTS);
    } catch (err) {
      setRecording(false);
      Alert.alert(
        'Voice capture unavailable',
        err instanceof Error ? err.message : 'Could not start recording.',
      );
    }
  }, []);

  const stop = useCallback(() => {
    userStoppedRef.current = true;
    ExpoSpeechRecognitionModule.stop();
    setRecording(false);
  }, []);

  // Keep finalRef in sync with manual edits so resuming appends correctly.
  const edit = useCallback((value: string) => {
    finalRef.current = value;
    setTranscript(value);
  }, []);

  const reset = useCallback(() => {
    finalRef.current = '';
    setTranscript('');
  }, []);

  return { recording, transcript, start, stop, edit, reset };
}
