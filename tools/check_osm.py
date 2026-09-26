"""
Karen's Ear — Link Verification Tool: OpenStreetMap Connectivity
Checks network accessibility to OpenStreetMap resources without requiring paid APIs.
"""

import sys
import urllib.request
import urllib.error

OSM_ENDPOINTS = [
    ("OSM Main", "https://www.openstreetmap.org"),
    ("OSM Tile Server", "https://tile.openstreetmap.org/0/0/0.png"),
]


def test_endpoint(name: str, url: str) -> bool:
    try:
        # Standard User-Agent to respect OSM policy
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "KarensEar-EmergencyIntelligence-Verifier/1.0 (Hackathon Verification)"},
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            status = response.getcode()
            print(f"  {name}: Reachable (HTTP {status})")
            return status in (200, 301, 302)
    except urllib.error.HTTPError as e:
        # Even a 403 on tile server due to bot protection indicates network reachability
        print(f"  {name}: Responded with HTTP {e.code} (Reachable)")
        return e.code in (200, 301, 302, 403)
    except Exception as e:
        print(f"  {name}: [FAIL] Network error: {e}")
        return False


def main() -> int:
    print("\n--- [CHECK: OpenStreetMap Connectivity] ---")
    results = [test_endpoint(name, url) for name, url in OSM_ENDPOINTS]
    if all(results):
        print(">>> RESULT: [PASS]")
        return 0
    else:
        print(">>> RESULT: [FAIL]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
