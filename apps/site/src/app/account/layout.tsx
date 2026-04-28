import type { ReactNode } from "react";

/**
 * Espace client layout — does NOT render Navbar/Footer because the
 * legacy login/data/onboarding pages already include them. New pages
 * (PR3 zones) wrap their content in <AccountShell>.
 */
export default function AccountLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
