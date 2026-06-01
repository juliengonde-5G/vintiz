"use client";

import { FormEvent, useState } from "react";

export default function NewsletterCard() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setDone(true);
  }

  return (
    <div className="relative mx-auto max-w-md">
      {/* Pink tag shape with punched hole */}
      <div className="relative bg-vz-accent-soft rounded-[28px] px-8 pt-14 pb-10 shadow-sm">
        <span className="absolute top-4 left-1/2 -translate-x-1/2 h-5 w-5 rounded-full bg-vz-bg" />
        <h3 className="text-center font-display text-[1.6rem] leading-tight text-black">
          Et si on restait en
        </h3>
        <p className="text-center italic text-2xl text-black mb-4" style={{ fontFamily: "'DM Serif Display', Georgia, serif" }}>
          contact ?
        </p>
        <p className="text-center text-[13px] text-black/80 leading-relaxed mb-5">
          Une dose d&apos;inspiration, des conseils mode responsable, et des offres
          exclusives rien que pour vous. <span aria-hidden>💌</span> Inscrivez-vous et laissez
          la créativité venir à vous !
        </p>
        {done ? (
          <p className="rounded-full bg-white px-4 py-3 text-center text-sm text-vz-teal">
            Merci ! Nous vous recontactons très vite.
          </p>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-3">
            <input
              type="email"
              required
              placeholder="contact@vintiz.fr"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-full bg-white px-5 py-3 text-sm text-black placeholder:text-black/40 focus:outline-none focus:ring-2 focus:ring-vz-teal"
            />
            <button
              type="submit"
              className="mx-auto inline-flex items-center justify-center rounded-full bg-[#4B3A5A] px-10 py-3 text-sm tracking-wider text-white hover:bg-[#3e3049] transition-colors"
            >
              S&apos;INSCRIRE
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
