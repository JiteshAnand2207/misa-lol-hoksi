"use client";

import { DashboardPrefetch } from "@/components/dashboard/DashboardPrefetch";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { DashboardTabState } from "@/components/dashboard/DashboardTabState";
import { RuntimeErrorBoundary } from "@/components/dashboard/RuntimeErrorBoundary";
import { AuthProvider } from "@/lib/auth-store";
import { DiscordLiveProvider } from "@/lib/discord-live";
import { FeatureFlagsProvider } from "@/lib/feature-flags";
import { I18nProvider } from "@/lib/i18n";
import { ProfileProvider } from "@/lib/profile-store";

export function DashboardProviders({ children }: { children: React.ReactNode }) {
  return (
    <RuntimeErrorBoundary>
      <I18nProvider>
        <DashboardTabState />
        <FeatureFlagsProvider>
          <AuthProvider>
            <DashboardPrefetch />
            <ProfileProvider>
              <DiscordLiveProvider>
                <DashboardShell>{children}</DashboardShell>
              </DiscordLiveProvider>
            </ProfileProvider>
          </AuthProvider>
        </FeatureFlagsProvider>
      </I18nProvider>
    </RuntimeErrorBoundary>
  );
}