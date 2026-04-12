"use client";

import { useState, FormEvent } from "react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

export default function ContactPage() {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [sent, setSent] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    // In production, this would send an email or save to database
    setSent(true);
  };

  return (
    <>
      <Navbar />

      <section className="pt-28 pb-16 px-6 bg-vintiz-bg">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="font-serif text-4xl sm:text-5xl text-vintiz-black mb-4">
            <em className="text-vintiz-teal">Contact</em>
          </h1>
          <p className="text-lg text-vintiz-black/60 max-w-2xl mx-auto">
            Une question ? Envie de deposer des vetements ? Contactez-nous.
          </p>
        </div>
      </section>

      <section className="py-16 px-6 bg-white">
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12">
          {/* Contact Info */}
          <div>
            <h2 className="font-serif text-2xl text-vintiz-black mb-8">Nos coordonnees</h2>
            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-full bg-vintiz-pink/20 flex items-center justify-center shrink-0">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                    <circle cx="12" cy="10" r="3" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-medium text-vintiz-black">Adresse</h3>
                  <p className="text-vintiz-black/60">6 rue Saint-Jacques</p>
                  <p className="text-vintiz-black/60">27200 Vernon</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-full bg-vintiz-pink/20 flex items-center justify-center shrink-0">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-medium text-vintiz-black">Horaires</h3>
                  <p className="text-vintiz-black/60">Mardi - Samedi : 10h - 19h</p>
                  <p className="text-vintiz-black/60">Dimanche &amp; Lundi : Ferme</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-full bg-vintiz-pink/20 flex items-center justify-center shrink-0">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2">
                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-medium text-vintiz-black">Reseaux sociaux</h3>
                  <div className="flex gap-3 mt-2">
                    <a href="#" className="text-vintiz-black/40 hover:text-vintiz-teal transition-colors">Instagram</a>
                    <a href="#" className="text-vintiz-black/40 hover:text-vintiz-teal transition-colors">Facebook</a>
                    <a href="#" className="text-vintiz-black/40 hover:text-vintiz-teal transition-colors">TikTok</a>
                  </div>
                </div>
              </div>
            </div>

            {/* Map */}
            <div className="mt-8 rounded-2xl overflow-hidden h-48 bg-vintiz-pink/10">
              <iframe
                src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d2608.5!2d1.4773!3d49.0926!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x47e6b6c0d0d0d0d%3A0x0!2s6+Rue+Saint-Jacques%2C+27200+Vernon!5e0!3m2!1sfr!2sfr!4v1"
                width="100%"
                height="100%"
                style={{ border: 0 }}
                allowFullScreen
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                title="Vintiz Vernon"
              />
            </div>
          </div>

          {/* Contact Form */}
          <div>
            <h2 className="font-serif text-2xl text-vintiz-black mb-8">Ecrivez-nous</h2>
            {sent ? (
              <div className="bg-vintiz-teal/10 border border-vintiz-teal/30 rounded-2xl p-8 text-center">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" className="mx-auto mb-4">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <h3 className="font-serif text-xl text-vintiz-black mb-2">Message envoye !</h3>
                <p className="text-vintiz-black/60">Nous vous repondrons dans les plus brefs delais.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-vintiz-black mb-1.5">Nom</label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full px-4 py-3 rounded-lg border border-vintiz-pink/40 bg-white text-vintiz-black focus:outline-none focus:ring-2 focus:ring-vintiz-teal/40 focus:border-vintiz-teal"
                    placeholder="Votre nom"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-vintiz-black mb-1.5">Email</label>
                  <input
                    type="email"
                    required
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full px-4 py-3 rounded-lg border border-vintiz-pink/40 bg-white text-vintiz-black focus:outline-none focus:ring-2 focus:ring-vintiz-teal/40 focus:border-vintiz-teal"
                    placeholder="votre@email.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-vintiz-black mb-1.5">Message</label>
                  <textarea
                    required
                    rows={5}
                    value={form.message}
                    onChange={(e) => setForm({ ...form, message: e.target.value })}
                    className="w-full px-4 py-3 rounded-lg border border-vintiz-pink/40 bg-white text-vintiz-black focus:outline-none focus:ring-2 focus:ring-vintiz-teal/40 focus:border-vintiz-teal resize-none"
                    placeholder="Votre message..."
                  />
                </div>
                <button
                  type="submit"
                  className="w-full px-6 py-3 bg-vintiz-teal text-white font-medium rounded-lg hover:bg-vintiz-teal/90 transition-colors"
                >
                  Envoyer
                </button>
              </form>
            )}
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
