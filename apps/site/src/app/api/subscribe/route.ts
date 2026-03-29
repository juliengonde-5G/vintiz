import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const SUBSCRIBERS_PATH = path.join(
  process.cwd(),
  "..",
  "..",
  "data",
  "subscribers.json"
);

function isValidEmail(email: string): boolean {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

function readSubscribers(): string[] {
  try {
    if (fs.existsSync(SUBSCRIBERS_PATH)) {
      const data = fs.readFileSync(SUBSCRIBERS_PATH, "utf-8");
      return JSON.parse(data);
    }
  } catch {
    // If file is corrupted, start fresh
  }
  return [];
}

function writeSubscribers(subscribers: string[]): void {
  const dir = path.dirname(SUBSCRIBERS_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(SUBSCRIBERS_PATH, JSON.stringify(subscribers, null, 2));
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email } = body;

    if (!email || typeof email !== "string") {
      return NextResponse.json(
        { error: "L'adresse email est requise." },
        { status: 400 }
      );
    }

    const trimmedEmail = email.trim().toLowerCase();

    if (!isValidEmail(trimmedEmail)) {
      return NextResponse.json(
        { error: "L'adresse email n'est pas valide." },
        { status: 400 }
      );
    }

    const subscribers = readSubscribers();

    if (subscribers.includes(trimmedEmail)) {
      return NextResponse.json(
        { message: "Vous êtes déjà inscrit(e) ! Nous vous tiendrons informé(e)." },
        { status: 200 }
      );
    }

    subscribers.push(trimmedEmail);
    writeSubscribers(subscribers);

    return NextResponse.json(
      { message: "Merci pour votre inscription ! Nous vous tiendrons informé(e) de l'ouverture." },
      { status: 201 }
    );
  } catch {
    return NextResponse.json(
      { error: "Une erreur est survenue. Veuillez réessayer." },
      { status: 500 }
    );
  }
}
