"use client";

import { FormEvent, useState } from "react";

type Status = "idle" | "loading" | "success" | "error";

export default function ContactForm() {
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("loading");

    const fd = new FormData(e.currentTarget);
    const subject = encodeURIComponent(
      `[vintiz.fr] Contact — ${fd.get("subject") || "demande générale"}`,
    );
    const body = encodeURIComponent(
      [
        `Nom : ${fd.get("name") || "—"}`,
        `Téléphone : ${fd.get("phone") || "—"}`,
        `E-mail : ${fd.get("email") || "—"}`,
        `Sujet : ${fd.get("subject") || "—"}`,
        "",
        `Message :`,
        `${fd.get("message") || "—"}`,
      ].join("\n"),
    );

    // Fallback mailto — endpoint backend dédié à brancher plus tard
    // (POST /api/contact à créer côté apps/site/src/app/api/).
    window.location.href = `mailto:contact@vintiz.fr?subject=${subject}&body=${body}`;

    setStatus("success");
    setMessage(
      "Votre client e-mail s'ouvre avec le message pré-rempli. Sinon écrivez-nous directement à contact@vintiz.fr.",
    );
  }

  if (status === "success") {
    return (
      <div className="rounded-2xl border border-vz-teal/30 bg-vz-surface p-8 text-center">
        <p className="font-display text-2xl text-vz-teal">Merci !</p>
        <p className="mt-3 text-sm text-vz-ink-soft leading-relaxed">{message}</p>
        <button
          type="button"
          onClick={() => {
            setStatus("idle");
            setMessage("");
          }}
          className="mt-5 text-sm text-vz-teal hover:underline"
        >
          Envoyer un autre message
        </button>
      </div>
    );
  }

  const inputCls =
    "w-full rounded-lg border border-black/10 bg-vz-bg/50 px-4 py-3 text-sm text-vz-ink placeholder:text-vz-ink/40 focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal";

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="name" className="sr-only">
            Nom
          </label>
          <input
            id="name"
            name="name"
            type="text"
            autoComplete="name"
            placeholder="Votre nom"
            className={inputCls}
          />
        </div>
        <div>
          <label htmlFor="email" className="sr-only">
            E-mail
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            placeholder="Votre e-mail *"
            className={inputCls}
          />
        </div>
      </div>

      <div>
        <label htmlFor="phone" className="sr-only">
          Téléphone
        </label>
        <input
          id="phone"
          name="phone"
          type="tel"
          autoComplete="tel"
          placeholder="Téléphone (facultatif)"
          className={inputCls}
        />
      </div>

      <div>
        <label htmlFor="subject" className="sr-only">
          Sujet
        </label>
        <select
          id="subject"
          name="subject"
          defaultValue=""
          className={inputCls}
        >
          <option value="" disabled>
            Sujet de votre message
          </option>
          <option value="demande générale">Demande générale</option>
          <option value="disponibilité pièce">Disponibilité d&apos;une pièce</option>
          <option value="personal shopper">Personal Shopper</option>
          <option value="rachat vêtements">Rachat de vêtements de marque</option>
          <option value="presse / partenariat">Presse / partenariat</option>
        </select>
      </div>

      <div>
        <label htmlFor="message" className="sr-only">
          Message
        </label>
        <textarea
          id="message"
          name="message"
          rows={6}
          required
          placeholder="Votre message *"
          className={inputCls}
        />
      </div>

      <button
        type="submit"
        disabled={status === "loading"}
        className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-8 py-3 text-sm font-medium tracking-wide hover:bg-vz-teal-deep disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
      >
        {status === "loading" ? "Envoi…" : "Envoyer le message"}
      </button>
    </form>
  );
}
