export type Kind = 'article' | 'video' | 'newsletter' | 'note' | 'pdf';
export type Status = 'inbox' | 'library' | 'archived';

export interface User {
  id: number;
  email: string;
  name: string;
}

export interface Summary {
  source: 'ai' | 'extractive';
  model: string | null;
  tldr: string;
  key_points: string[];
  suggested_tags: string[];
  truncated: boolean;
  note: string | null;
  created_at: string;
}

export interface ItemCard {
  id: number;
  kind: Kind;
  status: Status;
  favorite: boolean;
  title: string;
  url: string | null;
  source_name: string;
  author: string;
  word_count: number;
  reading_minutes: number;
  has_transcript: boolean;
  thumbnail_url: string | null;
  tags: string[];
  tldr: string | null;
  created_at: string;
}

export interface ItemDetail extends ItemCard {
  description: string;
  content: string;
  published: string;
  summary: Summary | null;
  updated_at: string;
}

export interface SaveResult {
  item: ItemDetail;
  warnings: string[];
}

export interface ItemPage {
  items: ItemCard[];
  total: number;
}

export interface Stats {
  inbox: number;
  library: number;
  archived: number;
  favorites: number;
  by_kind: Partial<Record<Kind, number>>;
  tags: number;
  questions: number;
}

export interface Tag {
  id: number;
  name: string;
  count: number;
}

export interface SearchOut {
  query: string;
  mode: 'all' | 'any';
  hits: { item: ItemCard; snippet: string }[];
}

export interface Citation {
  n: number;
  item_id: number;
  title: string;
  url: string | null;
  excerpt: string;
}

export interface Answer {
  id: number;
  question: string;
  answer: string;
  source: 'ai' | 'passages';
  model: string | null;
  note: string | null;
  confidence: 'high' | 'medium' | 'low' | null;
  citations: Citation[];
  created_at: string;
}

export interface Meta {
  version: string;
  ai_enabled: boolean;
  ai_model: string | null;
}

export interface ItemFilters {
  status?: Status | 'all';
  kind?: Kind;
  tag?: string;
  favorite?: boolean;
  sort?: 'newest' | 'oldest' | 'title';
}
