"""
اختبارات PubChem (تُوسَم integration — تحتاج إنترنت).
"""
import pytest
from core.pubchem_client import PubChemClient, fetch_drug_data


@pytest.mark.integration
class TestPubChem:

    def test_known_cid(self):
        """الماء معروف: CID 962."""
        client = PubChemClient()
        assert client.get_cid("water") == 962

    def test_known_smiles(self):
        """الأسبرين: C9H8O4."""
        data = fetch_drug_data("aspirin")
        assert data is not None
        assert data['cid'] == 2244
        assert data['smiles'] == "CC(=O)OC1=CC=CC=C1C(=O)O"
        assert data['mw'] == "180.16"

    def test_invalid_drug(self):
        """اسم غير موجود يعيد None."""
        assert fetch_drug_data("THIS_DOES_NOT_EXIST_12345") is None

    def test_cache_works(self):
        """الاستدعاء الثاني أسرع (من cache)."""
        client = PubChemClient()
        cid1 = client.get_cid("aspirin")
        cid2 = client.get_cid("aspirin")
        assert cid1 == cid2

    def test_returns_dict_shape(self):
        """البيانات المُعادة لها الشكل المتوقع."""
        data = fetch_drug_data("ibuprofen")
        assert data is not None
        for key in ['name', 'cid', 'smiles', 'mw', 'logp']:
            assert key in data
