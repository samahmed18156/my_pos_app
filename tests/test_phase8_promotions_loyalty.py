import sqlite3
import unittest
from services.promotion_service import ensure_schema as promo_schema, calculate_best_promotion
from services.loyalty_service import ensure_schema as loyalty_schema, balance, earn_for_sale, reverse_sale, reverse_return

class Phase8PromotionLoyaltyTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.execute('CREATE TABLE promotions(id INTEGER PRIMARY KEY,name TEXT UNIQUE,promo_type TEXT,value REAL,start_date TEXT,end_date TEXT,min_spend REAL,active INTEGER,notes TEXT)')
        promo_schema(self.c); loyalty_schema(self.c)
    def test_best_percentage_promotion(self):
        self.c.execute("INSERT INTO promotions VALUES(1,'Ten','Percentage',10,'2020-01-01','2099-12-31',0,1,'')")
        r=calculate_best_promotion(self.c,[{'qty':2,'price':100,'value':200}])
        self.assertEqual(r['discount'],20); self.assertEqual(r['total'],180)
    def test_fixed_promotion_is_capped(self):
        self.c.execute("INSERT INTO promotions VALUES(1,'Save','Fixed Amount',250,'2020-01-01','2099-12-31',0,1,'')")
        r=calculate_best_promotion(self.c,[{'qty':1,'price':100,'value':100}])
        self.assertEqual(r['discount'],100); self.assertEqual(r['total'],0)
    def test_buy_get_notes_rule(self):
        self.c.execute("INSERT INTO promotions VALUES(1,'B2G1','Buy X Get Y',1,'2020-01-01','2099-12-31',0,1,'buy=2,get=1')")
        r=calculate_best_promotion(self.c,[{'qty':3,'price':10,'value':30}])
        self.assertEqual(r['discount'],10)
    def test_loyalty_earn_and_void_reversal(self):
        self.assertEqual(earn_for_sale(self.c,7,11,99),9)
        self.assertEqual(balance(self.c,7),9)
        self.assertEqual(reverse_sale(self.c,7,11),9)
        self.assertEqual(balance(self.c,7),0)
    def test_return_reversal_is_proportional(self):
        earn_for_sale(self.c,7,12,100,rate=10)
        self.assertEqual(reverse_return(self.c,7,12,4,50,100),5)
        self.assertEqual(balance(self.c,7),5)

if __name__=='__main__': unittest.main()
