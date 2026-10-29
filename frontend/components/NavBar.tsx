"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Race Intelligence" },
  { href: "/analytics", label: "Analytics" },
  { href: "/drivers", label: "Drivers" },
  { href: "/constructors", label: "Constructors" },
  { href: "/circuits", label: "Circuits" },
  { href: "/live", label: "LIVE" },
  { href: "/predictions", label: "Predictions" },
  { href: "/coach", label: "Coach" },
  { href: "/assistant", label: "Assistant" },
  { href: "/health", label: "Data Health" },
];

export default function NavBar() {
  const pathname = usePathname();
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link href="/" className="brand">
          <span className="red">RACE</span>
          <span>LAB</span>
        </Link>
        <nav className="topnav">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={pathname === n.href ? "active" : ""}>
              {n.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
