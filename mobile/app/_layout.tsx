import { DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { useFonts as useFraunces, Fraunces_400Regular, Fraunces_700Bold } from '@expo-google-fonts/fraunces';
import { useFonts as useGeist, Geist_400Regular, Geist_500Medium, Geist_600SemiBold, Geist_700Bold } from '@expo-google-fonts/geist';
import { QueryClientProvider } from '@tanstack/react-query';
import { Stack, useRouter, useSegments } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';
import 'react-native-reanimated';

import '../global.css';
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

    if (data.state_restricted) {
      if (top !== '(onboarding)' || second !== 'state-restricted') {
        router.replace('/(onboarding)/state-restricted');
      }
      return;
    }

    if (data.needs_consent) {
      if (top !== '(onboarding)') router.replace('/(onboarding)/consent');
      return;
    }

    // All clear → main app
    if (top !== '(tabs)') router.replace('/(tabs)');
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
      }}>
      <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      <Stack.Screen name="(onboarding)" options={{ headerShown: false }} />
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="profile" options={{ title: 'Profile' }} />
      <Stack.Screen name="tools" options={{ headerShown: false }} />
      <Stack.Screen name="settings" options={{ headerShown: false }} />
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
    <QueryClientProvider client={queryClient}>
      <ThemeProvider value={navTheme}>
        <RootGate />
        <StatusBar style="dark" />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
