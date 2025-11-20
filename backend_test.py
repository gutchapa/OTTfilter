import requests
import sys
import json
from datetime import datetime

class OTTAggregatorAPITester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict):
                        if 'movies' in response_data:
                            print(f"   Movies returned: {len(response_data['movies'])}")
                        elif isinstance(response_data, list):
                            print(f"   Items returned: {len(response_data)}")
                    elif isinstance(response_data, list):
                        print(f"   Items returned: {len(response_data)}")
                except:
                    pass
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Error: {response.text[:200]}")

            self.test_results.append({
                'name': name,
                'method': method,
                'endpoint': endpoint,
                'expected_status': expected_status,
                'actual_status': response.status_code,
                'success': success,
                'response_size': len(response.text) if response.text else 0
            })

            return success, response.json() if success and response.text else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.test_results.append({
                'name': name,
                'method': method,
                'endpoint': endpoint,
                'expected_status': expected_status,
                'actual_status': 'ERROR',
                'success': False,
                'error': str(e)
            })
            return False, {}

    def test_discover_movies(self):
        """Test initial movie discovery"""
        success, response = self.run_test(
            "Discover Movies (Initial Load)",
            "GET",
            "discover",
            200,
            params={"page": 1}
        )
        
        if success and 'movies' in response:
            movies = response['movies']
            print(f"   ✓ Found {len(movies)} movies")
            
            # Check for diverse content
            languages = set()
            genres = set()
            platforms = set()
            
            for movie in movies[:5]:  # Check first 5 movies
                if 'language' in movie:
                    languages.add(movie['language'])
                if 'genres' in movie:
                    genres.update(movie['genres'])
                if 'ott_platforms' in movie:
                    platforms.update(movie['ott_platforms'])
            
            print(f"   ✓ Languages found: {', '.join(languages)}")
            print(f"   ✓ Genres found: {len(genres)} different genres")
            print(f"   ✓ OTT Platforms found: {', '.join(list(platforms)[:3])}...")
            
            return movies[0] if movies else None
        
        return None

    def test_search_functionality(self):
        """Test search by movie name, actor, director"""
        test_queries = [
            "Rajinikanth",  # Actor search
            "Aamir Khan",   # Actor search
            "Baahubali",    # Movie search
            "RRR"           # Movie search
        ]
        
        for query in test_queries:
            success, response = self.run_test(
                f"Search Movies - '{query}'",
                "GET",
                "basic",
                200,
                params={"q": query}
            )
            
            if success and isinstance(response, list):
                print(f"   ✓ Found {len(response)} results for '{query}'")

    def test_filter_options(self):
        """Test filter options endpoint"""
        success, response = self.run_test(
            "Get Filter Options",
            "GET",
            "options/all",
            200
        )
        
        if success:
            print(f"   ✓ Genres available: {len(response.get('genres', []))}")
            print(f"   ✓ Languages available: {len(response.get('languages', []))}")
            print(f"   ✓ Platforms available: {len(response.get('platforms', []))}")
            return response
        
        return None

    def test_movie_filtering(self, filter_options):
        """Test various filtering combinations"""
        if not filter_options:
            print("❌ Cannot test filtering - no filter options available")
            return
        
        # Test 1: Filter by genre
        if filter_options.get('genres'):
            genre = filter_options['genres'][0]
            success, response = self.run_test(
                f"Filter by Genre - '{genre}'",
                "POST",
                "movies/filter",
                200,
                data={"genres": [genre]}
            )
        
        # Test 2: Filter by language
        if filter_options.get('languages'):
            language = filter_options['languages'][0]
            success, response = self.run_test(
                f"Filter by Language - '{language}'",
                "POST",
                "movies/filter",
                200,
                data={"languages": [language]}
            )
        
        # Test 3: Filter by platform
        if filter_options.get('platforms'):
            platform = filter_options['platforms'][0]
            success, response = self.run_test(
                f"Filter by Platform - '{platform}'",
                "POST",
                "movies/filter",
                200,
                data={"platforms": [platform]}
            )
        
        # Test 4: Filter by rating
        success, response = self.run_test(
            "Filter by Rating (>7.0)",
            "POST",
            "movies/filter",
            200,
            data={"min_rating": 7.0}
        )
        
        # Test 5: Multiple filters
        if filter_options.get('genres') and filter_options.get('languages'):
            success, response = self.run_test(
                "Multiple Filters (Genre + Language + Rating)",
                "POST",
                "movies/filter",
                200,
                data={
                    "genres": [filter_options['genres'][0]],
                    "languages": [filter_options['languages'][0]],
                    "min_rating": 6.0
                }
            )

    def test_movie_details(self, sample_movie):
        """Test movie details endpoint"""
        if not sample_movie or 'id' not in sample_movie:
            print("❌ Cannot test movie details - no sample movie available")
            return
        
        success, response = self.run_test(
            f"Get Movie Details - '{sample_movie.get('title', 'Unknown')}'",
            "GET",
            f"movies/{sample_movie['id']}",
            200
        )
        
        if success:
            required_fields = ['title', 'genres', 'language', 'ott_platforms', 'rating']
            for field in required_fields:
                if field in response:
                    print(f"   ✓ {field}: {response[field]}")

def main():
    print("🎬 OTT Aggregator API Testing")
    print("=" * 50)
    
    tester = OTTAggregatorAPITester()
    
    # Test 1: Discover movies (initial load)
    sample_movie = tester.test_discover_movies()
    
    # Test 2: Search functionality
    tester.test_search_functionality()
    
    # Test 3: Get filter options
    filter_options = tester.test_filter_options()
    
    # Test 4: Test filtering
    tester.test_movie_filtering(filter_options)
    
    # Test 5: Movie details
    tester.test_movie_details(sample_movie)
    
    # Print final results
    print(f"\n📊 Test Results")
    print("=" * 50)
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if success_rate < 70:
        print("❌ Critical issues found - Backend needs attention")
        return 1
    elif success_rate < 90:
        print("⚠️  Some issues found - Review recommended")
        return 0
    else:
        print("✅ All tests passed - Backend working well")
        return 0

if __name__ == "__main__":
    sys.exit(main())