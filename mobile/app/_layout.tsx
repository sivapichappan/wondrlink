import AsyncStorage from '@react-native-async-storage/async-storage';
import { DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { useFonts as useInstrumentSans, InstrumentSans_400Regular, InstrumentSans_500Medium, InstrumentSans_600SemiBold, InstrumentSans_700Bold } from '@expo-google-fonts/instrument-sans';
import { useFonts as useSourceSerif, SourceSerif4_400Regular, SourceSerif4_400Regular_Italic, SourceSerif4_600SemiBold, SourceSerif4_700Bold } from '@expo-google-fonts/source-serif-4';
import { QueryClientProvider } from '@tanstack/react-query';
import { Stack, useRouter, useSegments } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import 'react-native-reanimated';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { REVIEWER_INTENT_KEY } from './(auth)/welcome';

import '../global.css';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import { HelpSheet } from '@/components/common/HelpSheet';
import { NavOverlayProvider } from '@/components/common/NavOverlay';
import { OfflineBanner } from '@/components/common/OfflineBanner';
import { Colors } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { useNotificationRouting } from '@/hooks/useNotificationRouting';
import { queryClient } from '@/lib/query';
import { initSentry } from '@/lib/sentry';

SplashScreen.preventAutoHideAsync().catch(() => {});
initSentry();

const navTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: Colors.primary,
    background: Colors.paper,
    card: Colors.surface,
    text: Colors.textPrimary,
    border: Colors.border,
    notification: Colors.accent,
  },
};

