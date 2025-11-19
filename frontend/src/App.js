import React, { useState } from "react";
import "@/App.css";
import { Badge } from "@/components/ui/badge";
import { MovieProvider, useMovieContext } from "./context/MovieContext";
import { MovieCard } from "./components/features/MovieCard";
import { SearchBar } from "./components/features/SearchBar";
import { FilterPanel } from "./components/features/FilterPanel";
import { MovieDialog } from "./components/features/MovieDialog";
import { Youtube } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

const MainContent = () => {
  const { movies, loading, resetFilters, youtubeResults, showYoutubeDialog, setShowYoutubeDialog } = useMovieContext();
  const [selectedMovie, setSelectedMovie] = useState(null);

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 via-blue-50 to-cyan-50">
      {/* Header */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-white/80 border-b border-teal-200/50 shadow-sm">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-8 py-3 sm:py-4">
          <div className="flex items-center justify-between mb-3 sm:mb-4">
            <h1 className="text-2xl sm:text-4xl lg:text-5xl font-bold bg-gradient-to-r from-teal-600 to-cyan-600 bg-clip-text text-transparent" style={{ fontFamily: 'Playfair Display, serif' }}>
              StreamFilter
            </h1>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-teal-700 border-teal-300 text-xs sm:text-sm" data-testid="movie-count-badge">
                {movies.length} Movies
              </Badge>
            </div>
          </div>

          {/* Search & Filter */}
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="flex-1">
              <SearchBar />
            </div>
            <FilterPanel />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-8 py-4 sm:py-6 lg:py-8">
        {loading ? (
          <div className="flex items-center justify-center h-64" data-testid="loading-indicator">
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600"></div>
              <p className="mt-4 text-gray-600">Loading movies...</p>
            </div>
          </div>
        ) : movies.length === 0 ? (
          <div className="text-center py-16" data-testid="no-results">
            <div className="text-6xl mb-4">🎬</div>
            <h2 className="text-2xl font-semibold mb-2" style={{ fontFamily: 'Playfair Display, serif' }}>No movies found</h2>
            <p className="text-gray-600 mb-4">Try adjusting your filters or search query</p>
            <button onClick={resetFilters} className="bg-teal-600 hover:bg-teal-700 text-white px-4 py-2 rounded">
              Reset Filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 sm:gap-4 md:gap-6" data-testid="movies-grid">
            {movies.map((movie) => (
              <MovieCard key={movie.id} movie={movie} onClick={setSelectedMovie} />
            ))}
          </div>
        )}
      </main>

      {/* Dialogs */}
      <MovieDialog movie={selectedMovie} onClose={() => setSelectedMovie(null)} />

      {/* YouTube Results Dialog */}
      <Dialog open={showYoutubeDialog} onOpenChange={setShowYoutubeDialog}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="youtube-dialog">
          <DialogHeader>
            <DialogTitle className="text-3xl flex items-center gap-2" style={{ fontFamily: 'Playfair Display, serif' }}>
              <Youtube className="w-8 h-8 text-red-600" />
              Related Videos
            </DialogTitle>
            <DialogDescription>
              Trailers, songs, and scenes from YouTube
            </DialogDescription>
          </DialogHeader>

          <div className="mt-6 space-y-4">
            {youtubeResults.map((video, idx) => (
              <a
                key={idx}
                href={video.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex gap-4 p-4 rounded-lg border border-gray-200 hover:border-teal-400 hover:shadow-lg transition-all group"
              >
                <img
                  src={video.thumbnail_url}
                  alt={video.title}
                  className="w-40 h-24 object-cover rounded-lg"
                />
                <div className="flex-1">
                  <h3 className="font-semibold text-lg group-hover:text-teal-600 transition-colors line-clamp-2">
                    {video.title}
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">{video.channel_title}</p>
                  <Badge variant="outline" className="mt-2 border-red-300 text-red-700">
                    <Youtube className="w-3 h-3 mr-1" />
                    Watch on YouTube
                  </Badge>
                </div>
              </a>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

function App() {
  return (
    <MovieProvider>
      <MainContent />
    </MovieProvider>
  );
}

export default App;
