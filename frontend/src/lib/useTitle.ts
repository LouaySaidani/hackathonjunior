import { useEffect } from "react";

/** Each route sets a distinct document title (announced by screen readers on navigation). */
export function useTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · Wasf`;
  }, [title]);
}
