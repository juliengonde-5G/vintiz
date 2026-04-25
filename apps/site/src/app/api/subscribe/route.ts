import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, consent, source } = body ?? {};

    if (!email || typeof email !== "string") {
      return NextResponse.json(
        { error: "L'adresse email est requise." },
        { status: 400 }
      );
    }
    if (consent !== true) {
      return NextResponse.json(
        { error: "Le consentement est obligatoire." },
        { status: 400 }
      );
    }

    const forwarded = request.headers.get("x-forwarded-for");

    const upstream = await fetch(`${API_URL}/api/newsletter/subscribe`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(forwarded ? { "x-forwarded-for": forwarded } : {}),
      },
      body: JSON.stringify({ email, consent: true, source: source ?? "site_landing" }),
    });

    const data = await upstream.json().catch(() => ({}));

    if (!upstream.ok) {
      const detail =
        typeof data?.detail === "string"
          ? data.detail
          : "L'inscription a échoué. Veuillez réessayer.";
      return NextResponse.json({ error: detail }, { status: upstream.status });
    }

    return NextResponse.json(
      { message: data.message ?? "Inscription enregistrée." },
      { status: 201 }
    );
  } catch {
    return NextResponse.json(
      { error: "Une erreur est survenue. Veuillez réessayer." },
      { status: 500 }
    );
  }
}
