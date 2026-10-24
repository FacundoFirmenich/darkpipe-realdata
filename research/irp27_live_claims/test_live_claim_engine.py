from __future__ import annotations
import unittest
from live_claim_engine import lexical_flags,infer_event,match_atlas,process,summary
ATLAS=[{'claim_id':'FIN-02','claim':'Credit growth proves an improvement in household welfare.','estimand':'Whether new credit increases productive capacity or finances distress','classification':'SOCIOMATERIALLY_BLIND','public_language':'More credit can be useful or distress-driven.','max_authority':'UNDERDETERMINED_NO_WELFARE_SIGN'}]
SOURCE={'source_id':'S','actor':'A','publisher_type':'official_speech','date':'2026-10-16','url':'https://example.org'}
CLAIM={'live_claim_id':'C','source_fragment':'Un país no puede crecer sin crédito','normalized_claim':'El crédito es una condición necesaria y causal del crecimiento económico.','atlas_hint':'FIN-02','event_hint':'RHETORICAL_EXPANSION','claim_mode':'GENERAL_CAUSAL_CLAIM','estimand':'Efecto causal del crédito sobre crecimiento','observed_narrow':'Puede financiar inversión.','not_established':'No identifica causalidad.','safe_wording':'Puede ser una infraestructura.','blocked_wording':'Todo crédito causa crecimiento.','orientations':['CAUSALITY:OVERSTATES']}
class T(unittest.TestCase):
 def test_similarity(self):self.assertGreaterEqual(match_atlas(CLAIM,ATLAS)['similarity'],.88)
 def test_flags(self):self.assertTrue(lexical_flags('crece porque hay crédito')['causal'])
 def test_event(self):self.assertEqual('RHETORICAL_EXPANSION',infer_event(CLAIM,match_atlas(CLAIM,ATLAS)))
 def test_process_fail_closed(self):
  e=process(SOURCE,CLAIM,ATLAS,True,'abc');self.assertFalse(e['automatic_publication']);self.assertEqual('HUMAN_REVIEW_ALERT',e['notification_class'])
 def test_summary(self):self.assertEqual(1,summary([process(SOURCE,CLAIM,ATLAS,True,'abc')])['events'])
if __name__=='__main__':unittest.main()
