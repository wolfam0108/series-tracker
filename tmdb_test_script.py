import requests
import sys

# SETTINGS
# USER: Please replace with your actual API Read Access Token (long string)
TMDB_API_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJhN2UwN2MwNGRhZDE5OTUzNjk0OGY5ODViZDg4ZTk3NiIsIm5iZiI6MTc1ODU1MTgxNy4zNzUsInN1YiI6IjY4ZDE1ZjA5MmZhMWY2NTBlZWZlOTdjNiIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.tFyOjSbbL0GZ9u8LYZipqvJngEkzcZmsIL7x7rSlIuA" 

# Search query to test
SEARCH_QUERY = "Гриффины" 

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {TMDB_API_TOKEN}"
}

def search_series(query):
    url = f"https://api.themoviedb.org/3/search/tv?query={query}&include_adult=false&language=ru-RU&page=1"
    print(f"Searching for: {query}...")
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', [])
        print(f"Found {len(results)} results.")
        return results
    except Exception as e:
        print(f"Error searching series: {e}")
        return []

def get_series_details(series_id):
    url = f"https://api.themoviedb.org/3/tv/{series_id}?language=ru-RU"
    print(f"Fetching details for ID: {series_id}...")
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching details: {e}")
        return None

def main():
    if TMDB_API_TOKEN == "PLACEHOLDER_TOKEN":
        print("ERROR: Please update TMDB_API_TOKEN in the script with your actual key.")
        return

    # 1. Search
    results = search_series(SEARCH_QUERY)
    if not results:
        print("No results found.")
        return

    # 2. Display Results
    print(f"\n--- Found {len(results)} results for '{SEARCH_QUERY}' ---")
    for idx, res in enumerate(results):
        name = res.get('name', 'Unknown')
        orig_name = res.get('original_name', '')
        year = res.get('first_air_date', '????')[:4]
        print(f"[{idx}] {name} ({year}) | Orig: {orig_name} | ID: {res.get('id')}")

    # 3. Interactive Selection
    try:
        selection = input(f"\nSelect a series (0-{len(results)-1}): ")
        idx = int(selection)
        if idx < 0 or idx >= len(results):
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return

    selected_series = results[idx]
    print(f"\nSelected: {selected_series.get('name')} (ID: {selected_series.get('id')})")

    # 4. Get Details (Seasons)
    details = get_series_details(selected_series.get('id'))
    if details:
        print(f"\n--- Seasons Info ---")
        for season in details.get('seasons', []):
            print(f"Season {season.get('season_number')}: {season.get('episode_count')} episodes (Air Date: {season.get('air_date')})")

if __name__ == "__main__":
    main()
