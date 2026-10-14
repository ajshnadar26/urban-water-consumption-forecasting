import unittest
import numpy as np
import pandas as pd
from src.allocation import allocate, MINIMUM
from src.pipeline import clean_records,metrics,predict

class SystemTests(unittest.TestCase):
    def test_supply_and_caps(self):
        for supply in [0,20,60,100,150]:
            for policy in ['Priority','Proportional']:
                demand=np.array([50.,25.,15.,10.]);cap=demand*np.array([1.,.8,.7,1.])
                out,status=allocate(demand,supply,policy,cap)
                self.assertLessEqual(out.allocated_mg.sum(),supply+1e-7)
                self.assertTrue((out.allocated_mg>=-1e-7).all())
                self.assertTrue((out.allocated_mg<=np.minimum(demand,cap)+1e-7).all())
                if status['feasible']: self.assertTrue((out.allocated_mg>=MINIMUM*demand-1e-7).all())
    def test_emergency_is_explicit(self):
        out,status=allocate([50,25,15,10],10)
        self.assertFalse(status['feasible']); self.assertGreater(out.minimum_violation_mg.sum(),0)
    def test_capacity_can_make_floors_infeasible(self):
        _,status=allocate([50,25,15,10],200,capacity=[10,25,15,10])
        self.assertFalse(status['feasible'])
    def test_zero_demand(self):
        out,status=allocate([0,0,0,0],100)
        self.assertEqual(out.allocated_mg.sum(),0); self.assertTrue(status['feasible'])
    def test_bad_input(self):
        for supply in [-1,np.nan]:
            with self.assertRaises(ValueError):allocate([1,2,3,4],supply)
    def test_duplicates(self):
        frame=pd.DataFrame({'year_month':[202001,202001],'postal_code':['a','a'],'customer_class':['x','x'],'total_gallons':[20,20]})
        cleaned,audit=clean_records(frame)
        self.assertEqual(len(cleaned),1);self.assertEqual(audit['exact_duplicates_removed'],1)
        frame.loc[1,'total_gallons']=30
        with self.assertRaises(ValueError):clean_records(frame)
    def test_invalid_record(self):
        frame=pd.DataFrame({'year_month':['bad'],'postal_code':['a'],'customer_class':['x'],'total_gallons':[20]})
        with self.assertRaises(ValueError):clean_records(frame)
    def test_metrics_zero_handling(self):
        m=metrics([0,10],[2,8]);self.assertEqual(m['MAE'],2);self.assertEqual(m['RMSE'],2)
        self.assertEqual(m['MAPE'],20);self.assertIsNone(metrics([0],[1])['MAPE'])
    def test_future_weather_cannot_leak_into_predictions(self):
        index=pd.date_range('2020-01-01',periods=36,freq='MS')
        frame=pd.DataFrame({'temperature_2m_mean':20+np.sin(np.arange(36)),
                            'precipitation_sum':50+np.arange(36)},index=index)
        history=pd.Series(100+np.arange(24),index=index[:24])
        original,_=predict('Weather calendar regression',history,frame,index[24:],(0,0,0))
        frame.loc[index[24:],:]=1e9
        changed,_=predict('Weather calendar regression',history,frame,index[24:],(0,0,0))
        np.testing.assert_allclose(original,changed)

if __name__=='__main__': unittest.main()
