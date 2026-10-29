import type { Metadata } from "next";
import NavBar from "@/components/NavBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "RACELAB F1 Analytics",
  description:
    "Motorsport performance analytics and AI driver coach: historical analytics, live timing, predictions, coaching and an LLM race assistant.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <NavBar />
        <main className="container">{children}</main>
        <div className="container">
          <footer className="footer">
            RACELAB - Next.js front end + Flask API over the f1_analytics core. Start the API with `python backend/run.py`.
          </footer>
        </div>
      </body>
    </html>
  );
}
