import { DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { useFonts as useFraunces, Fraunces_400Regular, Fraunces_700Bold } from '@expo-google-fonts/fraunces';
import { useFonts as useGeist, Geist_400Regular, Geist_500Medium, Geist_600SemiBold, Geist_700Bold } from '@expo-google-fonts/geist';
import { QueryClientProvider } from '@tanstack/react-query';
import { Stack, useRouter, useSegments } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import 'react-native-reanimated';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import '../global.css';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import { HelpSheet } from '@/components/common/HelpSheet';
import { NavOverlayProvider } from '@/components/common/NavOverlay';
import { OfflineBanner } from '@/components/common/OfflineBanner';
import { Colors } from '@/constants/theme';
import { useAcknowledgement } from '@/hooks/useAcknowledgement';
import { queryClient } from '@/lib/query';
import { initSentry } from '@/lib/sentry';

SplashScreen.preventAutoHideAsync().catch(() => {});
initSentry();

const navTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: Colors.primary,
    background: Colors.surface,
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
      // account-type comes before consent, because the consent being asked for
      // is a PATIENT's consent to have their health data processed. A clinician
      // signing up to review content is not agreeing to that, and should not be
      // shown it. One extra tap for a patient; the only honest order for the
      // other path. Anything inside (onboarding) is left alone so the branch
      // itself can navigate.
      if (top !== '(onboarding)') router.replace('/(onboarding)/account-type' as never);
      return;
    }

    // Sage onboarding: consent is done but we don't know who this account is
    // for yet — the who-for + basics screens come before the app.
    if (data.needs_basics) {
      const inBasicsFlow =
        top === '(onboarding)' && (second === 'who-for' || second === 'basics');
      if (!inBasicsFlow) router.replace('/(onboarding)/who-for' as never);
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
  const [geistLoaded] = useGeist({
    Geist_400Regular,
    Geist_500Medium,
    Geist_600SemiBold,
    Geist_700Bold,
  });
  const [frauncesLoaded] = useFraunces({
    Fraunces_400Regular,
    Fraunces_700Bold,
  });
  const fontsLoaded = geistLoaded && frauncesLoaded;

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
