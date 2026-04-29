"use client";

import { FormEvent, useState } from "react";
import AddressBlock from "../_components/AddressBlock";

export default function DevContact() {
  const [sent, setSent] = useState(false);

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSent(true);
  }

  return (
    <main className="bg-vz-bg min-h-screen">
      <section className="max-w-6xl mx-auto px-6 py-16 lg:py-24">
        <h1 className="font-mockSerif italic text-vz-teal text-6xl md:text-8xl">Contact</h1>

        <div className="mt-12 grid lg:grid-cols-2 gap-12 lg:gap-20">
          <div>
            <AddressBlock />
          </div>

          <div className="w-full">
            {sent ? (
              <div className="rounded-2xl border border-vz-teal/30 bg-white p-8 text-center">
                <p className="font-mockSerif text-2xl text-vz-teal">Merci !</p>
                <p className="mt-2 text-sm text-black/70">
                  Votre message nous est bien parvenu. Nous vous répondons sous 48 h.
                </p>
              </div>
            ) : (
              <form onSubmit={onSubmit} className="space-y-4">
                <div className="grid sm:grid-cols-2 gap-4">
                  <Field id="nom" label="Nom" />
                  <Field id="email" label="E-mail" type="email" required />
                </div>
                <Field id="tel" label="Numéro de téléphone" type="tel" />
                <Field id="comment" label="Commentaire" textarea />
                <button
                  type="submit"
                  className="inline-flex items-center rounded-full bg-vz-accent-soft px-10 py-3 text-sm tracking-widest font-medium text-black hover:bg-vz-accent transition-colors"
                >
                  ENVOYER
                </button>
              </form>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

function Field({
  id,
  label,
  type = "text",
  required = false,
  textarea = false,
}: {
  id: string;
  label: string;
  type?: string;
  required?: boolean;
  textarea?: boolean;
}) {
  const placeholder = required ? `${label} *` : label;
  const cls =
    "w-full rounded-lg border border-vz-accent-soft/60 bg-vz-bg/40 px-4 py-3 text-sm text-black placeholder:text-vz-teal/70 focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal";
  return (
    <div>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      {textarea ? (
        <textarea id={id} name={id} rows={5} placeholder={placeholder} required={required} className={cls} />
      ) : (
        <input id={id} name={id} type={type} placeholder={placeholder} required={required} className={cls} />
      )}
    </div>
  );
}
