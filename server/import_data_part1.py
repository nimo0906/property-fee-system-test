from server.import_data_shared import *

class ImportMixinPart1(BaseHandler):
    def _import_page(self):
        flash = self._get_flash()
        import urllib.parse
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        selected_type = (query.get('data_type') or ['auto'])[0]
        def sel(value):
            return ' selected' if selected_type == value else ''
        self._html(self._page('数据导入', flash + f'''
    <div class="import-hero import-hero-pro">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-3">
            <div>
                <div class="page-kicker">DATA INTAKE</div>
                <h4 class="mb-2">数据导入工作台 <span class="text-muted fs-6">导入向导</span></h4>
                <p class="mb-0 text-muted">按“上传预览、字段核对、确认导入、结果复核”处理。基础资料可写入系统；历史收款金额只做识别核对，不自动入账。</p>
            </div>
            <div class="d-flex gap-2 align-items-center">
                <a class="btn btn-outline-secondary" href="/backups"><i class="bi bi-cloud-check"></i> 备份记录</a>
            </div>
        </div>
    </div>
    <div class="import-dashboard">
        <section class="import-upload-panel">
            <div class="section-heading">
                <div>
                    <span class="section-eyebrow">STEP 01</span>
                    <h5>上传文件</h5>
                </div>
                <span class="badge status-info">CSV / XLSX / XLS</span>
            </div>
            <form method=POST action="/import/upload" enctype="multipart/form-data" class="row g-3">
                <div class="col-12">
                    <label class="form-label required-dot">选择文件</label>
                    <input type="file" name="file" class="form-control form-control-lg" accept=".csv,.xlsx,.xls" required>
                    <div class="form-text">最大 10MB。上传后先进入核对表，确认前不会写入数据库。</div>
                </div>
                <div class="col-12">
                    <label class="form-label">数据类型</label>
                    <select name="data_type" class="form-select">
                        <option value="auto"{sel("auto")}>自动检测（推荐）</option>
                        <option value="rooms"{sel("rooms")}>收费对象基础资料</option>
                        <option value="owners"{sel("owners")}>业主信息</option>
                        <option value="payment_ledger"{sel("payment_ledger")}>收款明细识别（不自动入账）</option>
                        <option value="bills"{sel("bills")}>账单记录（谨慎使用）</option>
                        <option value="commercial_contracts"{sel("commercial_contracts")}>商业合同</option>
                        <option value="b_tower_contracts"{sel("b_tower_contracts")}>出租合同（收费对象）</option>
                    </select>
                    <div class="form-text text-warning">自动检测适合模板文件或字段清晰的 Excel；若识别不准确，请手动选择导入类型后重新预览。</div>
                </div>
                <div class="col-12">
                    <div class="import-action-row">
                        <button name="mode" value="preview" class="btn btn-primary btn-lg"><i class="bi bi-eye"></i> 上传并进入核对表</button>
                    </div>
                </div>
            </form>
        </section>
        <aside class="import-side-panel">
            <div class="section-heading">
                <div>
                    <span class="section-eyebrow">CONTROL</span>
                    <h5>导入边界</h5>
                </div>
            </div>
            <div class="import-rule-list">
                <div class="import-rule-item success"><i class="bi bi-check2-circle"></i><div><strong>基础资料导入</strong><span>可写入收费对象、业主、面积、类别、合同日期、备注资料。</span></div></div>
                <div class="import-rule-item success"><i class="bi bi-file-earmark-text"></i><div><strong>合同导入</strong><span>商业合同写入合同档案；出租合同可写入收费对象管理。</span></div></div>
                <div class="import-rule-item warning"><i class="bi bi-exclamation-triangle"></i><div><strong>收款明细识别</strong><span>列头识别、房号归属、合同日期、跳过行和问题行需要核对。</span></div></div>
                <div class="import-rule-item danger"><i class="bi bi-shield-check"></i><div><strong>安全机制</strong><span>确认导入前自动备份，导错后可一键撤销；历史金额不会自动入账。</span></div></div>
            </div>
        </aside>
    </div>

    <div class="card import-review-card mb-3">
        <div class="card-header d-flex flex-wrap justify-content-between align-items-center gap-2">
            <span><i class="bi bi-download"></i> 按类型下载模板</span>
            <span class="badge status-info">建议先套模板再导入</span>
        </div>
        <div class="card-body">
            <div class="row g-2">
                <div class="col-md-4"><a class="btn btn-outline-primary w-100" href="/import/template/basic.xlsx">下载基础资料模板</a></div>
                <div class="col-md-4"><a class="btn btn-outline-primary w-100" href="/import/template/owners.xlsx">业主信息模板</a></div>
                <div class="col-md-4"><a class="btn btn-outline-primary w-100" href="/import/template/payment_ledger.xlsx">收款明细识别模板</a></div>
                <div class="col-md-4"><a class="btn btn-outline-primary w-100" href="/import/template/bills.xlsx">账单记录模板</a></div>
                <div class="col-md-4"><a class="btn btn-outline-primary w-100" href="/import/template/commercial_contracts.xlsx">商业合同模板</a></div>
                <div class="col-md-4"><a class="btn btn-outline-primary w-100" href="/import/template/b_tower_contracts.xlsx">出租合同模板</a></div>
            </div>
            <div class="small text-muted mt-3">不同导入类型字段不同。商业合同模板必须保留“在租合同”sheet；收款明细识别不会自动入账。</div>
        </div>
    </div>
    <div class="import-flow-grid">
        <div class="import-flow-card"><span>01</span><strong>上传预览</strong><small>先看系统识别出的类型、列头和数据行。</small></div>
        <div class="import-flow-card"><span>02</span><strong>字段核对</strong><small>项目、楼栋/区域、单元/分区、房号/铺位号、面积、业主、合同日期必须确认。</small></div>
        <div class="import-flow-card"><span>03</span><strong>确认写入</strong><small>写入前自动创建备份，结果页可撤销。</small></div>
        <div class="import-flow-card"><span>04</span><strong>结果复核</strong><small>下载问题行 CSV，修正后可单独重新导入。</small></div>
    </div>
    ''', 'import'))
