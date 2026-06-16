import os
import tempfile
import unittest
from datetime import date

from server.db import db_init, get_db
from server.contract_billing import create_merchant_contract, generate_contract_bills, build_contract_billing_preview, confirm_contract_billing
from server.cloud_schema import build_postgres_schema
from server.dashboard_v2 import get_enterprise_dashboard_metrics
from server.permissions import is_readonly_role, role_allows


class V2CommercialComplexTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("PM_DB_PATH")
        os.environ["PM_DB_PATH"] = os.path.join(self.tmp.name, "property.db")
        import server.db as db
        db.DB_PATH = os.environ["PM_DB_PATH"]
        db_init()

    def tearDown(self):
        if self.old_db is None:
            os.environ.pop("PM_DB_PATH", None)
        else:
            os.environ["PM_DB_PATH"] = self.old_db
        import server.db as db
        db.DB_PATH = os.environ.get("PM_DB_PATH") or db.DB_PATH
        self.tmp.cleanup()

    def _seed_mall_room(self):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO owners(name,phone) VALUES('星河餐饮','13800000000')")
        owner_id = cur.lastrowid
        cur.execute(
            """INSERT INTO rooms(building,unit,room_number,category,area,owner_id,shop_name,custom_rate,payment_cycle)
               VALUES('商场','商场','A-101','商户',120,?,?,8.5,'monthly')""",
            (owner_id, "星河餐饮"),
        )
        room_id = cur.lastrowid
        conn.commit()
        conn.close()
        return room_id, owner_id

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("PM_DB_PATH")
        os.environ["PM_DB_PATH"] = os.path.join(self.tmp.name, "property.db")
        import server.db as db
        db.DB_PATH = os.environ["PM_DB_PATH"]
        db_init()

    def tearDown(self):
        if self.old_db is None:
            os.environ.pop("PM_DB_PATH", None)
        else:
            os.environ["PM_DB_PATH"] = self.old_db
        import server.db as db
        db.DB_PATH = os.environ.get("PM_DB_PATH") or db.DB_PATH
        self.tmp.cleanup()

    def _seed_mall_room(self):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO owners(name,phone) VALUES('星河餐饮','13800000000')")
        owner_id = cur.lastrowid
        cur.execute(
            """INSERT INTO rooms(building,unit,room_number,category,area,owner_id,shop_name,custom_rate,payment_cycle)
               VALUES('商场','商场','A-101','商户',120,?,?,8.5,'monthly')""",
            (owner_id, "星河餐饮"),
        )
        room_id = cur.lastrowid
        conn.commit()
        conn.close()
        return room_id, owner_id

