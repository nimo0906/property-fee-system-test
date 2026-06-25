(function(){
  window.togglePaymentGroup = function(id){
    var rows = document.querySelectorAll('.payment-detail-' + id);
    var icon = document.getElementById('pay_icon_' + id);
    rows.forEach(function(row){ row.style.display = row.style.display === 'none' ? '' : 'none'; });
    if(icon){ icon.className = icon.className === 'bi bi-chevron-right' ? 'bi bi-chevron-down' : 'bi bi-chevron-right'; }
  };
  window.togglePaymentSelection = function(id, checked){
    document.querySelectorAll('input[name="payment_ids"][data-payment-group="' + id + '"]').forEach(function(x){ x.checked = checked; });
  };
  window.toggleAllPayments = function(checked){
    document.querySelectorAll('input[name="payment_ids"],.payment-group-chk').forEach(function(x){ x.checked = checked; });
  };
  function appendCsrfToken(form){
    var meta = document.querySelector('meta[name="csrf-token"]');
    if(!meta || !meta.content){
      return;
    }
    var input = document.createElement('input');
    input.type = 'hidden';
    input.name = '_csrf_token';
    input.value = meta.content;
    form.appendChild(input);
  }
  window.submitPaymentAction = function(action){
    var checked = Array.from(document.querySelectorAll('input[name="payment_ids"]:checked'));
    if(!checked.length){
      window.location = '/payments?flash=' + encodeURIComponent('请勾选缴费记录');
      return;
    }
    var form = document.createElement('form');
    form.method = 'POST';
    form.action = action;
    form.target = '_blank';
    form.style.display = 'none';
    checked.forEach(function(x){
      var input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'payment_ids';
      input.value = x.value;
      form.appendChild(input);
    });
    appendCsrfToken(form);
    document.body.appendChild(form);
    form.submit();
    setTimeout(function(){ form.remove(); }, 1000);
  };
})();
