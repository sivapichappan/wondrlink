/**
 * (app) group shell — replaces the old 5-tab bottom bar.
 *
 * A headerless Stack (each screen owns its TopBar) with the drawer + Help sheet
 * mounted ONCE on top, coordinated via NavOverlay context. No bottom tabs: Home
 * is the root, everything else is reached through the drawer, Home chips, or the
 * SOS pill.
 */

import { Stack } from 'expo-router';
import { View } from 'react-native';

import { AppDrawer } from '@/components/common/AppDrawer';
import { Colors } from '@/constants/theme';

export default function AppLayout() {
  // NavOverlayProvider + HelpSheet live at the ROOT layout (reachable
  // everywhere). The drawer is app-group-only, so it stays mounted here.
  return (
    <View style={{ flex: 1, backgroundColor: Colors.surface }}>
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: Colors.surface },
        }}
      />
      <AppDrawer />
    </View>
  );
}
