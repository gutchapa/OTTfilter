import React, { useState } from 'react';
import { Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
} from "@/components/ui/sheet";
import { useMovieContext } from '../../context/MovieContext';

export const FilterPanel = () => {
    const { filterOptions, filterMovies, resetFilters } = useMovieContext();
    const [isOpen, setIsOpen] = useState(false);

    const [selectedGenres, setSelectedGenres] = useState([]);
    const [selectedLanguages, setSelectedLanguages] = useState([]);
    const [selectedPlatforms, setSelectedPlatforms] = useState([]);
    const [minRating, setMinRating] = useState([0]);
    const [castSearch, setCastSearch] = useState("");

    const handleApply = () => {
        filterMovies({
            genres: selectedGenres.length > 0 ? selectedGenres : null,
            languages: selectedLanguages.length > 0 ? selectedLanguages : null,
            platforms: selectedPlatforms.length > 0 ? selectedPlatforms : null,
            min_rating: minRating[0] > 0 ? minRating[0] : null,
            cast_name: castSearch.trim() || null
        });
        setIsOpen(false);
    };

    const handleClear = () => {
        setSelectedGenres([]);
        setSelectedLanguages([]);
        setSelectedPlatforms([]);
        setMinRating([0]);
        setCastSearch("");
        resetFilters();
    };

    const toggleSelection = (item, list, setList) => {
        setList(prev => prev.includes(item) ? prev.filter(i => i !== item) : [...prev, item]);
    };

    const activeCount = selectedGenres.length + selectedLanguages.length + selectedPlatforms.length;

    return (
        <Sheet open={isOpen} onOpenChange={setIsOpen}>
            <SheetTrigger asChild>
                <Button
                    data-testid="filter-button"
                    variant="outline"
                    className="flex-1 sm:flex-none h-11 sm:h-12 px-4 sm:px-6 border-teal-300 hover:bg-teal-50 text-sm sm:text-base"
                >
                    <Filter className="w-4 h-4 sm:w-5 sm:h-5 sm:mr-2" />
                    <span className="hidden sm:inline">Filters</span>
                    {activeCount > 0 && (
                        <Badge className="ml-1 sm:ml-2 bg-teal-600 text-xs" data-testid="active-filters-badge">
                            {activeCount}
                        </Badge>
                    )}
                </Button>
            </SheetTrigger>
            <SheetContent className="w-full sm:max-w-md overflow-y-auto" data-testid="filter-sheet">
                <SheetHeader>
                    <SheetTitle className="text-2xl" style={{ fontFamily: 'Playfair Display, serif' }}>Filters</SheetTitle>
                    <SheetDescription>Refine your movie search</SheetDescription>
                </SheetHeader>

                <div className="mt-6 space-y-6">
                    {/* Genres */}
                    <div>
                        <h3 className="font-semibold mb-3 text-lg">Genres</h3>
                        <div className="flex flex-wrap gap-2">
                            {filterOptions.genres.map(genre => (
                                <Badge
                                    key={genre}
                                    variant={selectedGenres.includes(genre) ? "default" : "outline"}
                                    className={`cursor-pointer transition-all ${selectedGenres.includes(genre) ? 'bg-teal-600 hover:bg-teal-700' : 'hover:bg-teal-50'}`}
                                    onClick={() => toggleSelection(genre, selectedGenres, setSelectedGenres)}
                                >
                                    {genre}
                                </Badge>
                            ))}
                        </div>
                    </div>

                    {/* Languages */}
                    <div>
                        <h3 className="font-semibold mb-3 text-lg">Languages</h3>
                        <div className="flex flex-wrap gap-2">
                            {filterOptions.languages.map(lang => (
                                <Badge
                                    key={lang}
                                    variant={selectedLanguages.includes(lang) ? "default" : "outline"}
                                    className={`cursor-pointer transition-all ${selectedLanguages.includes(lang) ? 'bg-cyan-600 hover:bg-cyan-700' : 'hover:bg-cyan-50'}`}
                                    onClick={() => toggleSelection(lang, selectedLanguages, setSelectedLanguages)}
                                >
                                    {lang}
                                </Badge>
                            ))}
                        </div>
                    </div>

                    {/* OTT Platforms */}
                    <div>
                        <h3 className="font-semibold mb-3 text-lg">Streaming Platforms</h3>
                        <div className="space-y-2">
                            {filterOptions.platforms.map(platform => (
                                <div key={platform} className="flex items-center space-x-2">
                                    <Checkbox
                                        id={platform}
                                        checked={selectedPlatforms.includes(platform)}
                                        onCheckedChange={() => toggleSelection(platform, selectedPlatforms, setSelectedPlatforms)}
                                        className="border-teal-400 data-[state=checked]:bg-teal-600"
                                    />
                                    <label htmlFor={platform} className="text-sm font-medium cursor-pointer">
                                        {platform}
                                    </label>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Rating */}
                    <div>
                        <h3 className="font-semibold mb-3 text-lg">Minimum Rating</h3>
                        <div className="space-y-2">
                            <Slider
                                value={minRating}
                                onValueChange={setMinRating}
                                max={10}
                                step={0.5}
                                className="w-full"
                            />
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-gray-600">0</span>
                                <span className="font-semibold text-teal-600">{minRating[0]} ★</span>
                                <span className="text-gray-600">10</span>
                            </div>
                        </div>
                    </div>

                    {/* Cast Search */}
                    <div>
                        <h3 className="font-semibold mb-3 text-lg">Actor/Director Name</h3>
                        <Input
                            placeholder="e.g., Rajinikanth, Aamir Khan"
                            value={castSearch}
                            onChange={(e) => setCastSearch(e.target.value)}
                            className="border-teal-200 focus:border-teal-400"
                        />
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2 pt-4">
                        <Button
                            onClick={handleApply}
                            className="flex-1 bg-teal-600 hover:bg-teal-700 text-white"
                        >
                            Apply Filters
                        </Button>
                        <Button
                            onClick={handleClear}
                            variant="outline"
                            className="flex-1 border-teal-300 hover:bg-teal-50"
                        >
                            Clear All
                        </Button>
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    );
};
