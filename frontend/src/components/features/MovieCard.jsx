import React from 'react';
import { Star } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const OTT_COLORS = {
    'Netflix': 'bg-red-600',
    'Prime Video': 'bg-blue-600',
    'Disney+ Hotstar': 'bg-indigo-600',
    'Jio Cinema': 'bg-purple-600',
    'Zee5': 'bg-orange-600',
    'SonyLIV': 'bg-green-600',
    'Voot': 'bg-yellow-600',
    'MX Player': 'bg-cyan-600',
    'Aha': 'bg-pink-600',
    'Sun NXT': 'bg-amber-600'
};

export const MovieCard = ({ movie, onClick }) => {
    return (
        <div
            data-testid={`movie-card-${movie.id}`}
            className="group cursor-pointer transform transition-all duration-300 hover:scale-105 hover:shadow-2xl"
            onClick={() => onClick(movie)}
        >
            <div className="relative rounded-lg overflow-hidden shadow-lg bg-white">
                {/* Poster */}
                <div className="aspect-[2/3] relative overflow-hidden bg-gradient-to-br from-teal-100 to-cyan-100">
                    {movie.poster_url ? (
                        <img
                            src={movie.poster_url}
                            alt={movie.title}
                            className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                        />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400">
                            <span className="text-4xl">🎬</span>
                        </div>
                    )}

                    {/* Rating Badges */}
                    <div className="absolute top-2 right-2 flex flex-col gap-1">
                        {movie.rating > 0 && (
                            <div className="bg-teal-500 text-white px-2 py-1 rounded text-xs font-bold flex items-center gap-1 shadow-lg">
                                <Star className="w-3 h-3 fill-white" />
                                {movie.rating}
                                <span className="text-[10px] opacity-80">TMDB</span>
                            </div>
                        )}
                        {movie.imdb_rating && (
                            <div className="bg-yellow-400 text-yellow-900 px-2 py-1 rounded text-xs font-bold flex items-center gap-1 shadow-lg">
                                <Star className="w-3 h-3 fill-yellow-900" />
                                {movie.imdb_rating}
                                <span className="text-[10px]">IMDb</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Info */}
                <div className="p-3">
                    <h3 className="font-semibold text-sm line-clamp-2 mb-2 min-h-[2.5rem]" style={{ fontFamily: 'Inter, sans-serif' }}>
                        {movie.title}
                    </h3>

                    <div className="space-y-2">
                        {/* Language, Year & Certification */}
                        <div className="flex items-center gap-2 text-xs text-gray-600 flex-wrap">
                            <span className="bg-teal-100 text-teal-700 px-2 py-0.5 rounded">{movie.language}</span>
                            {movie.release_date && (
                                <span>{new Date(movie.release_date).getFullYear()}</span>
                            )}
                            {movie.certification && (
                                <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded font-semibold border border-red-300">
                                    {movie.certification}
                                </span>
                            )}
                        </div>

                        {/* OTT Platforms */}
                        <div className="flex flex-wrap gap-1">
                            {movie.ott_platforms.slice(0, 2).map((platform, idx) => (
                                <span
                                    key={idx}
                                    className={`text-[10px] text-white px-2 py-0.5 rounded ${OTT_COLORS[platform] || 'bg-gray-600'}`}
                                >
                                    {platform}
                                </span>
                            ))}
                            {movie.ott_platforms.length > 2 && (
                                <span className="text-[10px] text-gray-600 px-2 py-0.5 rounded bg-gray-100">
                                    +{movie.ott_platforms.length - 2}
                                </span>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
