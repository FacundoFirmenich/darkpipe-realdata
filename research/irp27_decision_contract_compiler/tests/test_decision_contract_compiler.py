from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from decision_contract_compiler import compile_contract, jev_request, nimble_schema, validate

ROOT = Path(__file__).resolve().parents[1]


class Tests(unittest.TestCase):
    def setUp(self):
        self.contract=json.loads((ROOT/'contracts/evidence_relation.contract.json').read_text())
        self.schema=json.loads((ROOT/'protocols/decision_contract.schema.json').read_text())

    def test_valid(self):
        validate(self.contract,self.schema)

    def test_provider_has_no_authority(self):
        bad=json.loads(json.dumps(self.contract)); bad['authority']['provider_conveys_authority']=True
        with self.assertRaises(ValueError):
            validate(bad,self.schema)

    def test_jev_laya_shape(self):
        request=jev_request(self.contract)
        self.assertEqual(set(request['questions']),set(self.contract['questions']))
        self.assertEqual('NONE',request['metadata']['authority'])

    def test_nimble_preserves_types(self):
        schema=nimble_schema(self.contract)
        self.assertEqual(schema['schema']['properties']['supports']['type'],'boolean')
        self.assertEqual(schema['schema']['properties']['relation']['enum'],list(self.contract['questions']['relation']['criteria']))

    def test_compile(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest=compile_contract(ROOT/'contracts/evidence_relation.contract.json',ROOT/'protocols/decision_contract.schema.json',Path(directory))
            self.assertEqual(manifest['semantic_invariants']['automatic_execution'],False)
            self.assertEqual(manifest['semantic_invariants']['automatic_publication'],False)
            self.assertTrue((Path(directory)/'CompiledContract.lean').exists())


if __name__=='__main__':
    unittest.main()
