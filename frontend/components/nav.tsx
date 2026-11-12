"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, FileText, Home, ScrollText, WalletCards } from "lucide-react";

export const NAV = [
  { href: "", label: "Home", short: "Home", Icon: Home },
  { href: "/rules", label: "Rules", short: "Rules", Icon: ScrollText },
  { href: "/money", label: "Money & Time", short: "Money", Icon: WalletCards },
  { href: "/calendar", label: "Calendar", short: "Calendar", Icon: CalendarDays },
  { href: "/record", label: "Record", short: "Record", Icon: FileText },
];

function active(path: string, base: string, href: string) {
  const target = base + href;
  if (!href) return path === base || path.startsWith(base + "/expenses");
  if (href === "/rules") return path.startsWith(target) || path.startsWith(base + "/agreement") || path.startsWith(base + "/source");
  return path.startsWith(target);
}

export function SideNav({ fid }: { fid: string }) {
  const path = usePathname();
  const base = `/f/${fid}`;
  return (
    <ul className="m-0 grid list-none gap-0.5 p-0">
      {NAV.map(({ href, label, Icon }) => {
        const on = active(path, base, href);
        return (
          <li key={label}>
            <Link
              href={base + href}
              aria-current={on ? "page" : undefined}
              className={`flex min-h-11 items-center gap-3 rounded-[10px] px-3 font-medium no-underline transition-colors ${on ? "bg-act-wash text-act" : "text-ink-2 hover:bg-sunk hover:text-ink"}`}
            >
              <Icon size={18} aria-hidden strokeWidth={on ? 2.3 : 1.9} /> {label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function TabBar({ fid }: { fid: string }) {
  const path = usePathname();
  const base = `/f/${fid}`;
  return (
    <nav aria-label="Family" className="no-print fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
      <ul className="m-0 grid list-none grid-cols-5 p-0">
        {NAV.map(({ href, short, Icon }) => {
          const on = active(path, base, href);
          return (
            <li key={short}>
              <Link href={base + href} aria-current={on ? "page" : undefined}
                className={`flex min-h-14 flex-col items-center justify-center gap-0.5 text-[0.72rem] font-semibold no-underline ${on ? "text-act" : "text-ink-2"}`}>
                <Icon size={20} aria-hidden strokeWidth={on ? 2.3 : 1.8} />
                {short}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
