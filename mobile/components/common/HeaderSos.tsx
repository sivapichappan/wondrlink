/**
 * HeaderSos — the SOS/Help pill as a native-stack `headerRight`.
 *
 * The tools / profile / settings stacks use React Navigation's native header
 * (not the app-shell TopBar), so they get the persistent Help affordance via
 * this small wrapper. Opens the root-mounted Help sheet through NavOverlay.
 */

import { View } from 'react-native';

import { SosPill } from './TopBar';
import { useNavOverlay } from './NavOverlay';

export function HeaderSos() {
  const { openHelp } = useNavOverlay();
  return (
    <View style={{ marginRight: 12 }}>
      <SosPill onPress={openHelp} />
    </View>
  );
}
