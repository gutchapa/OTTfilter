import { useState, useEffect } from "react";
import "@/App.css";
import axios from "axios";
import { Search, Filter, Star, Clock, X, Sparkles, Youtube } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// OTT Platform color mapping
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

function App() {
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedMovie, setSelectedMovie] = useState(null);
  const [filterOptions, setFilterOptions] = useState({
    genres: [],
    languages: [],
    platforms: []
  });
  
  // Filter states
  const [selectedGenres, setSelectedGenres] = useState([]);
  const [selectedLanguages, setSelectedLanguages] = useState([]);
  const [selectedPlatforms, setSelectedPlatforms] = useState([]);
  const [minRating, setMinRating] = useState([0]);
  const [castSearch, setCastSearch] = useState("");
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      
      // Fetch initial movies
      const moviesRes = await axios.get(`${API}/discover?page=1`);
      setMovies(moviesRes.data.movies || []);
      
      // Fetch filter options
      const optionsRes = await axios.get(`${API}/filter-options`);
      setFilterOptions(optionsRes.data);
      
      toast.success('Movies loaded successfully!');
    } catch (error) {
      console.error('Error loading data:', error);
      toast.error('Failed to load movies');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadInitialData();
      return;
    }
    
    try {
      setLoading(true);
      const res = await axios.get(`${API}/search?q=${encodeURIComponent(searchQuery)}`);
      setMovies(res.data);
    } catch (error) {
      console.error('Error searching:', error);
      toast.error('Search failed');
    } finally {
      setLoading(false);
    }
  };

  const handleFilter = async () => {
    try {
      setLoading(true);
      const filterData = {
        genres: selectedGenres.length > 0 ? selectedGenres : null,
        languages: selectedLanguages.length > 0 ? selectedLanguages : null,
        platforms: selectedPlatforms.length > 0 ? selectedPlatforms : null,
        min_rating: minRating[0] > 0 ? minRating[0] : null,
        cast_name: castSearch.trim() || null
      };
      
      const res = await axios.post(`${API}/movies/filter`, filterData);
      setMovies(res.data);
      setIsFilterOpen(false);
      toast.success(`Found ${res.data.length} movies`);
    } catch (error) {
      console.error('Error filtering:', error);
      toast.error('Filter failed');
    } finally {
      setLoading(false);
    }
  };

  const clearFilters = () => {
    setSelectedGenres([]);
    setSelectedLanguages([]);
    setSelectedPlatforms([]);
    setMinRating([0]);
    setCastSearch("");
    setSearchQuery("");
    loadInitialData();
  };

  const toggleGenre = (genre) => {
    setSelectedGenres(prev => 
      prev.includes(genre) ? prev.filter(g => g !== genre) : [...prev, genre]
    );
  };

  const toggleLanguage = (lang) => {
    setSelectedLanguages(prev => 
      prev.includes(lang) ? prev.filter(l => l !== lang) : [...prev, lang]
    );
  };

  const togglePlatform = (platform) => {
    setSelectedPlatforms(prev => 
      prev.includes(platform) ? prev.filter(p => p !== platform) : [...prev, platform]
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 via-blue-50 to-cyan-50">
      {/* Header */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-white/80 border-b border-teal-200/50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-4xl sm:text-5xl font-bold bg-gradient-to-r from-teal-600 to-cyan-600 bg-clip-text text-transparent" style={{fontFamily: 'Playfair Display, serif'}}>
              StreamFilter
            </h1>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-teal-700 border-teal-300" data-testid="movie-count-badge">
                {movies.length} Movies
              </Badge>
            </div>
          </div>
          
          {/* Search Bar */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <Input
                data-testid="search-input"
                placeholder="Search by movie name, actor, or director..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="pl-10 h-12 border-teal-200 focus:border-teal-400 focus:ring-teal-400"
              />
            </div>
            <Button 
              data-testid="search-button"
              onClick={handleSearch} 
              className="h-12 px-6 bg-teal-600 hover:bg-teal-700 text-white"
            >
              Search
            </Button>
            
            {/* Filter Sheet */}
            <Sheet open={isFilterOpen} onOpenChange={setIsFilterOpen}>
              <SheetTrigger asChild>
                <Button 
                  data-testid="filter-button"
                  variant="outline" 
                  className="h-12 px-6 border-teal-300 hover:bg-teal-50"
                >
                  <Filter className="w-5 h-5 mr-2" />
                  Filters
                  {(selectedGenres.length + selectedLanguages.length + selectedPlatforms.length) > 0 && (
                    <Badge className="ml-2 bg-teal-600" data-testid="active-filters-badge">
                      {selectedGenres.length + selectedLanguages.length + selectedPlatforms.length}
                    </Badge>
                  )}
                </Button>
              </SheetTrigger>
              <SheetContent className="w-full sm:max-w-md overflow-y-auto" data-testid="filter-sheet">
                <SheetHeader>
                  <SheetTitle className="text-2xl" style={{fontFamily: 'Playfair Display, serif'}}>Filters</SheetTitle>
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
                          data-testid={`genre-${genre.toLowerCase()}`}
                          variant={selectedGenres.includes(genre) ? "default" : "outline"}
                          className={`cursor-pointer transition-all ${selectedGenres.includes(genre) ? 'bg-teal-600 hover:bg-teal-700' : 'hover:bg-teal-50'}`}
                          onClick={() => toggleGenre(genre)}
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
                          data-testid={`language-${lang.toLowerCase()}`}
                          variant={selectedLanguages.includes(lang) ? "default" : "outline"}
                          className={`cursor-pointer transition-all ${selectedLanguages.includes(lang) ? 'bg-cyan-600 hover:bg-cyan-700' : 'hover:bg-cyan-50'}`}
                          onClick={() => toggleLanguage(lang)}
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
                            data-testid={`platform-${platform.toLowerCase().replace(/\s+/g, '-')}`}
                            id={platform}
                            checked={selectedPlatforms.includes(platform)}
                            onCheckedChange={() => togglePlatform(platform)}
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
                        data-testid="rating-slider"
                        value={minRating}
                        onValueChange={setMinRating}
                        max={10}
                        step={0.5}
                        className="w-full"
                      />
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600">0</span>
                        <span className="font-semibold text-teal-600" data-testid="rating-value">{minRating[0]} ★</span>
                        <span className="text-gray-600">10</span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Cast Search */}
                  <div>
                    <h3 className="font-semibold mb-3 text-lg">Actor/Director Name</h3>
                    <Input
                      data-testid="cast-search-input"
                      placeholder="e.g., Rajinikanth, Aamir Khan"
                      value={castSearch}
                      onChange={(e) => setCastSearch(e.target.value)}
                      className="border-teal-200 focus:border-teal-400"
                    />
                  </div>
                  
                  {/* Action Buttons */}
                  <div className="flex gap-2 pt-4">
                    <Button 
                      data-testid="apply-filters-button"
                      onClick={handleFilter} 
                      className="flex-1 bg-teal-600 hover:bg-teal-700 text-white"
                    >
                      Apply Filters
                    </Button>
                    <Button 
                      data-testid="clear-filters-button"
                      onClick={clearFilters} 
                      variant="outline"
                      className="flex-1 border-teal-300 hover:bg-teal-50"
                    >
                      Clear All
                    </Button>
                  </div>
                </div>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
            <h2 className="text-2xl font-semibold mb-2" style={{fontFamily: 'Playfair Display, serif'}}>No movies found</h2>
            <p className="text-gray-600 mb-4">Try adjusting your filters or search query</p>
            <Button onClick={clearFilters} className="bg-teal-600 hover:bg-teal-700" data-testid="reset-button">
              Reset Filters
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-6" data-testid="movies-grid">
            {movies.map((movie) => (
              <div
                key={movie.id}
                data-testid={`movie-card-${movie.id}`}
                className="group cursor-pointer transform transition-all duration-300 hover:scale-105 hover:shadow-2xl"
                onClick={() => setSelectedMovie(movie)}
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
                    
                    {/* Rating Badge */}
                    {movie.rating > 0 && (
                      <div className="absolute top-2 right-2 bg-yellow-400 text-yellow-900 px-2 py-1 rounded-full text-xs font-bold flex items-center gap-1 shadow-lg">
                        <Star className="w-3 h-3 fill-yellow-900" />
                        {movie.rating}
                      </div>
                    )}
                  </div>
                  
                  {/* Info */}
                  <div className="p-3">
                    <h3 className="font-semibold text-sm line-clamp-2 mb-2 min-h-[2.5rem]" style={{fontFamily: 'Inter, sans-serif'}}>
                      {movie.title}
                    </h3>
                    
                    <div className="space-y-2">
                      {/* Language & Year */}
                      <div className="flex items-center gap-2 text-xs text-gray-600">
                        <span className="bg-teal-100 text-teal-700 px-2 py-0.5 rounded">{movie.language}</span>
                        {movie.release_date && (
                          <span>{new Date(movie.release_date).getFullYear()}</span>
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
            ))}
          </div>
        )}
      </main>

      {/* Movie Detail Dialog */}
      <Dialog open={!!selectedMovie} onOpenChange={(open) => !open && setSelectedMovie(null)}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="movie-detail-dialog">
          {selectedMovie && (
            <div>
              <DialogHeader>
                <DialogTitle className="text-3xl" style={{fontFamily: 'Playfair Display, serif'}}>
                  {selectedMovie.title}
                </DialogTitle>
                {selectedMovie.original_title !== selectedMovie.title && (
                  <DialogDescription className="text-lg">
                    {selectedMovie.original_title}
                  </DialogDescription>
                )}
              </DialogHeader>
              
              <div className="mt-6 space-y-6">
                {/* Backdrop */}
                {selectedMovie.backdrop_url && (
                  <div className="w-full rounded-lg overflow-hidden">
                    <img
                      src={selectedMovie.backdrop_url}
                      alt={selectedMovie.title}
                      className="w-full h-64 object-cover"
                    />
                  </div>
                )}
                
                <div className="grid md:grid-cols-3 gap-6">
                  {/* Poster */}
                  <div>
                    {selectedMovie.poster_url && (
                      <img
                        src={selectedMovie.poster_url}
                        alt={selectedMovie.title}
                        className="w-full rounded-lg shadow-lg"
                      />
                    )}
                  </div>
                  
                  {/* Details */}
                  <div className="md:col-span-2 space-y-4">
                    {/* Rating & Runtime */}
                    <div className="flex items-center gap-4 flex-wrap">
                      {selectedMovie.rating > 0 && (
                        <div className="flex items-center gap-2 bg-yellow-100 text-yellow-900 px-3 py-2 rounded-lg">
                          <Star className="w-5 h-5 fill-yellow-900" />
                          <span className="font-bold text-lg">{selectedMovie.rating}</span>
                          <span className="text-sm">/ 10</span>
                        </div>
                      )}
                      {selectedMovie.runtime && (
                        <div className="flex items-center gap-2 text-gray-600">
                          <Clock className="w-5 h-5" />
                          <span>{selectedMovie.runtime} min</span>
                        </div>
                      )}
                    </div>
                    
                    {/* Synopsis */}
                    <div>
                      <h3 className="font-semibold text-lg mb-2">Synopsis</h3>
                      <p className="text-gray-700 leading-relaxed">{selectedMovie.synopsis}</p>
                    </div>
                    
                    {/* Genres */}
                    {selectedMovie.genres.length > 0 && (
                      <div>
                        <h3 className="font-semibold text-lg mb-2">Genres</h3>
                        <div className="flex flex-wrap gap-2">
                          {selectedMovie.genres.map((genre, idx) => (
                            <Badge key={idx} variant="outline" className="border-teal-300 text-teal-700">
                              {genre}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {/* Cast */}
                    {selectedMovie.cast.length > 0 && (
                      <div>
                        <h3 className="font-semibold text-lg mb-2">Cast</h3>
                        <p className="text-gray-700">{selectedMovie.cast.join(', ')}</p>
                      </div>
                    )}
                    
                    {/* Director */}
                    {selectedMovie.director && (
                      <div>
                        <h3 className="font-semibold text-lg mb-2">Director</h3>
                        <p className="text-gray-700">{selectedMovie.director}</p>
                      </div>
                    )}
                    
                    {/* Language & Release Date */}
                    <div className="flex gap-6">
                      <div>
                        <h3 className="font-semibold mb-1">Language</h3>
                        <p className="text-gray-700">{selectedMovie.language}</p>
                      </div>
                      {selectedMovie.release_date && (
                        <div>
                          <h3 className="font-semibold mb-1">Release Date</h3>
                          <p className="text-gray-700">{new Date(selectedMovie.release_date).toLocaleDateString()}</p>
                        </div>
                      )}
                    </div>
                    
                    {/* Streaming Platforms */}
                    <div>
                      <h3 className="font-semibold text-lg mb-3">Available On</h3>
                      <div className="flex flex-wrap gap-3">
                        {selectedMovie.ott_platforms.map((platform, idx) => (
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
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default App;
