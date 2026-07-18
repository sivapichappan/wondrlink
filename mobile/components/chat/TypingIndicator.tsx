import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';

import { Colors } from '@/constants/theme';

const DOT_COUNT = 3;
const DOT_DELAY = 180;
const DOT_DURATION = 380;

export function TypingIndicator() {
  const dots = useRef(
    Array.from({ length: DOT_COUNT }, () => new Animated.Value(0)),
  ).current;

  useEffect(() => {
    const animation = Animated.parallel(
      dots.map((dot, i) =>
        Animated.loop(
          Animated.sequence([
            Animated.delay(i * DOT_DELAY),
            Animated.timing(dot, {
              toValue: 1,
              duration: DOT_DURATION,
              useNativeDriver: true,
            }),
            Animated.timing(dot, {
              toValue: 0,
              duration: DOT_DURATION,
              useNativeDriver: true,
            }),
            Animated.delay((DOT_COUNT - 1 - i) * DOT_DELAY),
          ]),
        ),
      ),
    );
    animation.start();
    return () => animation.stop();
  }, [dots]);

  return (
    <View
      style={styles.row}
      accessibilityRole="text"
      accessibilityLabel="Sage is typing">
      <Text style={styles.label}>Sage is typing</Text>
      <View style={styles.dots}>
        {dots.map((dot, i) => (
          <Animated.View
            key={i}
            style={[
              styles.dot,
              {
                opacity: dot.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0.3, 1],
                }),
                transform: [
                  {
                    translateY: dot.interpolate({
                      inputRange: [0, 1],
                      outputRange: [0, -3],
                    }),
                  },
                ],
              },
            ]}
          />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  label: {
    color: Colors.textMuted,
    fontSize: 11,
    fontStyle: 'italic',
  },
  dots: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  dot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: Colors.textMuted,
  },
});
