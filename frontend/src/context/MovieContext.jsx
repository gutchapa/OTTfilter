import React, { createContext, useContext, useState, useEffect } from 'react';
import { movieService } from '../services/api';
import { toast } from 'sonner';

const MovieContext = createContext();

export const useMovieContext = () => useContext(MovieContext);

export const MovieProvider = ({ children }) => {
    const [movies, setMovies] = useState([]);
    const [loading, setLoading] = useState(false);
    const [filterOptions, setFilterOptions] = useState({
        genres: [],
        languages: [],
        platforms: []
    });
    const [youtubeResults, setYoutubeResults] = useState([]);
    const [showYoutubeDialog, setShowYoutubeDialog] = useState(false);

    // Initial Load
    useEffect(() => {
        loadInitialData();
    }, []);

    const loadInitialData = async () => {
        try {
            setLoading(true);
            setMovies([]); // Clear previous movies before loading new ones
            const [moviesData, optionsData] = await Promise.all([
                movieService.discover(1),
                movieService.getFilterOptions()
            ]);

            setMovies(moviesData.movies || []);
            setFilterOptions(optionsData);
            toast.success('Movies loaded successfully!');
        } catch (error) {
            console.error('Error loading data:', error);
            toast.error('Failed to load movies');
        } finally {
            setLoading(false);
        }
    };

    const searchMovies = async (query, useNatural = true) => {
        if (!query.trim()) {
            loadInitialData();
            return;
        }

        try {
            setLoading(true);
            setMovies([]); // Clear previous results
            if (useNatural) {
                const data = await movieService.searchNatural(query);
                setMovies(data.movies || []);

                if (data.youtube_results?.length > 0) {
                    setYoutubeResults(data.youtube_results);
                    setShowYoutubeDialog(true);
                }

                toast.success(`Found ${data.movies.length} movies`);
            } else {
                const data = await movieService.searchBasic(query);
                setMovies(data);
                toast.success(`Found ${data.length} movies`);
            }
        } catch (error) {
            console.error('Error searching:', error);
            toast.error('Search failed');
        } finally {
            setLoading(false);
        }
    };

    const filterMovies = async (filters) => {
        try {
            setLoading(true);
            setMovies([]); // Clear previous results
            const data = await movieService.filterMovies(filters);
            setMovies(data);
            toast.success(`Found ${data.length} movies`);
        } catch (error) {
            console.error('Error filtering:', error);
            toast.error('Filter failed');
        } finally {
            setLoading(false);
        }
    };

    const resetFilters = () => {
        loadInitialData();
    };

    return (
        <MovieContext.Provider value={{
            movies,
            loading,
            filterOptions,
            youtubeResults,
            showYoutubeDialog,
            setShowYoutubeDialog,
            searchMovies,
            filterMovies,
            resetFilters
        }}>
            {children}
        </MovieContext.Provider>
    );
};
