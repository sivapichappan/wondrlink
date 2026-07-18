import { AlertOctagon } from 'lucide-react-native';
import { Component, type ReactNode } from 'react';
import { ScrollView, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { Sentry } from '@/lib/sentry';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    Sentry.captureException(error, { extra: info as Record<string, unknown> });
  }

  reset = () => this.setState({ error: null });

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <ScrollView
        contentContainerStyle={{
          flexGrow: 1,
          justifyContent: 'center',
          padding: 24,
          gap: 16,
          backgroundColor: Colors.surface,
        }}>
        <View style={{ alignItems: 'center', marginBottom: 8 }}>
          <View
            style={{
              width: 56,
              height: 56,
              borderRadius: 28,
              backgroundColor: Colors.emergencyBg,
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <AlertOctagon size={28} color={Colors.danger} />
          </View>
        </View>
        <Text
          style={{
            fontFamily: Fonts.serifBold,
            fontSize: 22,
            color: Colors.textPrimary,
            textAlign: 'center',
          }}>
          Something went wrong
        </Text>
        <Text
          style={{
            color: Colors.textSecondary,
            fontSize: 14,
            lineHeight: 21,
            textAlign: 'center',
          }}>
          Sage hit an unexpected error. The team has been notified. You can try again, your
          chat history is safe.
        </Text>
        <View
          style={{
            padding: 12,
            backgroundColor: Colors.sidebarBg,
            borderRadius: Radius.md,
          }}>
          <Text
            style={{
              color: Colors.textMuted,
              fontSize: 11,
              fontFamily: 'Courier',
            }}>
            {this.state.error.name}: {this.state.error.message}
          </Text>
        </View>
        <Button label="Try again" fullWidth size="lg" onPress={this.reset} />
      </ScrollView>
    );
  }
}
