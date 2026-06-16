import os
import tempfile
import unittest
from datetime import date

from server.alert_center import get_alert_center
from server.contract_billing import create_merchant_contract, generate_contract_bills
from server.db import db_init, get_db


class TestAlertCenter(unittest.TestCase):
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

    def _seed_contract(self):
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO owners(name,phone) VALUES('预警商户','13911112222')")
        owner_id = cur.lastrowid
        cur.execute("INSERT INTO rooms(building,unit,room_number,category,area,owner_id,shop_name) VALUES('商场','商场','W-101','商户',80,?,'预警商户')", (owner_id,))
        room_id = cur.lastrowid
        conn.commit(); conn.close()
        return create_merchant_contract({
            "room_id": room_id,
            "owner_id": owner_id,
            "contract_no": "ALERT-001",
            "merchant_name": "预警商户",
            "shop_name": "预警商户",
            "rent_amount": 8000,
            "property_rate": 6,
            "deposit_amount": 10000,
            "start_date": "2026-01-01",
            "end_date": "2026-06-20",
        })

    def test_alert_center_counts_expiring_unpaid_and_zero_amount_risks(self):
        contract_id = self._seed_contract()
        generate_contract_bills(contract_id, "2026-06", operator="finance")
        conn = get_db()
        fee_id = conn.execute("SELECT id FROM fee_types WHERE name='合同租金'").fetchone()[0]
        room_id = conn.execute("SELECT room_id FROM merchant_contracts WHERE id=?", (contract_id,)).fetchone()[0]
        owner_id = conn.execute("SELECT owner_id FROM merchant_contracts WHERE id=?", (contract_id,)).fetchone()[0]
        conn.execute("INSERT INTO bills(room_id,owner_id,fee_type_id,billing_period,amount,status,bill_number,source) VALUES(?,?,?,?,0,'unpaid','ZERO-001','manual')", (room_id, owner_id, fee_id, '2026-06'))
        conn.commit(); conn.close()

        alerts = get_alert_center("2026-06", today=date(2026, 6, 8))

        self.assertEqual(alerts["summary"]["contracts_expiring_30d"], 1)
        self.assertEqual(alerts["summary"]["unpaid_contract_bills"], 3)
        self.assertEqual(alerts["summary"]["zero_amount_bills"], 1)
        self.assertEqual(alerts["severity"], "danger")
        self.assertEqual(alerts["expiring_contracts"][0]["contract_no"], "ALERT-001")
        self.assertIn("合同租金", [row["fee_name"] for row in alerts["unpaid_contract_bills"]])


    def test_alert_center_includes_space_contracts_without_room_link(self):
        conn = get_db()
        space_id = conn.execute(
            """INSERT INTO commercial_spaces(space_no,floor,area,shop_name,merchant_name,status)
               VALUES('SP-ALERT-01',1,120,'空间预警品牌','空间预警商户','active')"""
        ).lastrowid
        conn.commit(); conn.close()
        contract_id = create_merchant_contract({
            "commercial_space_id": space_id,
            "contract_no": "SPACE-ALERT-001",
            "merchant_name": "空间预警商户",
            "shop_name": "空间预警品牌",
            "rent_amount": 12000,
            "property_rate": 6,
            "deposit_amount": 20000,
            "start_date": "2026-01-01",
            "end_date": "2026-06-20",
        })
        generate_contract_bills(contract_id, "2026-06", operator="finance")

        alerts = get_alert_center("2026-06", today=date(2026, 6, 8))

        self.assertEqual(alerts["summary"]["contracts_expiring_30d"], 1)
        self.assertEqual(alerts["expiring_contracts"][0]["contract_no"], "SPACE-ALERT-001")
        self.assertEqual(alerts["expiring_contracts"][0]["room_number"], "SP-ALERT-01")
        self.assertEqual(alerts["summary"]["unpaid_contract_bills"], 3)
        self.assertTrue(all(row["room_number"] == "SP-ALERT-01" for row in alerts["unpaid_contract_bills"]))

    def test_alert_center_reports_normal_when_no_risks(self):
        alerts = get_alert_center("2026-06", today=date(2026, 6, 8))
        self.assertEqual(alerts["severity"], "success")
        self.assertEqual(alerts["summary"]["contracts_expiring_30d"], 0)
        self.assertEqual(alerts["summary"]["unpaid_contract_bills"], 0)


if __name__ == "__main__":
    unittest.main()
