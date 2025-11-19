import React, { useState } from 'react';
import { Search, Sparkles } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useMovieContext } from '../../context/MovieContext';

export const SearchBar = () => {
    const { searchMovies } = useMovieContext();
    const [query, setQuery] = useState("");
    const [useNatural, setUseNatural] = useState(true);

    const handleSearch = () => {
        searchMovies(query, useNatural);
    };

    return (
        <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1 w-full">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 sm:w-5 sm:h-5" />
                <Input
                    data-testid="search-input"
                    placeholder={useNatural ? "Try: 'tamil movies by Vijay'" : "Search movies..."}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    className="pl-9 sm:pl-10 pr-12 sm:pr-14 h-11 sm:h-12 border-teal-200 focus:border-teal-400 focus:ring-teal-400 text-sm sm:text-base w-full"
                />
                {useNatural && (
                    <div className="absolute right-2 sm:right-3 top-1/2 transform -translate-y-1/2">
                        <Badge variant="secondary" className="bg-gradient-to-r from-purple-500 to-pink-500 text-white text-[10px] sm:text-xs px-1.5 sm:px-2 py-0.5">
                            <Sparkles className="w-2.5 h-2.5 sm:w-3 sm:h-3 mr-0.5 sm:mr-1" />
                            AI
                        </Badge>
                    </div>
                )}
            </div>
            <Button
                data-testid="search-button"
                onClick={handleSearch}
                className="flex-1 sm:flex-none h-11 sm:h-12 px-4 sm:px-6 bg-teal-600 hover:bg-teal-700 text-white text-sm sm:text-base"
            >
                {useNatural ? <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 sm:mr-2" /> : <Search className="w-4 h-4 sm:w-5 sm:h-5 sm:mr-2" />}
                <span className="hidden sm:inline">Search</span>
            </Button>
        </div>
    );
};
