import type { MouseEvent, ReactNode } from "react";

import { openExternal } from "../lib/openExternal";

export function ExternalLink({
  href,
  className,
  children,
}: {
  href: string;
  className?: string;
  children: ReactNode;
}) {
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    openExternal(href);
  };

  return (
    <a href={href} className={className} target="_blank" rel="noreferrer" onClick={onClick}>
      {children}
    </a>
  );
}
