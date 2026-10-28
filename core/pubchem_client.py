"""
PubChem API client for fetching real compound data.
"""
import urllib.request
import json


class PubChemClient:
    """Client for PubChem REST API."""

    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    def __init__(self, timeout=10):
        self.timeout = timeout

    def get_compound(self, cid):
        """Fetch compound by CID."""
        url = f"{self.BASE_URL}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
            props = data["PropertyTable"]["Properties"][0]
            return props
        except Exception:
            return None

    def search_by_name(self, name):
        """Search compound by name."""
        url = f"{self.BASE_URL}/compound/name/{name}/cids/JSON"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
            return data["IdentifierList"]["CID"]
        except Exception:
            return []
