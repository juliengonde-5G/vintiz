import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Notre Concept | Vintiz - Mode responsable Vernon",
  description: "Decouvrez le concept Vintiz : mode premium de seconde main, selection rigoureuse, demarche eco-responsable. Boutique a Vernon.",
};

const steps = [
  {
    num: "01",
    title: "Selection rigoureuse",
    desc: "Chaque piece est examinee : qualite de la matiere, etat des coutures, absence de defauts. Seuls les articles en excellent ou tres bon etat sont retenus.",
  },
  {
    num: "02",
    title: "Nettoyage & preparation",
    desc: "Les vetements sont nettoyes, repasses et prepares avec soin avant d'etre presentes en boutique. Un etiquetage precis indique marque, taille et prix.",
  },
  {
    num: "03",
    title: "Mise en scene",
    desc: "Notre boutique est agencee comme un showroom de mode. Chaque zone est pensee pour creer une experience shopping agreable et inspirante.",
  },
  {
    num: "04",
    title: "Conseil personnalise",
    desc: "Notre equipe vous accompagne dans vos choix avec des conseils style et des suggestions adaptees a vos gouts et votre morphologie.",
  },
];

const impacts = [
  { value: "70%", label: "d'eau economisee vs neuf" },
  { value: "3x", label: "duree de vie des vetements" },
  { value: "0", label: "plastique dans nos emballages" },
  { value: "100%", label: "sacs en papier recycle" },
];

export default function ConceptPage() {
  return (
    <>
      <Navbar />

      {/* Hero */}
      <section className="pt-28 pb-16 px-6 bg-vintiz-bg">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="font-serif text-4xl sm:text-5xl text-vintiz-black mb-4">
            Notre <em className="text-vintiz-teal">Concept</em>
          </h1>
          <p className="text-lg text-vintiz-black/60 max-w-2xl mx-auto leading-relaxed">
            Chez Vintiz, nous croyons qu&apos;il est possible de s&apos;habiller avec style tout en etant responsable. Notre mission : rendre la mode de seconde main desirable.
          </p>
        </div>
      </section>

      {/* Steps */}
      <section className="py-20 px-6 bg-white">
        <div className="max-w-4xl mx-auto">
          <h2 className="font-serif text-3xl text-center text-vintiz-black mb-16">
            De la <em className="text-vintiz-teal">selection</em> a la <em className="text-vintiz-teal">vente</em>
          </h2>
          <div className="space-y-12">
            {steps.map((s) => (
              <div key={s.num} className="flex gap-6 items-start">
                <div className="shrink-0 w-14 h-14 rounded-full bg-vintiz-teal flex items-center justify-center">
                  <span className="font-serif text-lg font-bold text-white">{s.num}</span>
                </div>
                <div>
                  <h3 className="font-serif text-xl font-semibold text-vintiz-black mb-2">{s.title}</h3>
                  <p className="text-vintiz-black/60 leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Eco impact */}
      <section className="py-20 px-6 bg-vintiz-teal">
        <div className="max-w-6xl mx-auto text-center">
          <h2 className="font-serif text-3xl text-white mb-4">
            Notre impact <em>positif</em>
          </h2>
          <p className="text-white/70 mb-12 max-w-xl mx-auto">
            Acheter de la seconde main, c&apos;est un acte concret pour la planete.
          </p>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            {impacts.map((i) => (
              <div key={i.label} className="bg-white/10 rounded-2xl p-6 backdrop-blur-sm">
                <p className="font-serif text-3xl font-bold text-white mb-2">{i.value}</p>
                <p className="text-sm text-white/70">{i.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Loyalty */}
      <section className="py-20 px-6 bg-vintiz-bg">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="font-serif text-3xl text-vintiz-black mb-4">
            Programme <em className="text-vintiz-teal">Fidelite</em>
          </h2>
          <p className="text-vintiz-black/60 mb-12 max-w-2xl mx-auto leading-relaxed">
            Rejoignez le club Vintiz et profitez d&apos;avantages exclusifs : cumulez des points a chaque achat, acces aux ventes privees, offres d&apos;anniversaire.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="bg-white rounded-2xl p-6">
              <p className="font-serif text-4xl text-vintiz-teal mb-2">1&euro;</p>
              <p className="text-sm text-vintiz-black/60">= 1 point fidelite</p>
            </div>
            <div className="bg-white rounded-2xl p-6">
              <p className="font-serif text-4xl text-vintiz-teal mb-2">100 pts</p>
              <p className="text-sm text-vintiz-black/60">= 5&euro; de remise</p>
            </div>
            <div className="bg-white rounded-2xl p-6">
              <p className="font-serif text-4xl text-vintiz-teal mb-2">VIP</p>
              <p className="text-sm text-vintiz-black/60">Ventes privees exclusives</p>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
