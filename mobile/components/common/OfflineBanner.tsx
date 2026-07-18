import NetInfo, { type NetInfoState } from '@react-native-community/netinfo';
import { WifiOff } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';

/**
 * Top-aligned banner that appears whenever NetInfo reports the device is
 * offline. Hidden during the initial unknown state to avoid a flash.
 */
export function OfflineBanner() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const sub = NetInfo.addEventListener((state: NetInfoState) => {
      // isConnected: false → offline; null → unknown (don't show yet)
      if (state.isConnected === false) setOffline(true);
      else if (state.isConnected === true) setOffline(false);
    });
    return () => sub();
  }, []);

  if (!offline) return null;

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
        paddingHorizontal: 14,
        paddingVertical: 8,
        backgroundColor: Colors.warningBg,
      }}>
      <WifiOff size={14} color={Colors.warning} />
      <Text style={{ color: Colors.warning, fontSize: 12, fontFamily: Fonts.sansMedium }}>
        You're offline. Sage needs a connection to answer new questions.
      </Text>
    </View>
  );
}
