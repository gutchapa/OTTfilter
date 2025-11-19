import React, { useState } from 'react';
import { Star, Clock, AlertCircle, Info, Youtube } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

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

export const MovieDialog = ({ movie, onClose }) => {
    const [showContentWarnings, setShowContentWarnings] = useState(false);

    if (!movie) return null;

    return (
        <>
            <Dialog open={!!movie} onOpenChange={(open) => !open && onClose()}>
                <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="movie-detail-dialog">
                    <DialogHeader>
                        <DialogTitle className="text-3xl" style={{ fontFamily: 'Playfair Display, serif' }}>
                            {movie.title}
                        </DialogTitle>
                        {movie.original_title !== movie.title && (
                            <DialogDescription className="text-lg">
                                {movie.original_title}
                            </DialogDescription>
                        )}
                    </DialogHeader>

                    <div className="mt-6 space-y-6">
                        {/* Backdrop */}
                        {movie.backdrop_url && (
                            <div className="w-full rounded-lg overflow-hidden">
                                <img
                                    src={movie.backdrop_url}
                                    alt={movie.title}
                                    className="w-full h-64 object-cover"
                                />
                            </div>
                        )}

                        <div className="grid md:grid-cols-3 gap-6">
                            {/* Poster */}
                            <div>
                                {movie.poster_url && (
                                    <img
                                        src={movie.poster_url}
                                        alt={movie.title}
                                        className="w-full rounded-lg shadow-lg"
                                    />
                                )}
                            </div>

                            {/* Details */}
                            <div className="md:col-span-2 space-y-4">
                                {/* Rating & Runtime */}
                                <div className="flex items-center gap-4 flex-wrap">
                                    {movie.rating > 0 && (
                                        <div className="flex items-center gap-2 bg-teal-100 text-teal-900 px-3 py-2 rounded-lg">
                                            <Star className="w-5 h-5 fill-teal-900" />
                                            <div className="flex flex-col">
                                                <span className="font-bold text-lg">{movie.rating} / 10</span>
                                                <span className="text-xs opacity-75">TMDB</span>
                                            </div>
                                        </div>
                                    )}
                                    {movie.imdb_rating && (
                                        <div className="flex items-center gap-2 bg-yellow-100 text-yellow-900 px-3 py-2 rounded-lg">
                                            <Star className="w-5 h-5 fill-yellow-900" />
                                            <div className="flex flex-col">
                                                <span className="font-bold text-lg">{movie.imdb_rating} / 10</span>
                                                <span className="text-xs opacity-75">IMDb</span>
                                            </div>
                                        </div>
                                    )}
                                    {movie.runtime && (
                                        <div className="flex items-center gap-2 text-gray-600">
                                            <Clock className="w-5 h-5" />
                                            <span>{movie.runtime} min</span>
                                        </div>
                                    )}
                                </div>

                                {/* Synopsis */}
                                <div>
                                    <h3 className="font-semibold text-lg mb-2">Synopsis</h3>
                                    <p className="text-gray-700 leading-relaxed">{movie.synopsis}</p>
                                </div>

                                {/* Genres */}
                                {movie.genres.length > 0 && (
                                    <div>
                                        <h3 className="font-semibold text-lg mb-2">Genres</h3>
                                        <div className="flex flex-wrap gap-2">
                                            {movie.genres.map((genre, idx) => (
                                                <Badge key={idx} variant="outline" className="border-teal-300 text-teal-700">
                                                    {genre}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Cast */}
                                {movie.cast.length > 0 && (
                                    <div>
                                        <h3 className="font-semibold text-lg mb-2">Cast</h3>
                                        <p className="text-gray-700">{movie.cast.join(', ')}</p>
                                    </div>
                                )}

                                {/* Director */}
                                {movie.director && (
                                    <div>
                                        <h3 className="font-semibold text-lg mb-2">Director</h3>
                                        <p className="text-gray-700">{movie.director}</p>
                                    </div>
                                )}

                                {/* Language & Release Date */}
                                <div className="flex gap-6 flex-wrap">
                                    <div>
                                        <h3 className="font-semibold mb-1">Language</h3>
                                        <p className="text-gray-700">{movie.language}</p>
                                    </div>
                                    {movie.release_date && (
                                        <div>
                                            <h3 className="font-semibold mb-1">Release Date</h3>
                                            <p className="text-gray-700">{new Date(movie.release_date).toLocaleDateString()}</p>
                                        </div>
                                    )}
                                    {movie.certification && (
                                        <div>
                                            <h3 className="font-semibold mb-1">Content Rating</h3>
                                            <div className="flex items-center gap-3">
                                                <span className="bg-red-100 text-red-700 px-3 py-1 rounded font-bold border-2 border-red-300">
                                                    {movie.certification}
                                                </span>
                                                <span className="text-xs text-gray-600">
                                                    {movie.certification === 'U' && 'Universal - Suitable for all'}
                                                    {movie.certification === 'U/A' && 'Parental Guidance - Under 12 needs adult'}
                                                    {movie.certification === 'A' && 'Adults Only - 18+'}
                                                    {movie.certification === 'PG' && 'Parental Guidance Suggested'}
                                                    {movie.certification === 'PG-13' && 'Parents Strongly Cautioned - 13+'}
                                                    {movie.certification === 'R' && 'Restricted - 17+ or with parent'}
                                                </span>
                                                {movie.content_warnings && movie.content_warnings.length > 0 && (
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => setShowContentWarnings(true)}
                                                        className="text-red-700 border-red-300 hover:bg-red-50"
                                                    >
                                                        <Info className="w-4 h-4 mr-1" />
                                                        Why {movie.certification}?
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Streaming Platforms */}
                                <div>
                                    <h3 className="font-semibold text-lg mb-3">Available On</h3>
                                    <div className="flex flex-wrap gap-3">
                                        {movie.ott_platforms.map((platform, idx) => (
                                            <div
                                                key={idx}
                                                className={`${OTT_COLORS[platform] || 'bg-gray-600'} text-white px-4 py-2 rounded-lg font-semibold shadow-lg`}
                                            >
                                                {platform}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            {/* Content Warnings Dialog */}
            <Dialog open={showContentWarnings} onOpenChange={setShowContentWarnings}>
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle className="text-2xl flex items-center gap-2" style={{ fontFamily: 'Playfair Display, serif' }}>
                            <AlertCircle className="w-7 h-7 text-red-600" />
                            Content Details: {movie.title}
                        </DialogTitle>
                        <DialogDescription>
                            Why this movie is rated {movie.certification}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="mt-6 space-y-4">
                        {movie.content_warnings && movie.content_warnings.length > 0 ? (
                            <>
                                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded">
                                    <p className="text-sm text-red-800 font-semibold mb-2">
                                        This movie contains the following content:
                                    </p>
                                </div>

                                <ul className="space-y-3">
                                    {movie.content_warnings.map((warning, idx) => (
                                        <li key={idx} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                                            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                                            <span className="text-gray-800">{warning}</span>
                                        </li>
                                    ))}
                                </ul>
                            </>
                        ) : (
                            <div className="text-center py-8 text-gray-500">
                                <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                <p>No detailed content warnings available.</p>
                            </div>
                        )}
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
};
