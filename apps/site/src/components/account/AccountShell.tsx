import type { ReactNode } from "react";
import PublicHeader from "@/components/PublicHeader";
import Footer from "@/components/Footer";
import AccountNav from "@/components/account/AccountNav";

/**
 * Shared chrome for the espace client zones (PR3): Navbar + side nav +
 * content + Footer. Pages compose their content as children.
 *
 * Login / onboarding deliberately do NOT use this shell — they have a
 * full-bleed visual treatment without the side navigation.
 */
export default function AccountShell({
  title,
  intro,
  children,
}: {
  title: string;
  intro?: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen bg-vz-bg">
      <PublicHeader />
      <div className="max-w-6xl mx-auto px-4 pt-12 pb-24 md:flex md:gap-8">
        <AccountNav />
        <section className="flex-1 min-w-0 mt-12 md:mt-0">
          <header className="mb-8">
            <h1 className="text-3xl font-display font-bold text-black">{title}</h1>
            {intro && <p className="text-gray-600 mt-1 max-w-2xl">{intro}</p>}
          </header>
          {children}
        </section>
      </div>
      <Footer />
    </main>
  );
}
