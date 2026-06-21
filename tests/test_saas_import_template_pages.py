import unittest

from fastapi.testclient import TestClient

from server.saas_app import create_app


class TestSaasImportTemplatePages(unittest.TestCase):
    def _client(self, role_code='finance'):
        client = TestClient(create_app())
        response = client.post('/api/auth/login', json={
            'tenant_name': '模板物业',
            'project_name': '模板项目',
            'username': role_code,
            'role_code': role_code,
        })
        self.assertEqual(response.status_code, 200)
        return client

    def test_import_home_links_template_and_field_guide(self):
        client = self._client('finance')
        page = client.get('/backoffice/imports')
        self.assertEqual(page.status_code, 200)
        self.assertIn('导入模板', page.text)
        self.assertIn('/backoffice/imports/templates/charge-targets', page.text)
        self.assertIn('/api/imports/templates/charge-targets.csv', page.text)

    def test_template_page_documents_required_fields_and_business_names(self):
        client = self._client('finance')
        page = client.get('/backoffice/imports/templates/charge-targets')
        self.assertEqual(page.status_code, 200)
        html = page.text
        for text in [
            '收费对象导入模板',
            '字段说明',
            '楼栋 / 区域',
            '单元 / 分区',
            '房号 / 铺位号',
            '类型',
            '面积',
            '必填',
            '导入预览不会写库',
            '确认导入才写入有效行',
            '客户上传文件只进入当前租户目录',
            '下载 CSV 模板',
        ]:
            self.assertIn(text, html)
        self.assertNotIn('POSTGRES_PASSWORD=', html)
        self.assertNotIn('APP_SECRET_KEY=', html)

    def test_csv_template_download_requires_login_and_returns_safe_columns(self):
        client = self._client('finance')
        response = client.get('/api/imports/templates/charge-targets.csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response.headers.get('content-type', ''))
        self.assertIn('attachment; filename="charge_targets_template.csv"', response.headers.get('content-disposition', ''))
        lines = response.text.strip().splitlines()
        for text in ['项目', '楼栋/区域', '单元/分区', '房号/铺位号', '对象类型', '面积㎡', '物业费单价', '业主姓名']:
            self.assertIn(text, lines[0])
        self.assertIn('住宅楼,1单元,101', response.text)
        self.assertIn('居民,80', response.text)
        self.assertIn('canonical fields: owner_name,owner_phone', response.text)
        self.assertNotIn('tenant_id', response.text)
        self.assertNotIn('project_id', response.text)

    def test_template_page_documents_full_owner_room_charge_target_fields(self):
        client = self._client('finance')
        page = client.get('/backoffice/imports/templates/charge-targets')
        self.assertEqual(page.status_code, 200)
        for text in [
            '业主类型',
            '楼层',
            '店名',
            '承租人',
            '承租电话',
            '独立单价',
            '缴费周期',
            '备注',
            '旧表头兼容',
            '业主姓名、联系电话、楼栋/区域、单元/分区、房号/铺位号',
        ]:
            self.assertIn(text, page.text)


    def test_csv_template_aligns_with_desktop_basic_import_headers(self):
        client = self._client('finance')
        response = client.get('/api/imports/templates/charge-targets.csv')
        self.assertEqual(response.status_code, 200)
        first_line = response.text.splitlines()[0]
        for text in [
            '项目', '楼栋/区域', '单元/分区', '房号/铺位号', '楼层', '对象类型', '面积㎡',
            '物业费单价', '水费标准', '业主姓名', '业主电话', '身份证号', '租户姓名', '租户电话',
            '租户身份证号', '合同开始日期', '合同结束日期', '缴费周期', '店铺名称', '业态/商户类别', '备注',
        ]:
            self.assertIn(text, first_line)
        for hidden in ['tenant_id', 'project_id', 'POSTGRES_PASSWORD', 'APP_SECRET_KEY', '.env']:
            self.assertNotIn(hidden, response.text)

    def test_template_page_documents_desktop_basic_template_mapping(self):
        client = self._client('finance')
        page = client.get('/backoffice/imports/templates/charge-targets')
        self.assertEqual(page.status_code, 200)
        for text in [
            '本地端基础资料模板对照', '项目', '对象类型', '面积㎡', '物业费单价', '水费标准',
            '身份证号', '租户身份证号', '合同开始日期', '合同结束日期', '店铺名称', '业态/商户类别',
            '本地端字段会映射到云端收费对象、业主和商户字段',
        ]:
            self.assertIn(text, page.text)

    def test_template_routes_require_login(self):
        client = TestClient(create_app())
        self.assertEqual(client.get('/backoffice/imports/templates/charge-targets').status_code, 401)
        self.assertEqual(client.get('/api/imports/templates/charge-targets.csv').status_code, 401)


if __name__ == '__main__':
    unittest.main()
