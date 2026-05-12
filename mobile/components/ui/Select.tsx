import { ChevronDown } from 'lucide-react-native';
import { useState } from 'react';
import { FlatList, Modal, Pressable, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Colors, Fonts, Radius } from '@/constants/theme';

interface Option {
  value: string;
  label: string;
}

interface Props {
  label?: string;
  value: string;
  onChange: (next: string) => void;
  options: Option[];
  placeholder?: string;
  error?: string;
}

export function Select({ label, value, onChange, options, placeholder = 'Select…', error }: Props) {
  const [open, setOpen] = useState(false);
  const selected = options.find((o) => o.value === value);

  return (
    <View style={{ gap: 6 }}>
      {label && (
        <Text style={{ color: Colors.textSecondary, fontSize: 12, fontFamily: Fonts.sansMedium }}>
          {label}
        </Text>
      )}
      <Pressable
        onPress={() => setOpen(true)}
        accessibilityRole="button"
        accessibilityHint="Opens a list to choose from"
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: Colors.surface,
          borderWidth: 1,
          borderColor: error ? Colors.danger : Colors.border,
          borderRadius: Radius.sm,
          paddingHorizontal: 12,
          minHeight: 44,
        }}>
        <Text
          style={{
            color: selected ? Colors.textPrimary : Colors.textMuted,
            fontSize: 16,
            fontFamily: Fonts.sans,
          }}>
          {selected ? selected.label : placeholder}
        </Text>
        <ChevronDown size={18} color={Colors.textMuted} />
      </Pressable>
      {error && <Text style={{ color: Colors.danger, fontSize: 12 }}>{error}</Text>}

      <Modal
        visible={open}
        animationType="slide"
        transparent
        onRequestClose={() => setOpen(false)}>
        <Pressable
          onPress={() => setOpen(false)}
          style={{ flex: 1, backgroundColor: 'rgba(15,32,28,0.45)', justifyContent: 'flex-end' }}>
          <Pressable onPress={() => {}} style={{ maxHeight: '70%', backgroundColor: Colors.surface, borderTopLeftRadius: 18, borderTopRightRadius: 18 }}>
            <SafeAreaView edges={['bottom']}>
              <View style={{ padding: 16, borderBottomWidth: 1, borderBottomColor: Colors.border }}>
                <Text style={{ fontFamily: Fonts.sansSemiBold, fontSize: 16, color: Colors.textPrimary }}>
                  {label ?? 'Choose'}
                </Text>
              </View>
              <FlatList
                data={options}
                keyExtractor={(item) => item.value}
                renderItem={({ item }) => (
                  <TouchableOpacity
                    onPress={() => {
                      onChange(item.value);
                      setOpen(false);
                    }}
                    style={{
                      paddingVertical: 14,
                      paddingHorizontal: 16,
                      borderBottomWidth: 1,
                      borderBottomColor: Colors.border,
                      backgroundColor: item.value === value ? Colors.sidebarBg : Colors.surface,
                    }}>
                    <Text style={{ color: Colors.textPrimary, fontSize: 15, fontFamily: Fonts.sans }}>
                      {item.label}
                    </Text>
                  </TouchableOpacity>
                )}
              />
            </SafeAreaView>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}
