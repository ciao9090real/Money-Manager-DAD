import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "Finlio — Personal Finance Manager",
  description: "Your money, finally in one place."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
