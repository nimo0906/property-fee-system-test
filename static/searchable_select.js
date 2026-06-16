(function(){
    function optionMatches(opt, q){
        if(!q) return true;
        var text = (opt.textContent || opt.innerText || '').toLowerCase();
        var extra = '';
        if(opt.dataset){
            Object.keys(opt.dataset).forEach(function(k){ extra += ' ' + (opt.dataset[k] || ''); });
        }
        return (text + ' ' + extra.toLowerCase()).indexOf(q) >= 0;
    }

    window.filterSearchableSelect = function(selectId, inputId){
        var sel = document.getElementById(selectId);
        var input = document.getElementById(inputId);
        if(!sel || !input) return;
        var q = (input.value || '').trim().toLowerCase();
        for(var i = 0; i < sel.options.length; i++){
            var opt = sel.options[i];
            var ok = optionMatches(opt, q);
            opt.hidden = !ok;
            opt.disabled = !ok;
            opt.style.display = ok ? '' : 'none';
        }
    };

    window.bindSearchableSelect = function(selectId, inputId){
        var sel = document.getElementById(selectId);
        var input = document.getElementById(inputId);
        if(!sel || !input) return;
        input.addEventListener('input', function(){ window.filterSearchableSelect(selectId, inputId); });
        sel.addEventListener('change', function(){
            if(sel.selectedIndex >= 0){
                input.value = sel.options[sel.selectedIndex].textContent.trim();
            }
        });
    };

    document.addEventListener('DOMContentLoaded', function(){
        document.querySelectorAll('select.searchable-select[data-search-input]').forEach(function(sel){
            window.bindSearchableSelect(sel.id, sel.dataset.searchInput);
        });
    });
})();
