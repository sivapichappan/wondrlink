/**
 * NavOverlay — shared open/close state for the app-shell overlays.
 *
 * The left drawer and the Help/SOS bottom sheet are mounted ONCE in the (app)
 * group layout so they float above every screen without remounting on push.
 * Their trigger lives elsewhere (the per-screen TopBar's menu button and SOS
 * pill), so the visibility state is lifted into this context.
 */

import { createContext, useCallback, useContext, useMemo, useState } from 'react';

interface NavOverlayValue {
  drawerOpen: boolean;
  helpOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
  openHelp: () => void;
  closeHelp: () => void;
}

const NavOverlayContext = createContext<NavOverlayValue | null>(null);

export function NavOverlayProvider({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const openDrawer = useCallback(() => setDrawerOpen(true), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  const openHelp = useCallback(() => setHelpOpen(true), []);
  const closeHelp = useCallback(() => setHelpOpen(false), []);

  const value = useMemo(
    () => ({ drawerOpen, helpOpen, openDrawer, closeDrawer, openHelp, closeHelp }),
    [drawerOpen, helpOpen, openDrawer, closeDrawer, openHelp, closeHelp],
  );

  return <NavOverlayContext.Provider value={value}>{children}</NavOverlayContext.Provider>;
}

export function useNavOverlay(): NavOverlayValue {
  const ctx = useContext(NavOverlayContext);
  if (!ctx) {
    throw new Error('useNavOverlay must be used within a NavOverlayProvider');
  }
  return ctx;
}
