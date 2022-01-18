
;(function(){
    u('.date-utc').each(function(el){
        var $el = u(el);
        $el.text(dayjs($el.data('date')).local().format('YYYY-MM-DD HH:mm:ss'));
    })
    u('.copy-btn').on('click', function(ev){
        var $el = u(ev.currentTarget)
        var tooltip = new bootstrap.Tooltip(ev.currentTarget,
            {'placement': 'right', 'title': 'copied'}
        )
        tooltip.show()
        setTimeout(function(){tooltip.dispose()}, 500)
        navigator.clipboard.writeText($el.data('value'))
    })
})()
