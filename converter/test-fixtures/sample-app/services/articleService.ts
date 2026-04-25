import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL;

export interface Article {
  id: string;
  title: string;
  body: string;
  author: {
    id: string;
    name: string;
    avatar_url: string;
  };
  tags: string[];
  published_at: string;
  updated_at: string;
  view_count: number;
  is_featured: boolean;
}

export interface CreateArticleInput {
  title: string;
  body: string;
  tags: string[];
}

export type ArticleSortBy = "recent" | "popular" | "featured";

export const articleService = {
  async getAll(sortBy: ArticleSortBy = "recent", page = 1): Promise<Article[]> {
    const { data } = await axios.get(`${API_BASE}/articles`, {
      params: { sort: sortBy, page, limit: 20 },
    });
    return data.articles;
  },

  async getById(id: string): Promise<Article> {
    const { data } = await axios.get(`${API_BASE}/articles/${id}`);
    return data;
  },

  async create(input: CreateArticleInput, token: string): Promise<Article> {
    const { data } = await axios.post(`${API_BASE}/articles`, input, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return data;
  },

  async update(id: string, input: Partial<CreateArticleInput>, token: string): Promise<Article> {
    const { data } = await axios.put(`${API_BASE}/articles/${id}`, input, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return data;
  },

  async delete(id: string, token: string): Promise<void> {
    await axios.delete(`${API_BASE}/articles/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  },

  async search(query: string): Promise<Article[]> {
    const { data } = await axios.get(`${API_BASE}/articles/search`, {
      params: { q: query },
    });
    return data.articles;
  },
};
