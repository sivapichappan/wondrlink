import AsyncStorage from '@react-native-async-storage/async-storage';
import { DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { useFonts as useInstrumentSans, InstrumentSans_400Regular, InstrumentSans_500Medium, InstrumentSans_600SemiBold, InstrumentSans_700Bold } from '@expo-google-fonts/instrument-sans';
import { useFonts as useSourceSerif, SourceSerif4_400Regular, SourceSerif4_400Regular_Italic, SourceSerif4_600SemiBold, SourceSerif4_700Bold } from '@expo-google-fonts/source-serif-4';
import { QueryClientProvider } from '@tanstack/react-query';
import { Stack, useRouter, useSegments } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
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


  // A tapped notification opens what it is about. Mounted here rather than in a
  // screen so it also catches a cold launch, and given hasSession so it does
  // not navigate into a route the gate below is about to redirect away from.
  useNotificationRouting(!!ack.hasSession);

  useEffect(() => {
    if (ack.sessionLoading) return;
    if (ack.hasSession && ack.isLoading) return;

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
      // Read at DECISION time, never cached at mount: this gate mounts
      // before the welcome screen it renders, so a flag captured in a
      // mount effect is always the value from BEFORE the tap, and every
      // clinician would land on the patient consent.
      void (async () => {
        let intent = false;
        try {
          intent = (await AsyncStorage.getItem(REVIEWER_INTENT_KEY)) === '1';
        } catch {
          intent = false;
        }
        router.replace(
          (intent ? '/(onboarding)/reviewer-apply' : '/(onboarding)/consent') as never,
        );
      })();
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
    segments,
    router,
  ]);

  if (ack.sessionLoading || (ack.hasSession && ack.isLoading)) {
    // Paper, not white. This is the app's cold-launch frame, and it used to
    // paint #FFFFFF against a product whose ground is #F6F7F3 — so every
    // single launch flashed white before settling. A launch is three steps
    // (splash, this, first screen) and each one that changes colour reads
    // as a stutter.
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.paper }}>
        <ActivityIndicator color={Colors.primary} />
      </View>
    );
  }

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.paper },
        headerTintColor: Colors.textPrimary,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: Colors.paper },
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
  const [sansLoaded, sansError] = useInstrumentSans({
    InstrumentSans_400Regular,
    InstrumentSans_500Medium,
    InstrumentSans_600SemiBold,
    InstrumentSans_700Bold,
  });
  const [serifLoaded, serifError] = useSourceSerif({
    SourceSerif4_400Regular,
    SourceSerif4_400Regular_Italic,
    SourceSerif4_600SemiBold,
    SourceSerif4_700Bold,
  });
  // A FAILED font load must not hold the app hostage. These two families
  // arrive as new assets in the first OTA that carries the redesign, and
  // `loaded` never becomes true if their download fails — which, with a
  // bare `if (!fontsLoaded) return null`, is a permanently blank app that
  // no amount of relaunching fixes. React Native falls back to the system
  // face for a missing family, so an ugly screen beats no screen.
  const fontsSettled = (sansLoaded || !!sansError) && (serifLoaded || !!serifError);

  useEffect(() => {
    if (fontsSettled) SplashScreen.hideAsync().catch(() => {});
  }, [fontsSettled]);

  if (!fontsSettled) return null;

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
