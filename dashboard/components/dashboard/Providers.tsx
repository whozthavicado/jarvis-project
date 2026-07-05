"use client";

import { NavigationProvider } from "@/hooks/useNavigation";
import { ToastProvider } from "@/hooks/useToast";
import { SettingsProvider } from "@/hooks/useSettings";
import { FavoritesProvider } from "@/hooks/useFavorites";
import { ZeroBackendProvider } from "@/hooks/useZeroBackend";
import { SettingsModal } from "./SettingsModal";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <SettingsProvider>
        <ZeroBackendProvider>
          <FavoritesProvider>
            <NavigationProvider>
              {children}
              <SettingsModal />
            </NavigationProvider>
          </FavoritesProvider>
        </ZeroBackendProvider>
      </SettingsProvider>
    </ToastProvider>
  );
}
