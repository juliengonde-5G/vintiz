import { ReactNode } from "react";

type Tone = "storefront" | "pink-shop" | "mirrors" | "rack" | "counter" | "model-brown" | "model-white" | "street-female" | "street-male" | "product" | "shop-interior";

const TONES: Record<Tone, string> = {
  storefront: "from-slate-800 via-slate-700 to-slate-900",
  "pink-shop": "from-pink-200 via-pink-300 to-rose-300",
  mirrors: "from-rose-200 via-pink-100 to-emerald-200",
  rack: "from-stone-200 via-amber-100 to-rose-200",
  counter: "from-pink-100 via-rose-100 to-stone-200",
  "model-brown": "from-amber-800 via-amber-700 to-stone-600",
  "model-white": "from-stone-200 via-stone-100 to-zinc-300",
  "street-female": "from-stone-700 via-stone-500 to-rose-300",
  "street-male": "from-zinc-800 via-zinc-700 to-stone-500",
  product: "from-stone-300 via-stone-200 to-stone-100",
  "shop-interior": "from-rose-100 via-pink-100 to-emerald-100",
};

export default function Placeholder({
  tone,
  label,
  className = "",
  children,
}: {
  tone: Tone;
  label?: string;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div
      className={`relative overflow-hidden bg-gradient-to-br ${TONES[tone]} ${className}`}
      role="img"
      aria-label={label ?? tone}
    >
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(255,255,255,0.25),transparent_70%)]" />
      {label && (
        <span className="absolute bottom-3 left-3 text-[10px] uppercase tracking-[0.2em] text-white/80 bg-black/30 px-2 py-1 rounded backdrop-blur-sm">
          {label}
        </span>
      )}
      {children}
    </div>
  );
}
