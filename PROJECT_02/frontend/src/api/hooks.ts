import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './client';
import type { Answer, ItemDetail, ItemFilters, ItemPage, Meta, SaveResult, SearchOut, Stats, Status, Tag, User } from './types';

export const keys = {
  me: ['me'] as const,
  meta: ['meta'] as const,
  stats: ['stats'] as const,
  items: (f: ItemFilters) => ['items', f] as const,
  item: (id: number) => ['item', id] as const,
  tags: ['tags'] as const,
  search: (q: string, archived: boolean) => ['search', q, archived] as const,
  history: ['ask', 'history'] as const,
};

/** Everything derived from items: lists, counts, tags, search results. */
function useRefreshLibrary() {
  const qc = useQueryClient();
  return () => Promise.all(['items', 'stats', 'tags', 'search', 'item'].map((k) => qc.invalidateQueries({ queryKey: [k] })));
}

// --- session -----------------------------------------------------------------------------

export function useMe() {
  return useQuery<User | null>({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return await api<User>('/auth/me');
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: Infinity,
  });
}

export function useAuth() {
  const qc = useQueryClient();
  // Keep the "me" query (App observes it) and drop the rest of the previous session.
  const switchUser = (user: User | null) => {
    qc.setQueryData(keys.me, user);
    qc.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' });
  };
  return {
    login: useMutation({
      mutationFn: (body: { email: string; password: string }) => api<User>('/auth/login', { method: 'POST', body }),
      onSuccess: switchUser,
    }),
    register: useMutation({
      mutationFn: (body: { email: string; password: string; name: string }) => api<User>('/auth/register', { method: 'POST', body }),
      onSuccess: switchUser,
    }),
    logout: useMutation({
      mutationFn: () => api<void>('/auth/logout', { method: 'POST' }),
      onSuccess: () => switchUser(null),
    }),
  };
}

export function useMeta() {
  return useQuery({ queryKey: keys.meta, queryFn: () => api<Meta>('/meta'), staleTime: Infinity });
}

// --- items -------------------------------------------------------------------------------

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') s.set(k, String(v));
  const out = s.toString();
  return out ? `?${out}` : '';
}

export function useStats() {
  return useQuery({ queryKey: keys.stats, queryFn: () => api<Stats>('/items/stats') });
}

export function useItems(filters: ItemFilters) {
  return useQuery({ queryKey: keys.items(filters), queryFn: () => api<ItemPage>(`/items${qs({ ...filters, limit: 200 })}`) });
}

export function useItem(id: number) {
  return useQuery({ queryKey: keys.item(id), queryFn: () => api<ItemDetail>(`/items/${id}`), enabled: Number.isFinite(id) });
}

export function useSave() {
  const refresh = useRefreshLibrary();
  return {
    url: useMutation({
      mutationFn: (body: { url: string; tags: string[] }) => api<SaveResult>('/items/url', { method: 'POST', body }),
      onSuccess: refresh,
    }),
    text: useMutation({
      mutationFn: (body: { title: string; content: string; kind: 'newsletter' | 'note'; tags: string[] }) =>
        api<SaveResult>('/items/text', { method: 'POST', body }),
      onSuccess: refresh,
    }),
    file: useMutation({
      mutationFn: (form: FormData) => api<SaveResult>('/items/upload', { method: 'POST', body: form }),
      onSuccess: refresh,
    }),
  };
}

export interface ItemPatch {
  title?: string;
  status?: Status;
  favorite?: boolean;
  tags?: string[];
  content?: string;
}

export function useItemMutations() {
  const refresh = useRefreshLibrary();
  return {
    update: useMutation({
      mutationFn: ({ id, ...body }: ItemPatch & { id: number }) => api<ItemDetail>(`/items/${id}`, { method: 'PATCH', body: { ...body } }),
      onSuccess: refresh,
    }),
    remove: useMutation({ mutationFn: (id: number) => api<void>(`/items/${id}`, { method: 'DELETE' }), onSuccess: refresh }),
    summarize: useMutation({
      mutationFn: (id: number) => api<ItemDetail>(`/items/${id}/summarize`, { method: 'POST' }),
      onSuccess: refresh,
    }),
  };
}

// --- tags, search, ask ----------------------------------------------------------------------

export function useTags() {
  return useQuery({ queryKey: keys.tags, queryFn: () => api<Tag[]>('/tags') });
}

export function useTagMutations() {
  const refresh = useRefreshLibrary();
  return {
    rename: useMutation({
      mutationFn: ({ id, name }: { id: number; name: string }) => api<Tag>(`/tags/${id}`, { method: 'PATCH', body: { name } }),
      onSuccess: refresh,
    }),
    remove: useMutation({ mutationFn: (id: number) => api<void>(`/tags/${id}`, { method: 'DELETE' }), onSuccess: refresh }),
  };
}

export function useSearch(q: string, includeArchived: boolean) {
  return useQuery({
    queryKey: keys.search(q, includeArchived),
    queryFn: () => api<SearchOut>(`/search${qs({ q, include_archived: includeArchived || undefined })}`),
    enabled: q.trim().length > 0,
  });
}

export function useAskHistory() {
  return useQuery({ queryKey: keys.history, queryFn: () => api<Answer[]>('/ask/history') });
}

export function useAsk() {
  const qc = useQueryClient();
  const refresh = () => {
    qc.invalidateQueries({ queryKey: keys.history });
    qc.invalidateQueries({ queryKey: keys.stats });
  };
  return {
    ask: useMutation({
      mutationFn: (body: { question: string; tag?: string }) => api<Answer>('/ask', { method: 'POST', body }),
      onSuccess: refresh,
    }),
    forget: useMutation({ mutationFn: (id: number) => api<void>(`/ask/${id}`, { method: 'DELETE' }), onSuccess: refresh }),
  };
}
