import type { Metadata } from "next";
import { DM_Serif_Display } from "next/font/google";
import DevHeader from "./_components/DevHeader";
import DevFooter from "./_components/DevFooter";

const dmSerif = DM_Serif_Display({
  subsets: ["latin"],
  weight: ["400"],
  style: ["normal", "italic"],
  variable: "--font-mock-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Vintiz — Preview mockup",
  description: "Preview développeur — page d'accueil Vintiz basée sur le mockup Canva.",
  robots: { index: false, follow: false },
};

export default function DevLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`${dmSerif.variable} bg-vz-bg min-h-screen flex flex-col`}>
      <DevHeader />
      <div className="flex-1">{children}</div>
      <DevFooter />
    </div>
  );
}
