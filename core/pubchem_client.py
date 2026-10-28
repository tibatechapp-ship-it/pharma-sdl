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
        self._cache = {}

    def get_cid(self, name):
        """Get CID by name (cached)."""
        if name in self._cache:
            return self._cache[name]
        cids = self.search_by_name(name)
        cid = cids[0] if cids else None
        self._cache[name] = cid
        return cid

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


def fetch_drug_data(name):
    """Fetch drug data by name, returns dict or None."""
    client = PubChemClient()
    cids = client.search_by_name(name)
    if not cids:
        return None
    cid = cids[0]
    props = client.get_compound(cid)
    if not props:
        return None
    return {
        "name": name,
        "cid": cid,
        "smiles": props.get("CanonicalSMILES", ""),
        "mw": str(props.get("MolecularWeight", "")),
        "logp": props.get("XLogP", ""),
    }
