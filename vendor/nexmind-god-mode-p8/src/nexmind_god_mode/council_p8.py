from __future__ import annotations
from copy import deepcopy
class CreativeCouncilP8:
    def __init__(self,sr,final_producer,calibration_registry):self.sr=sr;self.final_producer=final_producer;self.calibration=calibration_registry
    def final_review(self,story,final_board,*,multimodal_evidence=None):
        review=self.final_producer.review(self.sr.state['production_id'],self.sr.state['brief'],story,self.sr.state,final_board,multimodal_evidence=multimodal_evidence,calibration=self.calibration.status())
        tok=self.sr.register_final_producer_review(review,final_board)
        return {'review':review,'review_id':tok,'calibration':self.calibration.status()}
    def commit_review(self,review_record,final_board):return self.sr.commit_final_producer(review_record['review_id'],final_board)