function RootGate() {
  const router = useRouter();
  const segments = useSegments();
  const ack = useAcknowledgement();

  // Whether this account came in through the welcome screen's "For
  // oncologists" door. Read once; null means "not known yet", which is not
  // the same as false and must not route anyone while it loads.
  const [reviewerIntent, setReviewerIntent] = useState<boolean | null>(null);
  useEffect(() => {
    AsyncStorage.getItem(REVIEWER_INTENT_KEY)
      .then((v) => setReviewerIntent(v === '1'))
      .catch(() => setReviewerIntent(false));
  }, []);

  // A tapped notification opens what it is about. Mounted here rather than in a
  // screen so it also catches a cold launch, and given hasSession so it does
  // not navigate into a route the gate below is about to redirect away from.
  useNotificationRouting(!!ack.hasSession);

  useEffect(() => {
    if (ack.sessionLoading) return;
    if (ack.hasSession && ack.isLoading) return;
    if (reviewerIntent === null) return;

    const segs = segments as readonly string[];
    const top = segs[0];
    const second = segs[1];

    // No session → must be in (auth)
    if (!ack.hasSession) {
      if (top !== '(auth)') router.replace('/(auth)/welcome');
      return;
    }

    // Have session — wait for acknowledgement response
    const data = ack.data;
    if (!data) return;

    // Reviewer accounts branch FIRST. A reviewer is never a patient (the
    // database enforces the exclusivity in both directions), so they must not
    // fall through into patient onboarding — completing it would try to create
    // a patient profile and be rejected, leaving the account stuck.
    //
    // Three outcomes, not two, and the middle one is the reason this reads a
    // status rather than a boolean:
    //
    //   requested / invited — applied, waiting on an admin. Not a reviewer yet
    //     and not a patient either, so the pending screen is the ONLY place
    //     they can be. Before the server sent a status they looked exactly like
    //     a stranger, and the app had nowhere to send them but onboarding.
    //   active — a full user of the app. They fall THROUGH to the normal
    //     branches below and get the same home, chat and drawer everyone else
    //     does, with Approvals as one more item in it. The old exclusive
    //     redirect to /review is gone: a physician vouching for patient-facing
    //     wording has to be able to see the product it appears in.
    //   revoked / none — an ordinary patient path.
    const reviewerStatus = data.reviewer_status ?? (data.is_reviewer ? 'active' : null);

    if (reviewerStatus === 'requested' || reviewerStatus === 'invited') {
      const onPending = top === '(onboarding)' && second === 'reviewer-pending';
      if (!onPending) router.replace('/(onboarding)/reviewer-pending' as never);
      return;
    }

    if (reviewerStatus === 'active') {
      // Skip the patient-only gates (consent, state, basics) — none of them can
      // be satisfied by an account that may not hold a patient profile.
      if (top === '(auth)' || top === '(onboarding)' || top == null) {
        router.replace('/');
      }
      return;
    }

    if (data.state_restricted) {
      if (top !== '(onboarding)' || second !== 'state-restricted') {
        router.replace('/(onboarding)/state-restricted');
      }
      return;
    }

    if (data.needs_consent) {
      // The account-type FORK is gone (redesign change 5): every patient used
      // to be asked which kind of account they wanted before they could
      // start. What it protected is still real, though — the consent being
      // asked for is a PATIENT's consent to have their health data
      // processed, and a clinician signing up to review wording is not
      // agreeing to that. So the welcome screen's "For oncologists" link
      // records the intent, and it routes them past this screen instead.
      // Anything inside (onboarding) is left alone so the branch can navigate.
      if (top === '(onboarding)') return;
      if (reviewerIntent) {
        router.replace('/(onboarding)/reviewer-apply' as never);
      } else {
        router.replace('/(onboarding)/consent' as never);
      }
      return;
    }

    // The ONE surviving onboarding question. Everything the "just four
    // things" form used to ask is learned in the conversation now, so this
    // gate waits on the question itself rather than on a name existing.
    if (!data.perspective_set) {
      const onWhoFor = top === '(onboarding)' && second === 'who-for';
      if (!onWhoFor) router.replace('/(onboarding)/who-for' as never);
      return;
    }

    // All clear → main app. Only redirect when the user is still parked in
    // auth/onboarding; otherwise leave them on whatever root-stack screen
    // they pushed (profile, tools, settings) so the back-stack behaves.
    if (top === '(auth)' || top === '(onboarding)' || top == null) {
      router.replace('/');
    }
  }, [
    ack.sessionLoading,
    ack.hasSession,
    ack.isLoading,
    ack.data,
    reviewerIntent,
    segments,
    router,
  ]);

  if (ack.sessionLoading || (ack.hasSession && ack.isLoading)) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.surface }}>
        <ActivityIndicator color={Colors.primary} />
      </View>
    );
  }

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.surface },
        headerTintColor: Colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: Colors.surface },
        animation: 'slide_from_right',
        animationDuration: 250,
      }}>
      <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      <Stack.Screen name="(onboarding)" options={{ headerShown: false }} />
      <Stack.Screen name="(app)" options={{ headerShown: false }} />
      <Stack.Screen name="profile" options={{ headerShown: false }} />
      <Stack.Screen name="tools" options={{ headerShown: false }} />
      <Stack.Screen name="settings" options={{ headerShown: false }} />
      <Stack.Screen name="review" options={{ headerShown: false }} />
    </Stack>
  );
}

export default function RootLayout() {
  // Semantic typography (redesign 2026-08-24): Source Serif 4 is Sage's
  // voice, Instrument Sans is the interface.
  const [sansLoaded] = useInstrumentSans({
    InstrumentSans_400Regular,
    InstrumentSans_500Medium,
    InstrumentSans_600SemiBold,
    InstrumentSans_700Bold,
  });
  const [serifLoaded] = useSourceSerif({
    SourceSerif4_400Regular,
    SourceSerif4_400Regular_Italic,
    SourceSerif4_600SemiBold,
    SourceSerif4_700Bold,
  });
  const fontsLoaded = sansLoaded && serifLoaded;

  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync().catch(() => {});
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ErrorBoundary>
          <QueryClientProvider client={queryClient}>
            <ThemeProvider value={navTheme}>
              {/* NavOverlay lives at the root so the SOS/Help sheet is reachable
                  from EVERY stack (app, tools, profile, settings). */}
              <NavOverlayProvider>
                <OfflineBanner />
                <RootGate />
                <HelpSheet />
                <StatusBar style="dark" />
              </NavOverlayProvider>
            </ThemeProvider>
          </QueryClientProvider>
        </ErrorBoundary>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
