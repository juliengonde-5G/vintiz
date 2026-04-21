export default function AddressBlock({ align = "left" }: { align?: "left" | "center" }) {
  const alignCls = align === "center" ? "text-center items-center" : "text-left items-start";
  return (
    <div className={`flex flex-col gap-3 ${alignCls}`}>
      <h3 className="font-display text-xl tracking-wide">ADRESSE</h3>
      <p className="text-base leading-relaxed">
        6 Rue St Jacques,
        <br />27200 Vernon
      </p>
      <div className="flex items-center gap-2 text-base">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-teal/10 text-teal">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 16.92V21a1 1 0 0 1-1.09 1 19.86 19.86 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.86 19.86 0 0 1 3.22 4.09 1 1 0 0 1 4.21 3h4.09a1 1 0 0 1 1 .75 12.11 12.11 0 0 0 .66 2.67 1 1 0 0 1-.23 1l-1.73 1.73a16 16 0 0 0 6 6l1.73-1.73a1 1 0 0 1 1-.23 12.11 12.11 0 0 0 2.67.66 1 1 0 0 1 .75 1z" />
          </svg>
        </span>
        02 58 65 66 46
      </div>
      <div className="flex items-center gap-2 text-base">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-teal/10 text-teal">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
        </span>
        <a href="https://www.google.com/maps/place/6+Rue+St+Jacques,+27200+Vernon" className="underline underline-offset-4 hover:text-teal">
          S&apos;y rendre
        </a>
      </div>
      <h3 className="font-display text-xl tracking-wide mt-4">HORAIRES</h3>
      <p className="text-base leading-relaxed">
        Ouverture du mardi au samedi
        <br />De 10h30 à 19h
      </p>
    </div>
  );
}
