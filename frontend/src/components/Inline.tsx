// Inline text renderer shared by the incident panel and the reports: **bold** and `code` only, and journey ids
// shown by name ("journey:checkout" -> "checkout"). No HTML is ever injected.
import { Fragment, ReactNode } from "react";

export const plain = (text: string) => text.replace(/journey:/g, "");

export function inline(text: string): ReactNode[] {
  return plain(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean).map((part, i) => {
    if (part.startsWith("**")) return <strong key={i} className="text-pine">{part.slice(2, -2)}</strong>;
    if (part.startsWith("`")) return <code key={i} className="rounded-md bg-saffron/15 px-1.5 font-medium text-pine">{part.slice(1, -1)}</code>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}
