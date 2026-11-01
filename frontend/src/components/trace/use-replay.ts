"use client";

import { useEffect, useState } from "react";

/**
 * Reveals real, already-recorded pipeline events one at a time at presentation speed.
 * The events and their timestamps are genuine; only the on-screen reveal is paced so a
 * human can follow a pipeline that actually runs in milliseconds.
 */
export function useReplay(total: number, key: string | undefined, paceMs = 420) {
  const [shown, setShown] = useState(0);
  const [prevKey, setPrevKey] = useState(key);

  if (key !== prevKey) {
    setPrevKey(key);
    setShown(0);
  }

  useEffect(() => {
    if (!key || shown >= total) return;
    const t = setTimeout(() => setShown((n) => Math.min(total, n + 1)), shown === 0 ? 150 : paceMs);
    return () => clearTimeout(t);
  }, [key, shown, total, paceMs]);

  return { shown: key ? shown : total, done: !key || shown >= total, skip: () => setShown(total) };
}
