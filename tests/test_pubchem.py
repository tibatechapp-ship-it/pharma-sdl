"""
اختبارات PubChem Client.
تُوسَم بـ integration لأنها تحتاج إنترنت.
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
        """الأسبرين: يجب أن يُعيد SMILES صالحاً يمثل C9H8O4."""
        data = fetch_drug_data("aspirin")
        assert data is not None, "فشل جلب بيانات الأسبرين"
        assert data["cid"] == 2244

        smiles = data["smiles"]
        assert smiles, "حقل SMILES فارغ أو None"
        assert "C" in smiles and "O" in smiles, "SMILES لا يحتوي ذرات C/O"

        try:
            from rdkit import Chem
            expected = Chem.CanonSmiles("CC(=O)OC1=CC=CC=C1C(=O)O")
            actual = Chem.CanonSmiles(smiles)
            assert actual == expected, f"SMILES لا يطابق الأسبرين: {smiles}"
        except ImportError:
            pass

    def test_invalid_drug(self):
        """اسم غير موجود يعيد None."""
        assert fetch_drug_data("THIS_DRUG_DOES_NOT_EXIST_12345") is None

    def test_cache_works(self):
        """الاستدعاء الثاني يعيد نفس CID (من cache)."""
        client = PubChemClient()
        cid1 = client.get_cid("aspirin")
        cid2 = client.get_cid("aspirin")
        assert cid1 == cid2 == 2244

    def test_returns_dict_shape(self):
        """البيانات المُعادة لها الشكل المتوقع."""
        data = fetch_drug_data("ibuprofen")
        assert data is not None
        for key in ("name", "cid", "smiles", "mw", "logp"):
            assert key in data, f"مفتاح مفقود: {key}"
        assert data["smiles"] is not None
