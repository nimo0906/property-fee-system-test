(function(){
    function syncCount(){
        var list=document.getElementById('ownerRoomList'), count=document.getElementById('ownerRoomCount');
        if(!list||!count) return;
        var all=list.querySelectorAll('[name=extra_room_ids]').length, checked=list.querySelectorAll('[name=extra_room_ids]:checked').length;
        count.textContent=all?('（已选 '+checked+'/'+all+'）'):'';
    }
    function setAllRooms(checked){
        document.querySelectorAll('#ownerRoomList [name=extra_room_ids]').forEach(function(c){c.checked=checked;});
        if(window.calcFees) window.calcFees();
        syncCount();
    }
    function ensureStickyTotal(){
        var node=document.getElementById('billingStickyTotal');
        if(node) return node;
        node=document.createElement('div');
        node.id='billingStickyTotal';
        node.className='billing-sticky-total';
        node.innerHTML='<span>当前合计</span><strong>¥0.00</strong>';
        document.body.appendChild(node);
        return node;
    }
    function syncStickyTotal(){
        var source=document.getElementById('totalAmt'), node=ensureStickyTotal();
        if(!source||!node) return;
        node.querySelector('strong').textContent=source.textContent||'¥0.00';
        var rect=source.getBoundingClientRect();
        node.classList.toggle('show', rect.top<0 || rect.bottom>window.innerHeight);
        syncCount();
    }
    document.addEventListener('click', function(e){
        if(e.target.id==='ownerRoomsToggle'){
            var list=document.getElementById('ownerRoomList'); if(!list) return;
            list.classList.toggle('collapsed'); e.target.textContent=list.classList.contains('collapsed')?'展开':'收起';
        }
        if(e.target.id==='ownerRoomsSelectAll') setAllRooms(true);
        if(e.target.id==='ownerRoomsClear') setAllRooms(false);
    });
    document.addEventListener('change', function(e){ if(e.target.name==='extra_room_ids') syncCount(); });
    var oldShow=window.showOwnerRooms;
    window.showOwnerRooms=function(){ if(oldShow) oldShow.apply(this, arguments); syncCount(); };
    var oldCalc=window.calcFees;
    window.calcFees=function(){ if(oldCalc) oldCalc.apply(this, arguments); syncStickyTotal(); };
    window.addEventListener('scroll', syncStickyTotal, true);
    window.addEventListener('resize', syncStickyTotal);
    window.addEventListener('DOMContentLoaded', function(){ ensureStickyTotal(); setTimeout(syncStickyTotal, 0); });
})();
