import type { Metadata, Viewport } from "next";
import { connection } from "next/server";
import { Anek_Latin, Source_Serif_4 } from "next/font/google";
import { ScreenSlot } from "@/components/backend-form";
import "./globals.css";

const anek = Anek_Latin({ subsets: ["latin"], axes: ["wdth"], variable: "--font-anek", display: "swap" });
const serif = Source_Serif_4({ subsets: ["latin"], axes: ["opsz"], style: ["normal", "italic"], variable: "--font-source-serif", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Between · shared child expenses, by the agreement", template: "%s · Between" },
  description: "Between turns a co-parenting agreement into rules both parents approve, decides each shared expense by those rules, and settles it through a PayPal checkout that Between verifies.",
  icons: { icon: "/icon.svg" },
};
export const viewport: Viewport = {
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#f3f5f7" }, { media: "(prefers-color-scheme: dark)", color: "#0e1216" }],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  await connection(); // every page carries a per-request CSP nonce
  return (
    <html lang="en" className={`${anek.variable} ${serif.variable}`}>
      <body>
        <ScreenSlot>{children}</ScreenSlot>
      </body>
    </html>
  );
}
