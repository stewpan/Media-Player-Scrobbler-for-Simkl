"""
Season resolver for Simkl MPS: filters and ranks show/anime search results by season number,
verifies episodes map correctly, and caches the resolved mappings.
"""
import logging
import re
import requests
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

SIMKL_API_BASE_URL = "https://api.simkl.com"

# In-memory cache for resolved titles and seasons to Simkl ID and details
# Key: (title.lower().strip(), season_number, media_type) -> resolved_dict
_resolver_cache: Dict[tuple, Dict[str, Any]] = {}

def clear_resolver_cache():
    """Clear the season resolver cache."""
    _resolver_cache.clear()
    logger.info("SeasonResolver: Cache cleared.")

def title_matches_season(title: str, season: int) -> bool:
    """Helper to check if a Simkl show title contains explicit indicators of the target season."""
    if not title or not season:
        return False
    title_lower = title.lower()
    try:
        season = int(season)
    except (ValueError, TypeError):
        return False

    roman = {1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi", 7: "vii", 8: "viii", 9: "ix", 10: "x"}
    roman_num = roman.get(season, "INVALID")
    
    patterns = [
        rf"\bseason\s*0*{season}\b",
        rf"\bs0*{season}\b",
        rf"\b{season}(?:st|nd|rd|th)?\s*season\b",
        rf"\bpart\s*0*{season}\b",
        rf"\bcour\s*0*{season}\b",
    ]
    if roman_num != "INVALID":
        patterns.append(rf"\bpart\s*{roman_num}\b")
        patterns.append(rf"\b{roman_num}\b")
        
    # Also support word representation of numbers
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth"}
    if season in words:
        patterns.append(rf"\b{words[season]}\s*season\b")
        
    for pattern in patterns:
        if re.search(pattern, title_lower):
            return True
            
    return False

def query_simkl_search(query: str, client_id: str, access_token: str, media_type: str = "anime") -> List[Dict[str, Any]]:
    """Helper to query Simkl's TV/Anime search API."""
    endpoint = "/search/anime" if media_type == "anime" else "/search/tv"
    headers = {
        'Content-Type': 'application/json',
        'simkl-api-key': client_id,
        'Authorization': f'Bearer {access_token}',
        'User-Agent': "Media-Player-Scrobbler-for-Simkl"
    }
    
    try:
        params = {'q': query, 'extended': 'full'}
        logger.debug(f"SeasonResolver: Querying {endpoint} with '{query}'")
        response = requests.get(f'{SIMKL_API_BASE_URL}{endpoint}', headers=headers, params=params)
        if response.status_code == 200:
            return response.json() or []
        else:
            logger.warning(f"Simkl API search failed for '{query}' on {endpoint}. Status: {response.status_code}")
    except Exception as e:
        logger.error(f"Error querying Simkl search for '{query}': {e}")
    return []

def get_episodes(simkl_id: int, client_id: str, access_token: str, media_type: str = "anime") -> List[Dict[str, Any]]:
    """Fetch episodes for an anime/show to verify if the episode number exists."""
    endpoint = f"/anime/{simkl_id}/episodes" if media_type == "anime" else f"/tv/{simkl_id}/episodes"
    headers = {
        'Content-Type': 'application/json',
        'simkl-api-key': client_id,
        'Authorization': f'Bearer {access_token}',
        'User-Agent': "Media-Player-Scrobbler-for-Simkl"
    }
    
    try:
        logger.debug(f"SeasonResolver: Fetching episodes from {endpoint}")
        response = requests.get(f'{SIMKL_API_BASE_URL}{endpoint}', headers=headers)
        if response.status_code == 200:
            return response.json() or []
        else:
            logger.warning(f"Simkl API episodes fetch failed for ID {simkl_id} on {endpoint}. Status: {response.status_code}")
    except Exception as e:
        logger.error(f"Error fetching episodes for Simkl ID {simkl_id}: {e}")
    return []

def verify_episode_exists(simkl_id: int, episode: int, client_id: str, access_token: str, media_type: str = "anime") -> bool:
    """Calls /anime/{id}/episodes or /tv/{id}/episodes and verifies that the episode number exists."""
    episodes = get_episodes(simkl_id, client_id, access_token, media_type)
    if not episodes:
        return False
    
    # Check if there's any episode matching the target episode number
    for ep in episodes:
        if ep.get('episode') == episode:
            return True
    return False

def resolve_season_entry(
    title: str, 
    season: int, 
    episode: int,
    client_id: str, 
    access_token: str, 
    media_type: str = "anime"
) -> Optional[Dict[str, Any]]:
    """
    Resolves the correct Simkl ID and details for a given show/anime title and season.
    Filters and ranks results to find the correct entry.
    Calls verification on the episode mapping before returning.
    Caches resolved values.
    """
    if not title or season is None or episode is None:
        return None
        
    title_clean = title.strip()
    cache_key = (title_clean.lower(), season, media_type)
    if cache_key in _resolver_cache:
        cached_result = _resolver_cache[cache_key]
        logger.info(f"SeasonResolver: Cache hit for '{title_clean}' Season {season} ({media_type}) -> ID {cached_result['simkl_id']}")
        return cached_result
        
    logger.info(f"SeasonResolver: Resolving Season {season} for '{title_clean}' ({media_type})")
    
    # Build search queries
    queries = []
    if season > 1:
        # Standard english representation
        queries.append(f"{title_clean} Season {season}")
        # Standard ordinal representation
        ordinal = f"{season}nd" if season == 2 else f"{season}rd" if season == 3 else f"{season}th"
        queries.append(f"{title_clean} {ordinal} Season")
    queries.append(title_clean)
    
    search_results = []
    for q in queries:
        results = query_simkl_search(q, client_id, access_token, media_type)
        if results:
            search_results.extend(results)
            
    if not search_results:
        logger.warning(f"SeasonResolver: No search results found for any query of '{title_clean}' ({media_type})")
        return None
        
    # Deduplicate results by Simkl ID
    seen_ids = set()
    unique_results = []
    for item in search_results:
        simkl_id = item.get('ids', {}).get('simkl') or item.get('ids', {}).get('simkl_id')
        if simkl_id and simkl_id not in seen_ids:
            seen_ids.add(simkl_id)
            # Ensure simkl key exists on ids dict
            item.setdefault('ids', {})['simkl'] = simkl_id
            unique_results.append(item)
            
    # Filter and rank results
    ranked_results = []
    for item in unique_results:
        item_title = item.get('title', '')
        score = 0
        
        # Check if title matches our targeted season explicitly
        if title_matches_season(item_title, season):
            score += 100
        else:
            if season > 1:
                # If searching for S > 1, downrank if it matches another season explicitly
                has_other_season = False
                for other_s in range(1, 15):
                    if other_s != season and title_matches_season(item_title, other_s):
                        has_other_season = True
                        break
                if has_other_season:
                    score -= 80
                else:
                    # Generic show title (usually represents Season 1), downrank slightly if searching for S > 1
                    score -= 20
            else:
                # If searching for S1, downrank if it matches S > 1 explicitly
                has_other_season = False
                for other_s in range(2, 15):
                    if title_matches_season(item_title, other_s):
                        has_other_season = True
                        break
                if has_other_season:
                    score -= 80
                    
        # Match base title similarity (strip trailing season suffixes)
        clean_item_title = re.sub(r'\b(season|part|cour|nd|rd|th|\d+)\b.*', '', item_title, flags=re.IGNORECASE).strip()
        if clean_item_title.lower() == title_clean.lower():
            score += 10
            
        ranked_results.append((score, item))
        
    # Sort by score descending
    ranked_results.sort(key=lambda x: x[0], reverse=True)
    
    # Verify episode mapping on candidates
    for score, item in ranked_results:
        simkl_id = item['ids']['simkl']
        item_title = item.get('title', '')
        
        if verify_episode_exists(simkl_id, episode, client_id, access_token, media_type):
            logger.info(f"SeasonResolver: Successfully resolved and verified '{title_clean}' Season {season} -> '{item_title}' (ID: {simkl_id})")
            resolved_dict = {
                "simkl_id": simkl_id,
                "title": item_title,
                "type": media_type,
                "raw_result": item
            }
            _resolver_cache[cache_key] = resolved_dict
            return resolved_dict
        else:
            logger.info(f"SeasonResolver: Episode {episode} verification failed for '{item_title}' (ID: {simkl_id}). Trying next candidate.")
            
    # Fallback if episode verification failed but we had candidates
    if ranked_results:
        highest_score, best_item = ranked_results[0]
        simkl_id = best_item['ids']['simkl']
        item_title = best_item.get('title', '')
        logger.warning(f"SeasonResolver: Episode verification failed for all candidates. Falling back to '{item_title}' (ID: {simkl_id})")
        resolved_dict = {
            "simkl_id": simkl_id,
            "title": item_title,
            "type": media_type,
            "raw_result": best_item
        }
        _resolver_cache[cache_key] = resolved_dict
        return resolved_dict
        
    return None
