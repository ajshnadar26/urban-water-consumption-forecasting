"""Integration checks of the actual Streamlit app and planning controls."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

class DashboardTests(unittest.TestCase):
    def test_dashboard_controls(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=45).run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.tabs),6)
        self.assertEqual(app.metric[3].value,'Feasible')
        app.sidebar.selectbox[1].select('Proportional').run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.metric[3].value,'Feasible')
        app.sidebar.slider[0].set_value(35).run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.metric[3].value,'INFEASIBLE')
        self.assertTrue(any('EMERGENCY' in e.value for e in app.error))
        app.sidebar.slider[0].set_value(110)
        app.sidebar.slider[1].set_value(50).run()
        self.assertEqual(app.metric[3].value,'INFEASIBLE')

if __name__=='__main__':unittest.main()
