import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8082";
const API_URL = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const movieService = {
  discover: async (page = 1) => {
    const response = await api.get(`/discover?page=${page}`);
    return response.data;
  },

  getFilterOptions: async () => {
    // Updated endpoint to match backend router
    const response = await api.get("/options/all");
    return response.data;
  },

  searchNatural: async (query) => {
    // Updated endpoint to match backend router
    const response = await api.post("/natural", { query });
    return response.data;
  },

  searchBasic: async (query) => {
    const response = await api.get(`/basic?q=${encodeURIComponent(query)}`);
    return response.data;
  },

  filterMovies: async (filters) => {
    const response = await api.post("/filter", filters);
    return response.data;
  },

  getMovie: async (id) => {
    const response = await api.get(`/${id}`);
    return response.data;
  }
};

export default api;
