import { View } from 'react-native';
import Svg, { Circle, Path, Line } from 'react-native-svg';

import { Colors } from '@/constants/theme';

interface Props {
  values: number[];
  width?: number;
  height?: number;
  /** Domain max — PHQ-9 caps at 27. */
  max?: number;
  color?: string;
}

export function Sparkline({ values, width = 220, height = 60, max = 27, color = Colors.primary }: Props) {
  if (!values || values.length === 0) {
    return <View style={{ width, height }} />;
  }
  const padX = 6;
  const padY = 4;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;
  const step = values.length > 1 ? innerW / (values.length - 1) : 0;

  const points = values.map((v, i) => {
    const x = padX + i * step;
    const norm = Math.max(0, Math.min(1, v / max));
    const y = padY + innerH - norm * innerH;
    return { x, y };
  });

  const d = points
    .map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`))
    .join(' ');

  return (
    <Svg width={width} height={height}>
      {/* Baseline */}
      <Line
        x1={padX}
        x2={width - padX}
        y1={padY + innerH}
        y2={padY + innerH}
        stroke={Colors.border}
        strokeWidth={1}
      />
      <Path d={d} stroke={color} strokeWidth={2} fill="none" />
      {points.map((p, i) => (
        <Circle key={i} cx={p.x} cy={p.y} r={3} fill={color} />
      ))}
    </Svg>
  );
}
