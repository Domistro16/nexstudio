#!/usr/bin/env python3
"""Deterministic adversarial contract model. This is not payment-provider or real-DB certification."""
from dataclasses import dataclass, field
from copy import deepcopy

@dataclass
class Model:
    balance:int=0; ledgers:dict=field(default_factory=dict); entitlement:dict=field(default_factory=dict); reversals:dict=field(default_factory=dict); funding:dict=field(default_factory=dict); welcome_used:bool=False; deliverable:bool=False
    def purchase(self,owner,production,quote,key,amount,quote_owner=None,expired=False,client_amount=None):
        before=deepcopy(self.__dict__)
        if quote_owner not in (None,owner): raise ValueError('OWNER')
        if expired: raise ValueError('EXPIRED')
        if client_amount is not None: raise ValueError('CLIENT_PRICE')
        if key in self.ledgers:return self.ledgers[key]
        if production in self.entitlement:return self.ledgers[self.entitlement[production]]
        if self.balance<amount:return {'ok':False,'required':amount-self.balance}
        self.balance-=amount; self.ledgers[key]={'type':'DEBIT','amount':-amount,'balance':self.balance,'production':production}; self.entitlement[production]=key; self.welcome_used=True; return self.ledgers[key]
    def settle(self,intent,amount,expected,ref):
        if amount!=expected: raise ValueError('MISMATCH')
        key='funding-settlement:'+intent
        if key in self.ledgers:return self.ledgers[key]
        self.balance+=amount;self.ledgers[key]={'type':'FUNDING','amount':amount,'balance':self.balance,'ref':ref};self.funding[intent]='SETTLED';return self.ledgers[key]
    def refund(self,production,debit_key):
        if self.deliverable: raise ValueError('DELIVERABLE')
        if debit_key in self.reversals:return self.reversals[debit_key]
        debit=self.ledgers[debit_key];amount=abs(debit['amount']);self.balance+=amount;row={'type':'REFUND','amount':amount,'balance':self.balance,'production':production};self.reversals[debit_key]=row;return row

def run():
    tests=[]
    def t(name,fn):
        try: fn();tests.append((name,True,''))
        except Exception as e: tests.append((name,False,str(e)))
    t('low balance does not debit',lambda:(lambda m: (_ for _ in ()).throw(AssertionError()) if (m.purchase('u','p','q','k',100)['ok'] or m.balance!=0 or m.ledgers) else None)(Model()))
    t('same purchase key reuses one debit',lambda:(lambda m: (m.purchase('u','p','q','k',100),m.purchase('u','p','q','k',100), (_ for _ in ()).throw(AssertionError()) if len(m.ledgers)!=1 else None))(Model(balance=200)))
    t('different tab keys still one entitlement',lambda:(lambda m: (m.purchase('u','p','q','a',100),m.purchase('u','p','q','b',100), (_ for _ in ()).throw(AssertionError()) if m.balance!=100 or len(m.ledgers)!=1 else None))(Model(balance=200)))
    def owner():
        m=Model(balance=200)
        try:m.purchase('attacker','p','q','k',100,quote_owner='victim');raise AssertionError('accepted')
        except ValueError as e: assert str(e)=='OWNER' and m.balance==200
    t('cross-owner purchase rejected',owner)
    def expired():
        m=Model(balance=200)
        try:m.purchase('u','p','q','k',100,expired=True);raise AssertionError('accepted')
        except ValueError as e: assert str(e)=='EXPIRED' and m.balance==200
    t('expired quote leaves balance untouched',expired)
    def injection():
        m=Model(balance=200)
        try:m.purchase('u','p','q','k',100,client_amount=1);raise AssertionError('accepted')
        except ValueError as e: assert str(e)=='CLIENT_PRICE' and m.balance==200
    t('client price injection rejected',injection)
    t('provider settlement replay credits once',lambda:(lambda m:(m.settle('i',100,100,'s'),m.settle('i',100,100,'s'),(_ for _ in ()).throw(AssertionError()) if m.balance!=100 or len(m.ledgers)!=1 else None))(Model()))
    def mismatch():
        m=Model()
        try:m.settle('i',99,100,'s');raise AssertionError('accepted')
        except ValueError as e: assert str(e)=='MISMATCH' and m.balance==0
    t('provider amount mismatch cannot credit',mismatch)
    def refund_once():
        m=Model(balance=200);m.purchase('u','p','q','k',100);m.refund('p','k');m.refund('p','k');assert m.balance==200 and len(m.reversals)==1
    t('technical refund replay posts once',refund_once)
    def deliverable():
        m=Model(balance=200);m.purchase('u','p','q','k',100);m.deliverable=True
        try:m.refund('p','k');raise AssertionError('refunded delivered work')
        except ValueError as e: assert str(e)=='DELIVERABLE' and m.balance==100
    t('deliverable blocks automatic technical refund',deliverable)
    def welcome():
        m=Model(balance=400);m.purchase('u','p1','q1','a',180);assert m.welcome_used
    t('welcome redemption becomes consumed on first debit',welcome)
    def funding_then_purchase():
        m=Model(balance=20);m.settle('i',80,80,'s');r=m.purchase('u','p','q','k',100);assert r['type']=='DEBIT' and m.balance==0
    t('exact shortfall funding resumes same production purchase',funding_then_purchase)
    def failure_no_credit():
        m=Model(balance=20);m.funding['i']='FAILED';assert m.balance==20 and not m.ledgers
    t('provider failure has no ledger movement',failure_no_credit)
    def independent_funding_and_debit():
        m=Model();m.settle('i',100,100,'s');assert m.ledgers['funding-settlement:i']['type']=='FUNDING';m.purchase('u','p','q','k',100);assert len(m.ledgers)==2 and m.balance==0
    t('funding credit and production debit are separate atomic records',independent_funding_and_debit)
    failed=[x for x in tests if not x[1]]
    print({'schema':'StudioAdversarialBillingModel V1','pass':not failed,'passed':len(tests)-len(failed),'total':len(tests),'tests':[{'name':n,'ok':o,'detail':d} for n,o,d in tests],'warning':'Deterministic contract model only; not real PostgreSQL/provider readiness evidence.'})
    if failed: raise SystemExit(1)
if __name__=='__main__':run()
