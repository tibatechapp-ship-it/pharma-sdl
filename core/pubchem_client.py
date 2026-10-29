"""
عميل PubChem PUG REST API.
يجلب بيانات حقيقية عن المركبات من قاعدة NCBI.
يتعامل بمرونة مع تغيّرات أسماء حقول PubChem عبر الإصدارات.
"""
import time

import requests


class PubChemClient:
    BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    PROPERTIES = "MolecularFormula,MolecularWeight,SMILES,CanonicalSMILES,ConnectivitySMILES,IsomericSMILES,XLogP,HBondDonorCount,HBondAcceptorCount,TPSA,RotatableBondCount,HeavyAtomCount,Complexity"

    def __init__(self, delay: float = 0.25):
        self.session = requests.Session()
        self.delay = delay
        self.cache: dict[int, dict] = {}

    def _get(self, url: str, timeout: int = 15) -> requests.Response | None:
        try:
            time.sleep(self.delay)
            r = self.session.get(url, timeout=timeout)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r
        except requests.RequestException:
            return None

    def get_cid(self, name: str) -> int | None:
        url = f"{self.BASE}/compound/name/{name}/cids/JSON"
        r = self._get(url)
        if r is None:
            return None
        try:
            return r.json()["IdentifierList"]["CID"][0]
        except (KeyError, IndexError):
            return None

    def get_cid_from_smiles(self, smiles: str) -> int | None:
        url = f"{self.BASE}/compound/smiles/{smiles}/cids/JSON"
        r = self._get(url)
        if r is None:
            return None
        try:
            return r.json()["IdentifierList"]["CID"][0]
        except (KeyError, IndexError):
            return None

    def get_properties(self, cid: int) -> dict | None:
        if cid in self.cache:
            return self.cache[cid]
        url = f"{self.BASE}/compound/cid/{cid}/property/{self.PROPERTIES}/JSON"
        r = self._get(url)
        if r is None:
            return None
        try:
            data = r.json()["PropertyTable"]["Properties"][0]
            self.cache[cid] = data
            return data
        except (KeyError, IndexError):
            return None

    @staticmethod
    def _extract_smiles(props: dict) -> str | None:
        for key in (
            "SMILES",
            "CanonicalSMILES",
            "ConnectivitySMILES",
            "IsomericSMILES",
        ):
            val = props.get(key)
            if val and str(val).strip():
                return str(val).strip()
        return None

    def fetch_drug(self, name: str) -> dict | None:
        cid = self.get_cid(name)
        if cid is None:
            return None
        props = self.get_properties(cid)
        if props is None:
            return None
        return {
            "name": name,
            "cid": cid,
            "smiles": self._extract_smiles(props),
            "mw": props.get("MolecularWeight"),
            "formula": props.get("MolecularFormula"),
            "logp": props.get("XLogP"),
            "hbd": props.get("HBondDonorCount"),
            "hba": props.get("HBondAcceptorCount"),
            "tpsa": props.get("TPSA"),
        }


_default_client: PubChemClient | None = None


def fetch_drug_data(name: str) -> dict | None:
    global _default_client
    if _default_client is None:
        _default_client = PubChemClient()
    return _default_client.fetch_drug(name)
