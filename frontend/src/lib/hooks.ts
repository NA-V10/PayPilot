"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export function useSystemStatus() {
  return useQuery({ queryKey: ["status"], queryFn: api.status, staleTime: 30_000, refetchInterval: 60_000 });
}

export function usePendingApprovals() {
  return useQuery({ queryKey: ["approvals", "pending"], queryFn: () => api.approvals("pending"), refetchInterval: 15_000 });
}

/** Invalidate everything that a transaction state change can affect. */
export function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "status" && q.queryKey[0] !== "scenarios" });
}

export function useApprovalActions() {
  const invalidate = useInvalidateAll();
  const approve = useMutation({ mutationFn: ({ id, note }: { id: string; note?: string }) => api.approve(id, note), onSettled: invalidate });
  const deny = useMutation({ mutationFn: ({ id, note }: { id: string; note?: string }) => api.deny(id, note), onSettled: invalidate });
  return { approve, deny };
}
