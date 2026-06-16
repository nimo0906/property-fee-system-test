from server.import_data_shared import *
from server.import_data_part1 import ImportMixinPart1
from server.import_data_part2 import ImportMixinPart2
from server.import_data_part3 import ImportMixinPart3

class ImportMixin(ImportPreviewMixin, ImportFeeMappingMixin, ImportViewMixin, ImportMixinPart1, ImportMixinPart2, ImportMixinPart3):
    COLUMN_MAP = {
        '楼栋':'building','building':'building','号楼':'building','栋':'building',
        '单元':'unit','单元/':'unit','单元/座':'unit','单元／座':'unit','单元座':'unit','unit':'unit','座':'unit',
        '房号':'room_number','房号/铺位':'room_number','铺位号/房号':'room_number','room_number':'room_number','房间号':'room_number','房间':'room_number','门牌号':'room_number','number':'room_number','铺位号':'room_number','铺位':'room_number',
        '楼层':'floor','floor':'floor','层':'floor','floor_number':'floor',
        '类别':'category','房屋类别':'category','房间类型':'category','类别信息':'category','类别信息栏':'category','类别栏':'category','房屋类型':'category','物业类型':'category','category':'category','类型':'category','category_name':'category',
        '面积':'area','面积㎡':'area','area':'area','area_sqm':'area','建筑面积':'area','平方':'area',
        '物业费单价':'custom_rate','商业物业费单价':'custom_rate','单价':'custom_rate','custom_rate':'custom_rate',
        '缴费周期':'payment_cycle','收费周期':'payment_cycle','付款周期':'payment_cycle','payment_cycle':'payment_cycle',
        '水费标准':'water_rate_type','水费档位':'water_rate_type','water_rate_type':'water_rate_type',
        '业主':'owner_name','业主姓名':'owner_name','商户名称':'owner_name','owner_name':'owner_name','姓名':'owner_name','name':'owner_name','客户':'owner_name','租户':'owner_name','租户姓名':'tenant_name','租户电话':'tenant_phone','承租人电话':'tenant_phone','租户手机号':'tenant_phone','租户身份证号':'tenant_id_card','承租人身份证号':'tenant_id_card',
        '电话':'owner_phone','业主电话':'owner_phone','phone':'owner_phone','手机':'owner_phone','手机号':'owner_phone','联系电话':'owner_phone','tel':'owner_phone','mobile':'owner_phone',
        '店铺名称':'shop_name','店铺':'shop_name','商铺名称':'shop_name',
        '业态':'business_type','业态/商户类别':'business_type','商户类别':'business_type',
        '合同开始日期':'contract_start','合同起始日期':'contract_start','合同开始':'contract_start','起租日期':'contract_start','租赁开始日期':'contract_start',
        '合同到期日期':'contract_end','合同结束日期':'contract_end','合同截止日期':'contract_end','合同到期':'contract_end','合同结束':'contract_end','租赁结束日期':'contract_end',
        '合同日期':'contract_period','合同期':'contract_period','合同缴租期':'contract_period','合同期限':'contract_period','租赁时间':'contract_period',
        '催缴租金租期':'rent_period','租金租期':'rent_period',
        '身份证':'id_card','id_card':'id_card','身份证号':'id_card','证件号':'id_card',
        '费用类型':'fee_type_name','fee_type_name':'fee_type_name','fee_type':'fee_type_name','费用项目':'fee_type_name','收费项目':'fee_type_name','项目':'fee_type_name',
        '账期':'period','period':'period','月份':'period','billing_period':'period','月':'period','收费月份':'period',
        '用户名称':'owner_name','客户名称':'owner_name','住户名称':'owner_name',
        '金额':'amount','amount':'amount','收费金额':'amount','费用金额':'amount','total_amount':'amount','应收':'amount','应缴':'amount','本期金额':'amount',
        '已缴':'paid_amount','paid_amount':'paid_amount','实缴':'paid_amount','已付':'paid_amount','本期收款(合计)':'paid_amount','本期收款合计':'paid_amount',
        '状态':'status','status':'status','缴费状态':'status','bill_status':'status',
        '缴费日期':'payment_date','payment_date':'payment_date','日期':'payment_date','date':'payment_date','收费日期':'payment_date','付款日期':'payment_date',
        '缴费方式':'payment_method','payment_method':'payment_method','支付方式':'payment_method','method':'payment_method','付款方式':'payment_method',
        '滞纳金':'late_fee','late_fee':'late_fee','违约金':'late_fee',
        '备注':'notes','notes':'notes','note':'notes','remark':'notes','说明':'notes',
    }
